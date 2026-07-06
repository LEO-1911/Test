"""Pipeline-Verhalten: Inkremental-Fetch, Fehlertoleranz (ein kaputter Ticker
stoppt nie den Lauf), rollierende Fundamentals."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.data import store
from backend.data.fixtures import FixtureProvider
from backend.data.pipeline import update_fundamentals, update_prices
from backend.data.universe import _ensure_instrument
from backend.models import FetchLog, FundamentalRow


def _setup(session: Session, tickers: list[str]) -> None:
    for ticker in tickers:
        _ensure_instrument(session, ticker, source="watchlist")


def test_second_run_fetches_nothing_new(session: Session) -> None:
    _setup(session, ["AAPL"])
    provider = FixtureProvider()
    first = update_prices(session, provider, ["AAPL"])
    assert first.get("AAPL", 0) > 200  # voller Backfill beim ersten Lauf

    second = update_prices(session, provider, ["AAPL"])
    # Cache greift: keine oder höchstens die heutige Bar neu
    assert second.get("AAPL", 0) <= 1


def test_failing_ticker_is_skipped_and_logged(session: Session) -> None:
    _setup(session, ["AAPL", "KAPUTT"])
    provider = FixtureProvider(failing_tickers={"KAPUTT"})

    prices = update_prices(session, provider, ["AAPL", "KAPUTT"])
    assert "AAPL" in prices and "KAPUTT" not in prices

    update_fundamentals(session, provider, ["AAPL", "KAPUTT"], limit=2)
    log_entry = session.scalar(
        select(FetchLog).where(FetchLog.ticker == "KAPUTT", FetchLog.kind == "fundamentals")
    )
    assert log_entry is not None
    assert log_entry.consecutive_errors >= 1
    assert "Fixture" in log_entry.last_error_msg

    # Der intakte Ticker hat trotzdem Fundamentals bekommen
    rows = list(session.scalars(select(FundamentalRow).where(FundamentalRow.ticker == "AAPL")))
    assert rows


def test_fundamentals_rolling_prefers_never_fetched(session: Session) -> None:
    _setup(session, ["ALT", "NEU"])
    store.record_fetch(session, "ALT", "fundamentals", ok=True)
    due = store.fundamentals_due(session, ["ALT", "NEU"], limit=1)
    assert due == ["NEU"]


def test_price_bars_are_business_days_only(session: Session) -> None:
    _setup(session, ["AAPL"])
    update_prices(session, FixtureProvider(), ["AAPL"])
    bars = store.get_price_bars(session, "AAPL", start=date(2025, 1, 1))
    assert bars
    assert all(b.date.weekday() < 5 for b in bars)
