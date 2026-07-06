"""Kern-Invarianten des Point-in-Time-Speichers: kein Lookahead, append-only,
Inkremental-Cache. Auf diese Tests verlassen sich Scoring und Backtest (MS2/MS6)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from backend.data import store
from backend.data.providers.base import FundamentalPoint, PriceBar


def _fp(value: float, as_of: datetime) -> FundamentalPoint:
    return FundamentalPoint(
        ticker="TEST", metric="pe_ttm", value=value, period="ttm", as_of=as_of, source="test"
    )


def test_asof_read_never_sees_future_values(session: Session) -> None:
    """Anti-Lookahead: ein Stichtag vor der zweiten Revision sieht nur die erste."""
    store.insert_fundamentals(session, [_fp(20.0, datetime(2026, 1, 10))])
    store.insert_fundamentals(session, [_fp(25.0, datetime(2026, 3, 10))])

    assert store.get_fundamental_asof(session, "TEST", "pe_ttm", datetime(2026, 2, 1)) == 20.0
    assert store.get_fundamental_asof(session, "TEST", "pe_ttm", datetime(2026, 4, 1)) == 25.0
    # Vor der ersten Kenntnisnahme: nichts bekannt
    assert store.get_fundamental_asof(session, "TEST", "pe_ttm", datetime(2025, 12, 1)) is None


def test_unchanged_value_creates_no_new_row(session: Session) -> None:
    assert store.insert_fundamentals(session, [_fp(20.0, datetime(2026, 1, 10))]) == 1
    assert store.insert_fundamentals(session, [_fp(20.0, datetime(2026, 1, 11))]) == 0
    assert store.insert_fundamentals(session, [_fp(21.0, datetime(2026, 1, 12))]) == 1


def _bar(day: date, close: float = 100.0) -> PriceBar:
    return PriceBar(ticker="TEST", date=day, open=close, high=close, low=close,
                    close=close, adj_close=close, volume=1000.0)


def test_price_upsert_is_idempotent(session: Session) -> None:
    bars = [_bar(date(2026, 1, d)) for d in (5, 6, 7)]
    assert store.upsert_price_bars(session, bars) == 3
    # Zweiter Lauf mit denselben + einer neuen Bar: nur die neue wird geschrieben
    assert store.upsert_price_bars(session, [*bars, _bar(date(2026, 1, 8))]) == 1
    assert store.latest_price_date(session, "TEST") == date(2026, 1, 8)


def test_fetch_log_tracks_errors_and_recovery(session: Session) -> None:
    store.record_fetch(session, "TEST", "prices", ok=False, error_msg="timeout")
    store.record_fetch(session, "TEST", "prices", ok=False, error_msg="timeout")
    store.record_fetch(session, "TEST", "prices", ok=True)
    assert store.is_stale(session, "TEST", "prices", max_age_hours=1) is False
    # Nie gefetcht -> stale
    assert store.is_stale(session, "NEU", "prices", max_age_hours=1) is True
