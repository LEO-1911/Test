"""Ledger-Kern: Hash-Chain-Integrität, Append-only-Trigger, Manipulationserkennung,
Outcome-Auswertung mit allen Fällen (Ziel, Stop, Expiry, offen)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from backend.data.providers.base import PriceBar
from backend.data.store import upsert_price_bars
from backend.ledger.chain import (
    GENESIS_HASH,
    append_entry,
    entry_payload,
    verify_chain,
)
from backend.ledger.outcomes import (
    evaluate_open_signals,
    open_signals,
    stats_by_signal_type,
)

TS = datetime(2026, 6, 1, 14, 30)


def _signal(session: Session, *, entry: float = 100.0, stop: float = 95.0,
            target: float = 110.0, horizon: int = 20, prob: float = 0.65,
            signal_type: str = "breakout", ts: datetime = TS):
    return append_entry(
        session, entry_type="signal", ticker="AAPL",
        payload={"signal_type": signal_type, "entry": entry, "stop": stop,
                 "target": target, "horizon_days": horizon},
        price_at_creation=entry, probability=prob, ts_utc=ts,
    )


def _bars(session: Session, closes: list[float], spread: float = 1.0) -> None:
    bars = [
        PriceBar(ticker="AAPL", date=date(2026, 6, 2) + timedelta(days=i),
                 open=c, high=c + spread, low=c - spread, close=c, adj_close=c, volume=1e6)
        for i, c in enumerate(closes)
    ]
    upsert_price_bars(session, bars)


# ---------------------------------------------------------------- Kette

def test_chain_links_and_verifies(session: Session) -> None:
    e1 = _signal(session)
    e2 = _signal(session, signal_type="mean_reversion", ts=TS + timedelta(hours=1))
    assert e1.prev_hash == GENESIS_HASH
    assert e2.prev_hash == e1.entry_hash
    assert len(e1.entry_hash) == 64
    result = verify_chain(session)
    assert result["valid"] is True
    assert result["entries"] == 2


def test_update_and_delete_blocked_by_trigger(session: Session) -> None:
    _signal(session)
    session.commit()
    with pytest.raises(DatabaseError, match="append-only"):
        session.execute(text("UPDATE ledger_entries SET ticker = 'MANIPULIERT' WHERE id = 1"))
    session.rollback()
    with pytest.raises(DatabaseError, match="append-only"):
        session.execute(text("DELETE FROM ledger_entries WHERE id = 1"))
    session.rollback()


def test_tampering_detected_even_without_triggers(session: Session) -> None:
    """Angreifer entfernt Trigger und ändert Daten direkt -> Kette bricht."""
    _signal(session)
    _signal(session, signal_type="mean_reversion", ts=TS + timedelta(hours=1))
    session.commit()
    session.execute(text("DROP TRIGGER ledger_entries_no_update"))
    session.execute(text("UPDATE ledger_entries SET price_at_creation = 42.0 WHERE id = 1"))
    session.commit()
    result = verify_chain(session)
    assert result["valid"] is False
    assert result["first_broken_id"] == 1
    assert "Manipulation" in result["error"]


def test_probability_bounds_enforced(session: Session) -> None:
    with pytest.raises(ValueError, match="probability"):
        _signal(session, prob=1.5)
    with pytest.raises(ValueError, match="entry_type"):
        append_entry(session, entry_type="quatsch", ticker="X", payload={})


# ---------------------------------------------------------------- Outcomes

def test_outcome_target_hit(session: Session) -> None:
    _signal(session, entry=100.0, stop=95.0, target=110.0)
    _bars(session, [102.0, 106.0, 109.5])  # High 110.5 am dritten Tag -> Ziel
    summary = evaluate_open_signals(session, as_of=date(2026, 6, 30))
    assert summary == {"closed": 1, "still_open": 0}
    outcome = entry_payload(open_or_outcome(session))
    assert outcome["result"] == "target_hit"
    assert outcome["return_pct"] == pytest.approx(10.0)
    assert outcome["success"] is True


def open_or_outcome(session: Session):
    from sqlalchemy import select

    from backend.models import LedgerEntry

    entry = session.scalar(select(LedgerEntry).where(LedgerEntry.entry_type == "outcome"))
    assert entry is not None
    return entry


def test_outcome_stop_hit_and_conservative_same_day(session: Session) -> None:
    """Reißen Stop UND Ziel am selben Tag, zählt konservativ der Stop."""
    _signal(session, entry=100.0, stop=95.0, target=105.0)
    _bars(session, [100.0], spread=10.0)  # Low 90 (Stop), High 110 (Ziel) am selben Tag
    evaluate_open_signals(session, as_of=date(2026, 6, 30))
    outcome = entry_payload(open_or_outcome(session))
    assert outcome["result"] == "stop_hit"
    assert outcome["return_pct"] == pytest.approx(-5.0)
    assert outcome["success"] is False


def test_outcome_expired_at_horizon(session: Session) -> None:
    _signal(session, entry=100.0, stop=90.0, target=120.0, horizon=3)
    _bars(session, [101.0, 102.0, 103.0, 104.0], spread=0.5)
    evaluate_open_signals(session, as_of=date(2026, 6, 30))
    outcome = entry_payload(open_or_outcome(session))
    assert outcome["result"] == "expired"
    assert outcome["days_held"] == 3
    assert outcome["return_pct"] == pytest.approx(3.0)
    assert outcome["success"] is True


def test_signal_stays_open_without_trigger_conditions(session: Session) -> None:
    _signal(session, entry=100.0, stop=90.0, target=120.0, horizon=30)
    _bars(session, [101.0, 102.0], spread=0.5)
    summary = evaluate_open_signals(session, as_of=date(2026, 6, 30))
    assert summary == {"closed": 0, "still_open": 1}
    assert len(open_signals(session)) == 1


def test_outcome_evaluation_is_idempotent(session: Session) -> None:
    _signal(session, entry=100.0, stop=95.0, target=110.0)
    _bars(session, [111.0])
    evaluate_open_signals(session, as_of=date(2026, 6, 30))
    second = evaluate_open_signals(session, as_of=date(2026, 6, 30))
    assert second == {"closed": 0, "still_open": 0}  # nichts doppelt bewertet
    assert verify_chain(session)["valid"] is True


# ---------------------------------------------------------------- Statistiken

def test_stats_by_signal_type_known_values(session: Session) -> None:
    # Zwei Breakouts: eines trifft das Ziel, eines den Stop
    _signal(session, entry=100.0, stop=95.0, target=110.0, prob=0.8, ts=TS)
    _signal(session, entry=100.0, stop=99.5, target=200.0, prob=0.6,
            ts=TS + timedelta(minutes=5))
    _bars(session, [111.0], spread=12.0)  # Ziel 110 UND Stop 99.5 am selben Tag
    evaluate_open_signals(session, as_of=date(2026, 6, 30))
    stats = stats_by_signal_type(session)
    assert len(stats) == 1
    s = stats[0]
    assert s["signal_type"] == "breakout"
    assert s["n_signals"] == 2 and s["n_closed"] == 2
    # Signal 1: Stop 95 nicht gerissen (Low 99) -> Ziel 110 -> Erfolg.
    # Signal 2: Stop 99.5 gerissen -> Misserfolg. Hit-Rate roh = 0.5
    assert s["hit_rate"] == pytest.approx(0.5)
    assert s["hit_rate_laplace"] == pytest.approx(0.5)
    # Brier: (0.8-1)^2=0.04, (0.6-0)^2=0.36 -> Mittel 0.20
    assert s["brier"] == pytest.approx(0.20)
    # Ø-Rendite: +10 % und -0.5 % -> 4.75 %
    assert s["avg_return_pct"] == pytest.approx(4.75)
    assert s["calibration"]["calibrated"] is False
    assert "unkalibriert" in s["calibration"]["label"]


def test_pipeline_runs_scoring_and_outcomes(session: Session) -> None:
    """Der Tageslauf muss Scoring UND Outcome-Auswertung enthalten (Regression:
    dieser Hook ging einmal durch einen Workspace-Reset verloren)."""
    from backend.data.fixtures import FixtureProvider
    from backend.data.pipeline import run_daily_update

    summary = run_daily_update(session, FixtureProvider(), fundamentals_limit=2)
    assert "scoring" in summary and "error" not in summary["scoring"]
    assert "ledger_outcomes" in summary and "error" not in summary["ledger_outcomes"]
