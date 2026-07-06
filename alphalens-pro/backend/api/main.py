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
from backend.models import FetchLog, Instrument, PriceBarRow
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
