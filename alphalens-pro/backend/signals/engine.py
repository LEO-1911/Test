"""Signal-Engine: Setups prüfen -> Wahrscheinlichkeit aus eigener Ledger-Historie
-> Positionsgröße (Kelly x Vol x Regime) -> unveränderlicher Ledger-Eintrag.

Die Erfolgswahrscheinlichkeit kommt aus der ECHTEN Hit-Rate dieses Signaltyps
(Laplace-geglättet); solange n klein ist, trägt sie das ehrliche
'unkalibriert'-Badge. Kein Signal ohne Stop, Größe und Begründung (USP 4+5)."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ledger.calibration import calibration_status, laplace_rate
from backend.ledger.chain import append_entry, entry_payload
from backend.ledger.outcomes import open_signals, stats_by_signal_type
from backend.models import Instrument, LedgerEntry, PriceBarRow
from backend.scoring.indicators import annualized_volatility
from backend.signals.regime import current_regime
from backend.signals.setups import ACTIVE_SETUPS, INACTIVE_SETUPS, SeriesBundle
from backend.signals.sizing import position_size

log = logging.getLogger(__name__)


def _series(session: Session, ticker: str, day: date, max_bars: int = 400) -> SeriesBundle:
    rows = list(session.execute(
        select(PriceBarRow.close, PriceBarRow.high, PriceBarRow.low, PriceBarRow.volume)
        .where(PriceBarRow.ticker == ticker, PriceBarRow.date <= day)
        .order_by(PriceBarRow.date.desc())
        .limit(max_bars)
    ).all())
    rows.reverse()
    valid = [(float(c), float(h if h is not None else c), float(lo if lo is not None else c),
              float(v if v is not None else 0.0))
             for c, h, lo, v in rows if c is not None]
    return SeriesBundle(
        closes=[r[0] for r in valid], highs=[r[1] for r in valid],
        lows=[r[2] for r in valid], volumes=[r[3] for r in valid],
    )


def signal_probability(session: Session, signal_type: str) -> tuple[float, dict[str, Any]]:
    """Kalibrierte Wahrscheinlichkeit aus der eigenen Historie dieses Signaltyps."""
    stats = {s["signal_type"]: s for s in stats_by_signal_type(session)}
    entry = stats.get(signal_type)
    n_closed = int(entry["n_closed"]) if entry else 0
    n_success = int(entry["n_success"]) if entry else 0
    probability = laplace_rate(n_success, n_closed)
    return round(probability, 4), calibration_status(n_closed)


def generate_signals(session: Session, day: date | None = None) -> dict[str, Any]:
    """Tageslauf: alle Aktien gegen die aktiven Setups prüfen; Treffer ins Ledger."""
    day = day or date.today()
    regime = current_regime(session, day)
    already_open = {
        (e.ticker, str(entry_payload(e).get("signal_type", "")))
        for e in open_signals(session)
    }
    stocks = list(session.scalars(
        select(Instrument).where(Instrument.asset_type == "stock")
    ))
    created: list[dict[str, Any]] = []
    checked = 0
    for inst in stocks:
        series = _series(session, inst.ticker, day)
        if len(series.closes) < 210:
            continue
        checked += 1
        realized_vol = annualized_volatility(series.closes, 252)
        for signal_type, check in ACTIVE_SETUPS.items():
            if (inst.ticker, signal_type) in already_open:
                continue  # dasselbe Setup nicht doppelt offen halten
            try:
                candidate = check(series)
            except Exception as exc:  # noqa: BLE001 — ein Ticker stoppt nie den Lauf
                log.warning("Setup %s/%s übersprungen: %s", inst.ticker, signal_type, exc)
                continue
            if candidate is None:
                continue
            probability, calibration = signal_probability(session, signal_type)
            sizing = position_size(
                probability, candidate.entry, candidate.stop, candidate.target,
                realized_vol, regime_factor=float(regime["factor"]),
            )
            entry = append_entry(
                session, entry_type="signal", ticker=inst.ticker,
                payload={
                    "signal_type": signal_type,
                    "entry": candidate.entry, "stop": candidate.stop,
                    "target": candidate.target, "horizon_days": candidate.horizon_days,
                    "atr": candidate.atr_value,
                    "why": candidate.why,
                    "sizing": sizing,
                    "calibration": calibration,
                    "regime": {"regime": regime["regime"], "factor": regime["factor"]},
                },
                price_at_creation=candidate.entry,
                probability=probability,
            )
            created.append({"id": entry.id, "ticker": inst.ticker,
                            "signal_type": signal_type})
    return {
        "date": day.isoformat(),
        "regime": regime["regime"],
        "regime_factor": regime["factor"],
        "stocks_checked": checked,
        "signals_created": len(created),
        "created": created,
        "inactive_setups": INACTIVE_SETUPS,
    }


def list_signals(session: Session, limit: int = 100) -> list[dict[str, Any]]:
    """Signale (neueste zuerst) mit Payload und ggf. Outcome — für die Signale-Seite."""
    outcome_by_ref: dict[int, dict[str, Any]] = {}
    for e in session.scalars(
        select(LedgerEntry).where(LedgerEntry.entry_type == "outcome")
    ):
        if e.ref_id is not None:
            outcome_by_ref[e.ref_id] = entry_payload(e)
    signals = list(session.scalars(
        select(LedgerEntry).where(LedgerEntry.entry_type == "signal")
        .order_by(LedgerEntry.id.desc()).limit(limit)
    ))
    return [
        {
            "id": e.id, "ts_utc": e.ts_utc.isoformat(), "ticker": e.ticker,
            "probability": e.probability, "payload": entry_payload(e),
            "outcome": outcome_by_ref.get(e.id),
        }
        for e in signals
    ]
