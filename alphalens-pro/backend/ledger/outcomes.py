"""Outcome-Evaluator: wertet offene Signale/Picks gegen den tatsächlichen
Kursverlauf aus und schreibt das Ergebnis als NEUEN verketteten Ledger-Eintrag.

Regeln (konservativ und dokumentiert):
- Bewertet wird auf Tagesbasis ab dem Handelstag NACH der Signalerstellung.
- Reißt Low den Stop und High das Ziel am selben Tag, zählt der Stop (ehrlich-
  konservativ — intraday wissen wir es nicht).
- Nach horizon_days ohne Stop/Ziel: Exit zum Schlusskurs ("expired").
- Erfolg := realisierte Rendite > 0 (Basis für Hit-Rate und Brier-Score)."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.data.store import get_price_bars
from backend.ledger import calibration
from backend.ledger.chain import append_entry, entry_payload
from backend.models import LedgerEntry

log = logging.getLogger(__name__)

EVALUABLE_TYPES = ("signal", "pick")
DEFAULT_HORIZON_DAYS = 20  # Handelstage, falls das Signal keinen Horizont mitbringt


def open_signals(session: Session) -> list[LedgerEntry]:
    """Signale/Picks ohne Outcome-Eintrag (ref_id-Verknüpfung)."""
    evaluated_refs = {
        ref for ref in session.scalars(
            select(LedgerEntry.ref_id).where(LedgerEntry.entry_type == "outcome")
        ) if ref is not None
    }
    return [
        e for e in session.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.entry_type.in_(EVALUABLE_TYPES))
            .order_by(LedgerEntry.id)
        )
        if e.id not in evaluated_refs
    ]


def _evaluate_one(
    session: Session, signal: LedgerEntry, as_of: date
) -> dict[str, Any] | None:
    """Liefert das Outcome-Payload oder None, wenn das Signal noch offen ist."""
    payload = entry_payload(signal)
    entry_price = float(payload.get("entry") or signal.price_at_creation or 0)
    if entry_price <= 0:
        return {"result": "invalid", "reason": "kein Entry-Preis", "return_pct": 0.0,
                "success": False, "exit_price": None, "days_held": 0}
    stop = payload.get("stop")
    target = payload.get("target")
    horizon = int(payload.get("horizon_days", DEFAULT_HORIZON_DAYS))
    signal_date = signal.ts_utc.date()
    bars = get_price_bars(session, signal.ticker,
                          start=signal_date + timedelta(days=1), end=as_of)
    days_held = 0
    for bar in bars:
        days_held += 1
        low = bar.low if bar.low is not None else bar.close
        high = bar.high if bar.high is not None else bar.close
        if stop is not None and low is not None and low <= float(stop):
            exit_price = float(stop)  # konservativ: Stop vor Ziel
            return {"result": "stop_hit", "exit_price": exit_price,
                    "return_pct": round((exit_price / entry_price - 1) * 100, 3),
                    "success": exit_price > entry_price, "days_held": days_held}
        if target is not None and high is not None and high >= float(target):
            exit_price = float(target)
            return {"result": "target_hit", "exit_price": exit_price,
                    "return_pct": round((exit_price / entry_price - 1) * 100, 3),
                    "success": exit_price > entry_price, "days_held": days_held}
        if days_held >= horizon:
            if bar.close is None:
                continue
            exit_price = float(bar.close)
            return {"result": "expired", "exit_price": exit_price,
                    "return_pct": round((exit_price / entry_price - 1) * 100, 3),
                    "success": exit_price > entry_price, "days_held": days_held}
    return None  # noch offen


def evaluate_open_signals(session: Session, as_of: date | None = None) -> dict[str, int]:
    """Tagesjob: alle offenen Signale prüfen, abgeschlossene als Outcome verketten."""
    as_of = as_of or date.today()
    closed = still_open = 0
    for signal in open_signals(session):
        try:
            outcome = _evaluate_one(session, signal, as_of)
        except Exception as exc:  # noqa: BLE001 — ein kaputtes Signal stoppt nie den Lauf
            log.warning("Outcome-Auswertung für Ledger #%d übersprungen: %s", signal.id, exc)
            continue
        if outcome is None:
            still_open += 1
            continue
        append_entry(
            session, entry_type="outcome", ticker=signal.ticker,
            payload={**outcome, "signal_type": entry_payload(signal).get("signal_type", "?")},
            ref_id=signal.id,
        )
        closed += 1
    return {"closed": closed, "still_open": still_open}


def stats_by_signal_type(session: Session) -> list[dict[str, Any]]:
    """Track-Record-Aggregation: je Signaltyp n, Hit-Rate (roh + Laplace),
    Ø-Rendite, Brier-Score und Kalibrierungs-Badge."""
    signals = {
        e.id: e for e in session.scalars(
            select(LedgerEntry).where(LedgerEntry.entry_type.in_(EVALUABLE_TYPES))
        )
    }
    outcomes = list(session.scalars(
        select(LedgerEntry).where(LedgerEntry.entry_type == "outcome")
    ))
    grouped: dict[str, dict[str, Any]] = {}
    for signal in signals.values():
        signal_type = str(entry_payload(signal).get("signal_type", "?"))
        g = grouped.setdefault(signal_type, {
            "signal_type": signal_type, "n_signals": 0, "n_closed": 0,
            "n_success": 0, "returns": [], "brier_pairs": [],
        })
        g["n_signals"] += 1
    for outcome in outcomes:
        src = signals.get(outcome.ref_id or -1)
        if src is None:
            continue
        signal_type = str(entry_payload(src).get("signal_type", "?"))
        g = grouped[signal_type]
        data = entry_payload(outcome)
        success = bool(data.get("success"))
        g["n_closed"] += 1
        g["n_success"] += int(success)
        g["returns"].append(float(data.get("return_pct", 0.0)))
        if src.probability is not None:
            g["brier_pairs"].append((float(src.probability), int(success)))

    results = []
    for g in grouped.values():
        returns: list[float] = g.pop("returns")
        pairs: list[tuple[float, int]] = g.pop("brier_pairs")
        n_closed, n_success = g["n_closed"], g["n_success"]
        results.append({
            **g,
            "hit_rate": round(n_success / n_closed, 4) if n_closed else None,
            "hit_rate_laplace": round(calibration.laplace_rate(n_success, n_closed), 4),
            "avg_return_pct": round(sum(returns) / len(returns), 3) if returns else None,
            "brier": (round(b, 4) if (b := calibration.brier_score(pairs)) is not None
                      else None),
            "calibration": calibration.calibration_status(n_closed),
        })
    results.sort(key=lambda r: r["signal_type"])
    return results


def reliability_pairs(session: Session, signal_type: str | None = None) -> list[tuple[float, int]]:
    """(Prognose, Ausgang)-Paare fürs Reliability-Diagramm."""
    signals = {
        e.id: e for e in session.scalars(
            select(LedgerEntry).where(LedgerEntry.entry_type.in_(EVALUABLE_TYPES))
        )
    }
    pairs: list[tuple[float, int]] = []
    for outcome in session.scalars(
        select(LedgerEntry).where(LedgerEntry.entry_type == "outcome")
    ):
        signal = signals.get(outcome.ref_id or -1)
        if signal is None or signal.probability is None:
            continue
        if signal_type and entry_payload(signal).get("signal_type") != signal_type:
            continue
        pairs.append((float(signal.probability), int(bool(entry_payload(outcome).get("success")))))
    return pairs
