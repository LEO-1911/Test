"""Engine-, Regime-, Picker- und Budget-Tests auf konstruierten Daten."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from backend.ai.budget import BudgetExceeded, budget_status, ensure_budget, record_usage
from backend.data.providers.base import PriceBar
from backend.data.store import upsert_market_state, upsert_price_bars
from backend.data.universe import _ensure_instrument
from backend.ledger.chain import entry_payload, verify_chain
from backend.ledger.outcomes import open_signals
from backend.signals.engine import generate_signals, signal_probability
from backend.signals.picker import picks_overview, run_weekly_picks
from backend.signals.regime import current_regime

TODAY = date(2026, 7, 7)


def _seed_prices(session: Session, ticker: str, closes: list[float],
                 volumes: list[float] | None = None, spread: float = 1.0) -> None:
    volumes = volumes or [1_000_000.0] * len(closes)
    start = TODAY - timedelta(days=int(len(closes) * 1.45))  # Wochenenden ausgleichen
    bars = []
    day = start
    i = 0
    while i < len(closes):
        if day.weekday() < 5:
            c = closes[i]
            bars.append(PriceBar(ticker=ticker, date=day, open=c, high=c + spread,
                                 low=c - spread, close=c, adj_close=c, volume=volumes[i]))
            i += 1
        day += timedelta(days=1)
    upsert_price_bars(session, bars)


def _uptrend_with_dip(n: int = 300) -> list[float]:
    """Aufwärtstrend + moderater Rücksetzer: RSI < 30, Kurs bleibt über MA200."""
    closes = [100.0 + i * 0.3 for i in range(n)]
    closes += [closes[-1] - 1.2 * i for i in range(1, 16)]
    return closes


# ---------------------------------------------------------------- Regime

def test_regime_risk_on_with_healthy_market(session: Session) -> None:
    _ensure_instrument(session, "^GSPC", asset_type="index", source="market_symbol")
    _seed_prices(session, "^GSPC", [4000.0 + i for i in range(300)])
    upsert_market_state(session, TODAY, "vix", 14.0)
    upsert_market_state(session, TODAY, "breadth_pct_above_ma200", 65.0)
    result = current_regime(session, TODAY)
    assert result["regime"] == "risk_on"
    assert result["factor"] == 1.0
    assert result["breaches"] == 0


def test_regime_risk_off_with_two_breaches(session: Session) -> None:
    _ensure_instrument(session, "^GSPC", asset_type="index", source="market_symbol")
    _seed_prices(session, "^GSPC", [5000.0 - i * 3 for i in range(300)])  # unter MA200
    upsert_market_state(session, TODAY, "vix", 32.0)                       # über 25
    upsert_market_state(session, TODAY, "breadth_pct_above_ma200", 55.0)   # ok
    result = current_regime(session, TODAY)
    assert result["breaches"] == 2
    assert result["regime"] == "risk_off"
    assert result["factor"] == 0.25


def test_regime_honest_about_missing_data(session: Session) -> None:
    result = current_regime(session, TODAY)
    assert result["regime"] == "risk_on"  # keine Daten = kein Breach, aber:
    assert result["data_complete"] is False
    assert all(not c["evaluable"] for c in result["criteria"])


# ---------------------------------------------------------------- Signal-Engine

def test_generate_signals_writes_to_ledger_with_full_context(session: Session) -> None:
    _ensure_instrument(session, "TREND", source="watchlist")
    _seed_prices(session, "TREND", _uptrend_with_dip())  # feuert mean_reversion
    upsert_market_state(session, TODAY, "vix", 14.0)
    summary = generate_signals(session, TODAY)
    assert summary["signals_created"] >= 1
    assert "earnings_momentum" in summary["inactive_setups"]

    signal = open_signals(session)[0]
    payload = entry_payload(signal)
    assert payload["signal_type"] == "mean_reversion"
    assert payload["stop"] < payload["entry"] < payload["target"]
    assert signal.probability == pytest.approx(0.5)  # keine Historie -> Laplace 0.5
    assert payload["calibration"]["calibrated"] is False
    assert payload["sizing"]["final_pct"] >= 0
    assert len(payload["why"]) >= 3
    assert verify_chain(session)["valid"] is True


def test_generate_signals_dedupes_open_signals(session: Session) -> None:
    _ensure_instrument(session, "TREND", source="watchlist")
    _seed_prices(session, "TREND", _uptrend_with_dip())
    first = generate_signals(session, TODAY)
    second = generate_signals(session, TODAY)
    assert first["signals_created"] >= 1
    assert second["signals_created"] == 0  # dasselbe offene Setup nicht doppelt


def test_signal_probability_uses_own_history(session: Session) -> None:
    prob, calibration = signal_probability(session, "breakout")
    assert prob == pytest.approx(0.5)  # Cold Start
    assert calibration["calibrated"] is False


# ---------------------------------------------------------------- Picker

def _seed_scored_stock(session: Session, ticker: str, sector: str = "Technology") -> None:
    from backend.data.fixtures import FixtureProvider
    from backend.data.pipeline import update_fundamentals

    _ensure_instrument(session, ticker, source="watchlist")
    _seed_prices(session, ticker, [100.0 + i * 0.3 for i in range(300)])
    update_fundamentals(session, FixtureProvider(), [ticker], limit=1)


def test_weekly_picks_written_once_per_week(session: Session) -> None:
    from backend.scoring.engine import compute_scores

    _seed_scored_stock(session, "AAPL")
    _seed_scored_stock(session, "SAP.DE")
    compute_scores(session, TODAY)
    first = run_weekly_picks(session, TODAY, with_ai=False)
    assert first["created"] >= 1
    second = run_weekly_picks(session, TODAY, with_ai=False)
    assert second["created"] == 0 and "existieren" in second["skipped"]

    overview = picks_overview(session)
    assert len(overview["weeks"]) == 1
    week = overview["weeks"][0]
    assert week["n"] == first["created"]
    pick = week["picks"][0]
    assert pick["payload"]["sizing"]["final_pct"] > 0
    assert "Gleichgewichtung" in pick["payload"]["sizing"]["steps"]
    assert pick["payload"]["ai"]["skipped"]  # ohne API-Key ehrlich übersprungen
    assert verify_chain(session)["valid"] is True


def test_picker_refuses_low_scores(session: Session) -> None:
    from backend.scoring.engine import compute_scores

    _ensure_instrument(session, "FALL", source="watchlist")
    _seed_prices(session, "FALL", [400.0 - i * 1.0 for i in range(300)])  # Abwärtstrend
    compute_scores(session, TODAY)
    result = run_weekly_picks(session, TODAY, with_ai=False)
    assert result["created"] == 0
    assert "keine Picks" in result["skipped"]


# ---------------------------------------------------------------- KI-Budget

def test_budget_hard_stop(session: Session) -> None:
    status = budget_status(session)
    assert status["spent_usd"] == 0.0 and not status["exhausted"]
    # Sonnet: 100k Input + 20k Output = 0.3 + 0.3 = 0.60 $
    cost = record_usage(session, "claude-sonnet-5", "test", 100_000, 20_000)
    assert cost == pytest.approx(0.60)
    ensure_budget(session, 0.30)  # 0.60 + 0.30 <= 1.00 -> ok
    with pytest.raises(BudgetExceeded, match="Tagesbudget"):
        ensure_budget(session, 0.50)  # 0.60 + 0.50 > 1.00 -> Hard-Stop


def test_budget_cost_table(session: Session) -> None:
    # Haiku: 1M Input = 1 $, 1M Output = 5 $
    assert record_usage(session, "claude-haiku-4-5", "test", 1_000_000, 0) == pytest.approx(1.0)
    with pytest.raises(ValueError, match="Kein Preis"):
        record_usage(session, "unbekanntes-modell", "test", 1, 1)
