"""Backtest-Engine: Golden-Value-Metriken, Kostenwirkung, Anti-Lookahead-Invarianz,
deterministische Mini-Backtests mit bekanntem Ergebnis."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.backtest import metrics
from backend.backtest.engine import (
    _rebalance_days,
    get_report,
    list_reports,
    run_score_ranking,
    run_signal_setup,
    save_report,
)
from backend.data.providers.base import PriceBar
from backend.data.store import upsert_price_bars
from backend.data.universe import _ensure_instrument
from backend.models import PriceBarRow, ScoreRow

START = date(2026, 1, 5)  # ein Montag


# ---------------------------------------------------------------- Metriken

def test_cagr_known_values() -> None:
    equity_double_in_year = [1.0] + [0.0] * 0
    equity = [1.0 * (2 ** (i / 252)) for i in range(253)]  # exakt Verdopplung in 252 Renditen
    assert metrics.cagr(equity) == pytest.approx(1.0, rel=1e-9)
    assert metrics.cagr([1.0]) is None
    assert metrics.cagr(equity_double_in_year) is None


def test_sharpe_and_sortino_known_values() -> None:
    flat = [0.0] * 100
    assert metrics.sharpe(flat) is None  # Varianz 0 -> nicht definiert
    zero_mean = [0.01, -0.01] * 50
    assert metrics.sharpe(zero_mean) == pytest.approx(0.0, abs=1e-9)
    rets = [0.02, -0.01]
    expected_sortino = 0.005 / math.sqrt((0.01 ** 2) / 2) * math.sqrt(252)
    assert metrics.sortino(rets) == pytest.approx(expected_sortino)
    only_gains = [0.01] * 10
    assert metrics.sortino(only_gains) is None  # keine Abwärtsvolatilität


def test_max_drawdown_and_hit_rate() -> None:
    assert metrics.max_drawdown([100.0, 120.0, 60.0, 90.0]) == pytest.approx(-0.5)
    assert metrics.hit_rate([0.05, -0.02, 0.01]) == pytest.approx(2 / 3)
    assert metrics.hit_rate([]) is None


def test_annual_turnover_known_value() -> None:
    # 200k gehandelt bei 100k Durchschnittskapital über 1 Jahr -> 2.0
    assert metrics.annual_turnover(200_000, 100_000, 252) == pytest.approx(2.0, rel=0.01)


def test_block_bootstrap_deterministic_and_sane() -> None:
    rets = [0.001 * ((i % 7) - 3) for i in range(200)]  # strukturierte Serie
    ci1 = metrics.block_bootstrap_ci(rets, metrics.sharpe, seed=42)
    ci2 = metrics.block_bootstrap_ci(rets, metrics.sharpe, seed=42)
    assert ci1 == ci2  # deterministisch
    assert ci1 is not None and ci1[0] <= ci1[1]
    assert metrics.block_bootstrap_ci([0.01] * 10, metrics.sharpe) is None  # zu kurz


def test_summarize_includes_cis() -> None:
    equity = [100.0 * (1 + 0.0005) ** i * (1 + 0.002 * ((i % 5) - 2)) for i in range(300)]
    summary = metrics.summarize_equity(equity)
    assert summary["cagr"] is not None
    assert summary["cagr_ci95"] is not None
    assert summary["cagr_ci95"][0] <= summary["cagr_ci95"][1]
    assert summary["sharpe_ci95"] is not None


def test_rebalance_days_first_trading_day_per_month() -> None:
    days = [date(2026, 1, 5) + timedelta(days=i) for i in range(70)]
    days = [d for d in days if d.weekday() < 5]
    marks = _rebalance_days(days, "monthly")
    assert date(2026, 1, 5) in marks
    assert date(2026, 2, 2) in marks   # erster Handelstag Februar
    assert date(2026, 3, 2) in marks
    assert len(marks) == 3


# ---------------------------------------------------------------- Helpers

def _seed_stock(session: Session, ticker: str, closes: list[float],
                currency: str = "EUR") -> list[date]:
    _ensure_instrument(session, ticker, currency=currency, source="watchlist")
    days: list[date] = []
    day = START
    i = 0
    while i < len(closes):
        if day.weekday() < 5:
            c = closes[i]
            upsert_price_bars(session, [PriceBar(
                ticker=ticker, date=day, open=c, high=c + 0.5, low=c - 0.5,
                close=c, adj_close=c, volume=1_000_000.0)])
            days.append(day)
            i += 1
        day += timedelta(days=1)
    return days


def _seed_composites(session: Session, days: list[date], scores: dict[str, float]) -> None:
    for d in days:
        for ticker, value in scores.items():
            session.add(ScoreRow(ticker=ticker, date=d, kind="composite",
                                 name="composite", value=value))
    session.flush()


# ---------------------------------------------------------------- Score-Ranking

def test_score_ranking_picks_winner_and_prices_execution_next_day(session: Session) -> None:
    n = 130
    up = [100.0 * 1.01 ** i for i in range(n)]
    down = [100.0 * 0.99 ** i for i in range(n)]
    days = _seed_stock(session, "GEWINNER", up)
    _seed_stock(session, "VERLIERER", down)
    _seed_composites(session, days, {"GEWINNER": 90.0, "VERLIERER": 10.0})

    result = run_score_ranking(
        session, start=days[0], end=days[-1], top_n=1, rebalance="monthly",
        cost_bps_per_side=0.0, fee_eur=0.0, initial_capital=100_000.0)
    m = result["metrics"]
    assert m["total_return_pct"] is not None and m["total_return_pct"] > 100
    assert len(result["equity"]) == len(days)
    # Tag 1: Entscheidung, noch nicht investiert -> Equity unverändert (kein Lookahead)
    assert result["equity"][0][1] == pytest.approx(100_000.0)
    assert result["caveats"]  # Pflicht-Panel
    assert any("Survivorship" in c for c in result["caveats"])


def test_score_ranking_costs_reduce_equity(session: Session) -> None:
    n = 80
    up = [100.0 * 1.005 ** i for i in range(n)]
    days = _seed_stock(session, "GEWINNER", up)
    _seed_composites(session, days, {"GEWINNER": 90.0})

    free = run_score_ranking(session, start=days[0], end=days[-1], top_n=1,
                             cost_bps_per_side=0.0, fee_eur=0.0)
    costly = run_score_ranking(session, start=days[0], end=days[-1], top_n=1,
                               cost_bps_per_side=100.0, fee_eur=0.0)
    assert costly["metrics"]["total_costs_eur"] > 900  # ~1 % vom investierten Kapital
    assert costly["equity"][-1][1] < free["equity"][-1][1]


def test_score_ranking_no_lookahead_future_data_invariance(session: Session) -> None:
    """DER Ehrlichkeitstest: Zukunftsdaten in der DB dürfen das Ergebnis bis zum
    Stichtag nicht verändern — sonst leakt die Engine."""
    n = 100
    up = [100.0 * 1.004 ** i for i in range(n + 30)]
    all_days = _seed_stock(session, "GEWINNER", up)
    _seed_stock(session, "VERLIERER", [100.0] * (n + 30))
    _seed_composites(session, all_days, {"GEWINNER": 90.0, "VERLIERER": 10.0})
    cutoff = all_days[n - 1]

    with_future = run_score_ranking(session, start=all_days[0], end=cutoff, top_n=1,
                                    cost_bps_per_side=0.0, fee_eur=0.0)
    # Zukunft entfernen und identisch rechnen
    session.execute(delete(PriceBarRow).where(PriceBarRow.date > cutoff))
    session.execute(delete(ScoreRow).where(ScoreRow.date > cutoff))
    without_future = run_score_ranking(session, start=all_days[0], end=cutoff, top_n=1,
                                       cost_bps_per_side=0.0, fee_eur=0.0)
    assert with_future["equity"] == without_future["equity"]


def test_score_ranking_rejects_too_short_period(session: Session) -> None:
    days = _seed_stock(session, "KURZ", [100.0] * 10)
    with pytest.raises(ValueError, match="Handelstage"):
        run_score_ranking(session, start=days[0], end=days[-1])


# ---------------------------------------------------------------- Signal-Setup

def test_signal_setup_breakout_trade_with_known_outcome(session: Session) -> None:
    # Stetiger Aufwärtstrend; Volumenspitze in der Mitte erzeugt genau dort einen
    # Breakout (Schluss = Laufzeithoch). Ziel wird im Trend erreicht.
    n = 320
    closes = [100.0 + 0.4 * i for i in range(n)]
    _ensure_instrument(session, "BREAK", currency="EUR", source="watchlist")
    days: list[date] = []
    day = START
    i = 0
    while i < len(closes):
        if day.weekday() < 5:
            c = closes[i]
            volume = 2_000_000.0 if i == 260 else 1_000_000.0
            upsert_price_bars(session, [PriceBar(
                ticker="BREAK", date=day, open=c, high=c + 0.5, low=c - 0.5,
                close=c, adj_close=c, volume=volume)])
            days.append(day)
            i += 1
        day += timedelta(days=1)

    result = run_signal_setup(session, signal_type="breakout", start=days[0],
                              end=days[-1], cost_bps_per_side=0.0, n_folds=2)
    m = result["metrics"]
    assert m["n_trades"] == 1
    trade = result["trades"][0]
    assert trade["result"] == "target_hit"
    assert trade["return_pct"] > 0
    assert result["walk_forward"] is not None
    assert any("liquidesten" in c for c in result["caveats"])


def test_signal_setup_unknown_type_rejected(session: Session) -> None:
    with pytest.raises(ValueError, match="nicht aktiv"):
        run_signal_setup(session, signal_type="earnings_momentum",
                         start=START, end=START + timedelta(days=300))


# ---------------------------------------------------------------- Reports

def test_report_roundtrip(session: Session) -> None:
    n = 80
    days = _seed_stock(session, "GEWINNER", [100.0 * 1.005 ** i for i in range(n)])
    _seed_composites(session, days, {"GEWINNER": 90.0})
    result = run_score_ranking(session, start=days[0], end=days[-1], top_n=1)
    report_id = save_report(session, "Testlauf", result)

    listed = list_reports(session)
    assert any(r["id"] == report_id and r["name"] == "Testlauf" for r in listed)
    loaded = get_report(session, report_id)
    assert loaded is not None
    assert loaded["strategy"] == "score_ranking"
    assert loaded["metrics"] == result["metrics"]
    assert loaded["caveats"] == result["caveats"]
    assert get_report(session, 99_999) is None
