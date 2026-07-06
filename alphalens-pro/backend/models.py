"""ORM-Modelle. Point-in-Time-Disziplin: fachliche Zeitreihen tragen sowohl die
Bezugsperiode (period/date) als auch as_of — wann wir den Wert kannten. Lesende
Zugriffe für Scoring/Backtest filtern grundsätzlich auf as_of <= Stichtag."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base


class Instrument(Base):
    __tablename__ = "instruments"

    ticker: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    exchange: Mapped[str] = mapped_column(String, default="")
    currency: Mapped[str] = mapped_column(String, default="")
    sector: Mapped[str] = mapped_column(String, default="")
    asset_type: Mapped[str] = mapped_column(String, default="stock")  # stock|etf|crypto|index|fx
    region: Mapped[str] = mapped_column(String, default="")
    source: Mapped[str] = mapped_column(String, default="")  # wikipedia|builtin_seed|watchlist|etf
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IndexMembership(Base):
    """Index-Zugehörigkeit mit Gültigkeitszeitraum — Basis für spätere PIT-Universen."""

    __tablename__ = "index_memberships"
    __table_args__ = (UniqueConstraint("index_slug", "ticker", "valid_from"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    index_slug: Mapped[str] = mapped_column(String, index=True)
    ticker: Mapped[str] = mapped_column(String, index=True)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)  # None = aktuell Mitglied


class PriceBarRow(Base):
    __tablename__ = "prices_daily"
    __table_args__ = (
        UniqueConstraint("ticker", "date"),
        Index("ix_prices_ticker_date", "ticker", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String)
    date: Mapped[date] = mapped_column(Date)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    adj_close: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)


class FundamentalRow(Base):
    """Append-only: neue Erkenntnis = neue Zeile mit neuem as_of, nie Überschreiben."""

    __tablename__ = "fundamentals"
    __table_args__ = (
        UniqueConstraint("ticker", "metric", "period", "as_of"),
        Index("ix_fund_ticker_metric_asof", "ticker", "metric", "as_of"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String)
    metric: Mapped[str] = mapped_column(String)
    value: Mapped[float | None] = mapped_column(Float)
    period: Mapped[str] = mapped_column(String, default="ttm")  # z.B. ttm, 2026Q1, fy2025
    as_of: Mapped[datetime] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String, default="yfinance")


class MarketStateRow(Base):
    """Tageszustand des Marktes: VIX, Marktbreite, Index-Trends, EURUSD."""

    __tablename__ = "market_state"
    __table_args__ = (UniqueConstraint("date", "metric"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    metric: Mapped[str] = mapped_column(String)
    value: Mapped[float | None] = mapped_column(Float)
    as_of: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FetchLog(Base):
    """Buchführung pro (ticker, kind): letzter Erfolg/Fehler -> Inkremental-Fetch,
    Stale-Data-Badge und Fehlertoleranz-Auswertung."""

    __tablename__ = "fetch_log"
    __table_args__ = (UniqueConstraint("ticker", "kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)  # prices|fundamentals|news|earnings
    last_success: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error_msg: Mapped[str] = mapped_column(String, default="")
    consecutive_errors: Mapped[int] = mapped_column(Integer, default=0)
