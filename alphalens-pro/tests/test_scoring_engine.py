"""Engine-Tests: Säulen-Aggregation mit Renormalisierung, Composite-Gewichtung,
Persistenz mit vollständigem Breakdown, PIT-Verhalten, ETF-Risiko."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.data import store
from backend.data.fixtures import FixtureProvider
from backend.data.pipeline import update_fundamentals, update_prices
from backend.data.universe import _ensure_instrument
from backend.models import Instrument, ScoreRow
from backend.scoring.components import ComponentScore
from backend.scoring.engine import (
    _aggregate_pillar,
    compute_scores,
    score_breakdown,
    top_scores,
)


def _cs(name: str, score: float, missing: bool = False) -> ComponentScore:
    return ComponentScore(name=name, score=score, raw_value=score, missing=missing, detail="t")


def test_aggregate_pillar_renormalizes_missing_weights() -> None:
    scores = {"a": _cs("a", 80.0), "b": _cs("b", 40.0), "c": _cs("c", 0.0, missing=True)}
    weights = {"a": 0.5, "b": 0.25, "c": 0.25}
    # c fehlt -> Gewichte a:0.5/0.75, b:0.25/0.75 -> 80*2/3 + 40*1/3 = 66.7
    pillar, missing, effective = _aggregate_pillar(scores, weights)
    assert pillar == 66.7
    assert not missing
    assert effective["a"] == round(2 / 3, 4) or abs(effective["a"] - 2 / 3) < 1e-9
    assert effective["c"] == 0.0


def test_aggregate_pillar_all_missing_is_neutral_and_flagged() -> None:
    scores = {"a": _cs("a", 0.0, True), "b": _cs("b", 0.0, True)}
    pillar, missing, _ = _aggregate_pillar(scores, {"a": 0.5, "b": 0.5})
    assert pillar == 50.0
    assert missing


def _seed_db(session: Session) -> None:
    """Fixture-Universum mit Kursen + Fundamentals befüllen."""
    for ticker in ("AAPL", "SAP.DE", "VWCE.DE"):
        _ensure_instrument(session, ticker, source="watchlist")
    provider = FixtureProvider()
    update_prices(session, provider, ["AAPL", "SAP.DE", "VWCE.DE"])
    update_fundamentals(session, provider, ["AAPL", "SAP.DE", "VWCE.DE"], limit=3)


def test_compute_scores_persists_full_breakdown(session: Session) -> None:
    _seed_db(session)
    summary = compute_scores(session, date.today())
    assert summary["instruments_scored"] == 3

    breakdown = score_breakdown(session, "AAPL")
    assert breakdown is not None
    assert breakdown["composite"] is not None
    assert 0 <= breakdown["composite"] <= 100
    assert 1 <= breakdown["risk_score"] <= 10
    assert len(breakdown["pillars"]) == 4
    # Jede Säule hat alle konfigurierten Komponenten, inkl. ehrlicher Missing-Flags
    growth = next(p for p in breakdown["pillars"] if p["name"] == "growth")
    revision = next(c for c in growth["components"] if c["name"].endswith("revision_trend"))
    assert revision["missing"] is True
    assert "MS8" in revision["detail"]
    # Momentum ist aus echten (Fixture-)Kursen berechnet, nicht neutral
    momentum = next(p for p in breakdown["pillars"] if p["name"] == "momentum")
    assert any(not c["missing"] for c in momentum["components"])


def test_etf_gets_risk_score_but_no_composite(session: Session) -> None:
    _seed_db(session)
    vwce = session.get(Instrument, "VWCE.DE")
    assert vwce is not None and vwce.asset_type == "etf"
    compute_scores(session, date.today())
    breakdown = score_breakdown(session, "VWCE.DE")
    assert breakdown is not None
    assert breakdown["composite"] is None
    assert 1 <= breakdown["risk_score"] <= 10
    assert "ter" in breakdown["risk_detail"]


def test_recompute_is_idempotent(session: Session) -> None:
    _seed_db(session)
    compute_scores(session, date.today())
    count_first = len(list(session.scalars(select(ScoreRow))))
    compute_scores(session, date.today())
    count_second = len(list(session.scalars(select(ScoreRow))))
    assert count_first == count_second


def test_top_scores_ranked_descending(session: Session) -> None:
    _seed_db(session)
    compute_scores(session, date.today())
    ranking = top_scores(session, limit=10)
    assert len(ranking) == 2  # nur Aktien haben Composite (AAPL, SAP.DE)
    assert ranking[0]["composite"] >= ranking[1]["composite"]
    assert "pillars" in ranking[0] and "risk_score" in ranking[0]


def test_scoring_respects_asof_no_future_fundamentals(session: Session) -> None:
    """PIT-Check: Fundamentals mit as_of nach dem Stichtag dürfen nicht einfließen."""
    _seed_db(session)
    past_day = date(2024, 1, 15)  # vor allen Fixture-as_of-Zeitpunkten (heute)
    compute_scores(session, past_day)
    breakdown = score_breakdown(session, "AAPL", past_day)
    assert breakdown is not None
    quality = next(p for p in breakdown["pillars"] if p["name"] == "quality")
    roe = next(c for c in quality["components"] if c["name"].endswith(".roe"))
    assert roe["missing"] is True  # ROE war am Stichtag noch nicht bekannt


def test_scoring_survives_ticker_without_data(session: Session) -> None:
    _seed_db(session)
    _ensure_instrument(session, "LEER", source="watchlist")  # keine Kurse, keine Fundamentals
    summary = compute_scores(session, date.today())
    assert summary["instruments_scored"] == 4  # kein Crash
    breakdown = score_breakdown(session, "LEER")
    assert breakdown is not None
    assert breakdown["risk_score"] == 5.0  # neutral, ehrlich ausgewiesen


def test_fetch_log_untouched_by_scoring(session: Session) -> None:
    """Scoring ist reine Ableitung — es darf keine Fetch-Buchführung anfassen."""
    _seed_db(session)
    before = store.is_stale(session, "AAPL", "prices", max_age_hours=1)
    compute_scores(session, date.today())
    assert store.is_stale(session, "AAPL", "prices", max_age_hours=1) == before


def test_component_rows_carry_asof_timestamp(session: Session) -> None:
    _seed_db(session)
    compute_scores(session, date.today())
    row = session.scalar(select(ScoreRow).where(ScoreRow.kind == "component").limit(1))
    assert row is not None
    assert isinstance(row.as_of, datetime)
