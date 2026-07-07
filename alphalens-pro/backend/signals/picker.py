"""Wöchentlicher Stock Picker (M3): Top-N nach Composite Score, Regime-gedrosselt,
jeder Pick sofort ins Ledger. Der optionale Sonnet-Deep-Dive KOMMENTIERT die
Quant-Auswahl — er trifft sie nicht.

Größenlogik der Picks: Gleichgewichtung (100/N %) x Regime-Faktor, gekappt.
Bewusst kein Pseudo-Kelly: Picks haben kein Kursziel, also keine seriöse
Payoff-Schätzung — Gleichgewichtung ist die ehrliche Wahl."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ai.client import deep_dive_pick
from backend.ledger.calibration import calibration_status, laplace_rate
from backend.ledger.chain import append_entry, entry_payload
from backend.ledger.outcomes import stats_by_signal_type
from backend.models import LedgerEntry
from backend.scoring.engine import score_breakdown, top_scores
from backend.scoring.indicators import atr as atr_indicator
from backend.settings import load_config
from backend.signals.engine import _series
from backend.signals.regime import current_regime

log = logging.getLogger(__name__)

PICK_SIGNAL_TYPE = "weekly_pick"


def _iso_week(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def picks_exist_for_week(session: Session, week: str) -> bool:
    for e in session.scalars(select(LedgerEntry).where(LedgerEntry.entry_type == "pick")):
        if entry_payload(e).get("week") == week:
            return True
    return False


def run_weekly_picks(
    session: Session, day: date | None = None, *, with_ai: bool = True
) -> dict[str, Any]:
    """Montags-Lauf: Top-N ins Ledger. Idempotent pro Kalenderwoche."""
    day = day or date.today()
    week = _iso_week(day)
    cfg = load_config("signals")["picker"]
    if picks_exist_for_week(session, week):
        return {"week": week, "created": 0, "skipped": "Picks für diese Woche existieren"}

    regime = current_regime(session, day)
    ranking = top_scores(session, limit=int(cfg["top_n"]) * 2, day=None)
    candidates = [r for r in ranking if r["composite"] >= float(cfg["min_composite"])]
    candidates = candidates[: int(cfg["top_n"])]
    if not candidates:
        return {"week": week, "created": 0,
                "skipped": f"kein Composite >= {cfg['min_composite']} (ehrlich: keine Picks)"}

    # Wahrscheinlichkeit aus der echten Historie aller bisherigen Wochen-Picks
    stats = {s["signal_type"]: s for s in stats_by_signal_type(session)}
    hist = stats.get(PICK_SIGNAL_TYPE)
    n_closed = int(hist["n_closed"]) if hist else 0
    n_success = int(hist["n_success"]) if hist else 0
    probability = round(laplace_rate(n_success, n_closed), 4)
    calibration = calibration_status(n_closed)

    equal_weight = 100.0 / int(cfg["top_n"])
    size_pct = round(min(equal_weight, 25.0) * float(regime["factor"]), 2)

    created: list[dict[str, Any]] = []
    for rank, row in enumerate(candidates, start=1):
        ticker = str(row["ticker"])
        series = _series(session, ticker, day)
        if not series.closes:
            log.warning("Pick %s übersprungen: keine Kurse", ticker)
            continue
        entry_price = series.closes[-1]
        atr_value = atr_indicator(series.highs, series.lows, series.closes, 14)
        stop = (round(entry_price - float(cfg["stop_atr_multiple"]) * atr_value, 4)
                if atr_value else None)
        breakdown = score_breakdown(session, ticker)
        ai_result: dict[str, Any] = {"skipped": "KI deaktiviert für diesen Lauf"}
        if with_ai:
            ai_result = deep_dive_pick(session, ticker, {
                "rank": rank, "composite": row["composite"], "pillars": row["pillars"],
                "risk_score": row.get("risk_score"),
                "breakdown": breakdown["pillars"] if breakdown else None,
                "regime": regime["regime"],
            })
        pick = append_entry(
            session, entry_type="pick", ticker=ticker,
            payload={
                "signal_type": PICK_SIGNAL_TYPE,
                "week": week, "rank": rank,
                "composite": row["composite"], "pillars": row["pillars"],
                "risk_score": row.get("risk_score"),
                "entry": entry_price, "stop": stop, "target": None,
                "horizon_days": int(cfg["horizon_days"]),
                "sizing": {
                    "final_pct": size_pct,
                    "steps": (f"Gleichgewichtung 100/{cfg['top_n']} = {equal_weight:.1f} % "
                              f"x Regime {regime['factor']} = {size_pct} %"),
                },
                "calibration": calibration,
                "regime": {"regime": regime["regime"], "factor": regime["factor"]},
                "ai": ai_result,
            },
            price_at_creation=entry_price,
            probability=probability,
        )
        created.append({"id": pick.id, "rank": rank, "ticker": ticker,
                        "composite": row["composite"]})
    return {"week": week, "regime": regime["regime"], "created": len(created),
            "picks": created}


def picks_overview(session: Session) -> dict[str, Any]:
    """Aktuelle Woche + ehrliche Historie aller bisherigen Wochen (mit Benchmark)."""
    picks = list(session.scalars(
        select(LedgerEntry).where(LedgerEntry.entry_type == "pick").order_by(LedgerEntry.id)
    ))
    outcome_by_ref: dict[int, dict[str, Any]] = {}
    for e in session.scalars(select(LedgerEntry).where(LedgerEntry.entry_type == "outcome")):
        if e.ref_id is not None:
            outcome_by_ref[e.ref_id] = entry_payload(e)

    weeks: dict[str, list[dict[str, Any]]] = {}
    for pick in picks:
        payload = entry_payload(pick)
        weeks.setdefault(str(payload.get("week", "?")), []).append({
            "id": pick.id, "ts_utc": pick.ts_utc.isoformat(), "ticker": pick.ticker,
            "probability": pick.probability, "payload": payload,
            "outcome": outcome_by_ref.get(pick.id),
        })

    history = []
    for week in sorted(weeks, reverse=True):
        entries = weeks[week]
        closed = [e for e in entries if e["outcome"]]
        returns = [float(e["outcome"].get("return_pct", 0.0)) for e in closed]
        benchmark = _benchmark_return(session, entries)
        history.append({
            "week": week, "n": len(entries), "n_closed": len(closed),
            "avg_return_pct": round(sum(returns) / len(returns), 3) if returns else None,
            "hit_rate": (round(sum(1 for e in closed
                                   if e["outcome"].get("success")) / len(closed), 4)
                         if closed else None),
            "benchmark_return_pct": benchmark,
            "picks": entries,
        })
    return {"weeks": history}


def _benchmark_return(session: Session, entries: list[dict[str, Any]]) -> float | None:
    """S&P-500-Rendite über dasselbe Fenster (Pick-Datum + Horizont). Ohne
    ^GSPC-Daten ehrlich None statt einer erfundenen Benchmark."""
    if not entries:
        return None
    first = entries[0]
    start = date.fromisoformat(first["ts_utc"][:10])
    horizon = int(first["payload"].get("horizon_days", 5))
    from backend.models import PriceBarRow

    rows = list(session.execute(
        select(PriceBarRow.date, PriceBarRow.close)
        .where(PriceBarRow.ticker == "^GSPC", PriceBarRow.date >= start)
        .order_by(PriceBarRow.date)
        .limit(horizon + 1)
    ).all())
    valid = [(d, float(c)) for d, c in rows if c is not None]
    if len(valid) < 2:
        return None
    start_close = valid[0][1]
    end_close = valid[min(horizon, len(valid) - 1)][1]
    if start_close == 0:
        return None
    return round((end_close / start_close - 1) * 100, 3)
