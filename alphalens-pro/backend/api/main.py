"""FastAPI-App: Gesundheit, Universum, Instrument-Details.

Jede fachliche Antwort trägt Quelle + as_of — das UI zeigt beides im Tooltip."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from backend.data import store
from backend.db import init_db, session_scope
from backend.models import (
    FetchLog,
    FundamentalRow,
    Instrument,
    MarketStateRow,
    PriceBarRow,
    ScoreRow,
)
from backend.settings import load_config

app = FastAPI(title="AlphaLens Pro", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, Any]:
    schedule_cfg = load_config("schedule")
    stale_hours = int(schedule_cfg.get("stale_data_hours", 30))
    with session_scope() as session:
        instrument_count = session.scalar(select(func.count(Instrument.ticker))) or 0
        bar_count = session.scalar(select(func.count(PriceBarRow.id))) or 0
        last_success = session.scalar(select(func.max(FetchLog.last_success)))
        error_tickers = session.scalar(
            select(func.count(FetchLog.id)).where(FetchLog.consecutive_errors >= 3)
        ) or 0
    stale = last_success is None or (
        datetime.utcnow() - last_success > timedelta(hours=stale_hours)
    )
    return {
        "status": "ok",
        "instruments": instrument_count,
        "price_bars": bar_count,
        "last_fetch_success": last_success.isoformat() if last_success else None,
        "stale": stale,
        "tickers_with_persistent_errors": error_tickers,
        "disclaimer": "Keine Anlageberatung. Analyse- und Paper-Trading-Tool.",
    }


@app.get("/api/universe")
def universe() -> list[dict[str, Any]]:
    with session_scope() as session:
        instruments = session.scalars(select(Instrument).order_by(Instrument.ticker))
        return [
            {
                "ticker": i.ticker, "name": i.name, "currency": i.currency,
                "sector": i.sector, "asset_type": i.asset_type, "region": i.region,
                "source": i.source,
            }
            for i in instruments
        ]


@app.get("/api/instruments/{ticker}")
def instrument_detail(ticker: str) -> dict[str, Any]:
    with session_scope() as session:
        inst = session.get(Instrument, ticker)
        if inst is None:
            raise HTTPException(status_code=404, detail=f"{ticker} nicht im Universum")
        fundamentals = [
            {
                "metric": row.metric, "value": row.value, "period": row.period,
                "as_of": row.as_of.isoformat(), "source": row.source,
            }
            for row in store.latest_fundamentals(session, ticker)
        ]
        return {
            "ticker": inst.ticker, "name": inst.name, "currency": inst.currency,
            "sector": inst.sector, "asset_type": inst.asset_type,
            "fundamentals": fundamentals,
        }


@app.get("/api/instruments/{ticker}/prices")
def instrument_prices(ticker: str, days: int = 365) -> list[dict[str, Any]]:
    start = date.today() - timedelta(days=days)
    with session_scope() as session:
        bars = store.get_price_bars(session, ticker, start=start)
        return [
            {
                "date": b.date.isoformat(), "open": b.open, "high": b.high,
                "low": b.low, "close": b.close, "volume": b.volume,
            }
            for b in bars
        ]


@app.get("/api/instruments/{ticker}/score")
def instrument_score(ticker: str) -> dict[str, Any]:
    """Vollständiger Score-Breakdown fürs "Why?"-Panel: Composite, Säulen,
    jede Komponente mit Rohwert, Gewicht, Missing-Flag und Begründung."""
    from backend.scoring.engine import score_breakdown

    with session_scope() as session:
        breakdown = score_breakdown(session, ticker)
        if breakdown is None:
            raise HTTPException(status_code=404,
                                detail=f"Keine Scores für {ticker} — erst Scoring-Lauf ausführen")
        return breakdown


@app.get("/api/scores")
def scores_ranking(limit: int = 100) -> list[dict[str, Any]]:
    """Composite-Ranking des jüngsten Scoring-Tags inkl. Säulen und Risiko-Score."""
    from backend.scoring.engine import top_scores

    with session_scope() as session:
        return top_scores(session, limit=limit)


@app.post("/api/scores/compute")
def compute_scores_now() -> dict[str, Any]:
    """Scoring manuell anstoßen (normalerweise Teil des täglichen Updates)."""
    from backend.scoring.engine import compute_scores

    with session_scope() as session:
        return compute_scores(session)


@app.get("/api/market/state")
def market_state() -> list[dict[str, Any]]:
    """Jüngster Wert je Marktmetrik (VIX, Breadth, EURUSD, Index-Stände) mit as_of."""
    with session_scope() as session:
        rows = session.scalars(
            select(MarketStateRow).order_by(MarketStateRow.metric, MarketStateRow.date.desc())
        )
        seen: dict[str, MarketStateRow] = {}
        for row in rows:
            seen.setdefault(row.metric, row)
        return [
            {"metric": r.metric, "value": r.value, "date": r.date.isoformat(),
             "as_of": r.as_of.isoformat()}
            for r in seen.values()
        ]


@app.get("/api/screener")
def screener(
    q: str = "", asset_type: str = "", sector: str = "",
    min_score: float | None = None, max_risk: float | None = None,
    max_pe: float | None = None, limit: int = 200,
) -> list[dict[str, Any]]:
    """Filter-Engine auf der lokalen DB: Instrumente + jüngste Scores + Kern-Fundamentals.
    (Der natürlichsprachliche KI-Screener in MS10 übersetzt Freitext in genau
    diese Parameter — und zeigt sie zur Bestätigung an.)"""
    from backend.scoring.engine import latest_score_date

    with session_scope() as session:
        instruments = list(session.scalars(select(Instrument).order_by(Instrument.ticker)))
        day = latest_score_date(session)
        scores: dict[str, dict[str, float]] = {}
        if day is not None:
            for r in session.scalars(select(ScoreRow).where(
                    ScoreRow.date == day,
                    ScoreRow.kind.in_(["composite", "risk", "pillar"]))):
                entry = scores.setdefault(r.ticker, {})
                key = "composite" if r.kind == "composite" else (
                    "risk" if r.kind == "risk" else r.name)
                entry[key] = r.value
        pe_by_ticker: dict[str, float] = {}
        for row in session.scalars(select(FundamentalRow).where(
                FundamentalRow.metric == "pe_ttm").order_by(FundamentalRow.as_of)):
            if row.value is not None:
                pe_by_ticker[row.ticker] = float(row.value)

        results: list[dict[str, Any]] = []
        needle = q.strip().lower()
        for inst in instruments:
            if inst.source == "market_symbol":
                continue
            if needle and needle not in inst.ticker.lower() and needle not in inst.name.lower():
                continue
            if asset_type and inst.asset_type != asset_type:
                continue
            if sector and inst.sector != sector:
                continue
            s = scores.get(inst.ticker, {})
            pe = pe_by_ticker.get(inst.ticker)
            if min_score is not None and s.get("composite", -1) < min_score:
                continue
            if max_risk is not None and s.get("risk", 11) > max_risk:
                continue
            if max_pe is not None and (pe is None or pe > max_pe):
                continue
            results.append({
                "ticker": inst.ticker, "name": inst.name, "sector": inst.sector,
                "asset_type": inst.asset_type, "currency": inst.currency,
                "composite": s.get("composite"), "risk_score": s.get("risk"),
                "value": s.get("value"), "quality": s.get("quality"),
                "momentum": s.get("momentum"), "growth": s.get("growth"),
                "pe_ttm": pe, "score_date": day.isoformat() if day else None,
            })
        results.sort(key=lambda r: (r["composite"] is None, -(r["composite"] or 0)))
        return results[:limit]
