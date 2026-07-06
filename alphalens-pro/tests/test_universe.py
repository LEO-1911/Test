from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.data.universe import SEED_CONSTITUENTS, refresh_universe, watchlist_tickers
from backend.models import IndexMembership, Instrument


def test_refresh_offline_uses_seed_lists(session: Session) -> None:
    summary = refresh_universe(session, allow_network=False)
    assert all("builtin_seed" in v for v in summary.values())

    tickers = set(session.scalars(select(Instrument.ticker)))
    # Referenz-Ticker aus Seed/ETF/Watchlist müssen vorhanden sein
    for ticker in ("AAPL", "SAP.DE", "VWCE.DE", "^VIX", "EURUSD=X"):
        assert ticker in tickers, f"{ticker} fehlt im Universum"

    memberships = list(session.scalars(select(IndexMembership)))
    assert len(memberships) >= sum(len(v) for v in SEED_CONSTITUENTS.values()) - 20
    assert all(m.valid_to is None for m in memberships)


def test_refresh_is_idempotent(session: Session) -> None:
    refresh_universe(session, allow_network=False)
    count_first = len(list(session.scalars(select(Instrument.ticker))))
    refresh_universe(session, allow_network=False)
    count_second = len(list(session.scalars(select(Instrument.ticker))))
    assert count_first == count_second


def test_watchlist_from_config() -> None:
    watchlist = watchlist_tickers()
    assert "AAPL" in watchlist
    assert "SAP.DE" in watchlist
    assert "VWCE.DE" in watchlist


def test_etf_and_crypto_asset_types(session: Session) -> None:
    refresh_universe(session, allow_network=False)
    vwce = session.get(Instrument, "VWCE.DE")
    btc = session.get(Instrument, "BTC-USD")
    assert vwce is not None and vwce.asset_type == "etf"
    assert btc is not None and btc.asset_type == "crypto"
