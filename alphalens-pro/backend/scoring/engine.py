"""Scoring-Engine: Composite Score 0–100 aus vier Säulen + Risiko-Score 1–10.

Regeln:
- Point-in-Time: für Stichtag t werden nur Kurse mit date <= t und Fundamentals
  mit as_of <= t verwendet.
- Gewichte kommen aus config/scoring.yaml; fehlende Komponenten werden neutral (50)
  gewertet und ihre Gewichte innerhalb der Säule auf die vorhandenen renormalisiert.
- Jede Komponente wird einzeln persistiert (ScoreRow) — das UI kann den kompletten
  Rechenweg aufklappen (USP 2). Scores sind abgeleitete Daten: Neuberechnung
  ersetzt den Tag (das unveränderliche Ledger für Signale kommt in MS3)."""

from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.models import FundamentalRow, Instrument, PriceBarRow, ScoreRow
from backend.scoring import components as comp
from backend.scoring import indicators as ind
from backend.settings import load_config

log = logging.getLogger(__name__)

PERIODS = {"3m": 63, "6m": 126, "12m": 252}
METRICS = [
    "pe_ttm", "ev_ebitda", "pb", "roe", "net_margin", "debt_to_ebitda",
    "fcf", "market_cap", "revenue_growth", "eps_growth", "beta", "ter",
]


# ---------------------------------------------------------------- Datenzugriff

def _fundamentals_asof(
    session: Session, tickers: list[str], day: date
) -> dict[str, dict[str, float]]:
    """Jüngster Wert je (ticker, metric) mit as_of <= Tagesende — ein Query für alle."""
    cutoff = datetime.combine(day, time.max)
    rows = session.execute(
        select(FundamentalRow.ticker, FundamentalRow.metric, FundamentalRow.value,
               FundamentalRow.as_of)
        .where(FundamentalRow.ticker.in_(tickers), FundamentalRow.as_of <= cutoff,
               FundamentalRow.metric.in_(METRICS))
        .order_by(FundamentalRow.as_of)
    ).all()
    result: dict[str, dict[str, float]] = {}
    for ticker, metric, value, _ in rows:  # letzter gewinnt (aufsteigend sortiert)
        if value is not None:
            result.setdefault(ticker, {})[metric] = float(value)
    return result


def _metric_history(session: Session, ticker: str, metric: str, day: date) -> list[float]:
    cutoff = datetime.combine(day, time.max)
    return [
        float(v)
        for v in session.scalars(
            select(FundamentalRow.value)
            .where(FundamentalRow.ticker == ticker, FundamentalRow.metric == metric,
                   FundamentalRow.as_of <= cutoff)
            .order_by(FundamentalRow.as_of)
        )
        if v is not None
    ]


def _price_series(
    session: Session, ticker: str, day: date, max_bars: int = 800
) -> tuple[list[float], list[float]]:
    rows = list(session.execute(
        select(PriceBarRow.close, PriceBarRow.volume)
        .where(PriceBarRow.ticker == ticker, PriceBarRow.date <= day)
        .order_by(PriceBarRow.date.desc())
        .limit(max_bars)
    ).all())
    rows.reverse()
    closes = [float(c) for c, _ in rows if c is not None]
    volumes = [float(v) if v is not None else 0.0 for c, v in rows if c is not None]
    return closes, volumes


# ---------------------------------------------------------------- Komponenten je Ticker

def _value_components(
    ticker: str, fund: dict[str, float], sector_peers: dict[str, list[float]],
    pe_history: list[float], peer_label: str,
) -> dict[str, comp.ComponentScore]:
    return {
        "pe_vs_sector": comp.score_multiple_vs_peers(
            "pe_vs_sector", fund.get("pe_ttm"), sector_peers.get("pe_ttm", []), peer_label),
        "ev_ebitda_vs_sector": comp.score_multiple_vs_peers(
            "ev_ebitda_vs_sector", fund.get("ev_ebitda"),
            sector_peers.get("ev_ebitda", []), peer_label),
        "pb_vs_sector": comp.score_multiple_vs_peers(
            "pb_vs_sector", fund.get("pb"), sector_peers.get("pb", []), peer_label),
        "pe_vs_own_history": comp.score_vs_own_history(
            "pe_vs_own_history", fund.get("pe_ttm"), pe_history),
    }


def _quality_components(
    fund: dict[str, float], margin_history: list[float]
) -> dict[str, comp.ComponentScore]:
    return {
        "roe": comp.score_roe(fund.get("roe")),
        "roic": comp.score_roic(fund.get("roic")),
        "margin_stability": comp.score_margin_stability(margin_history),
        "leverage": comp.score_leverage(fund.get("debt_to_ebitda")),
        "fcf_conversion": comp.score_fcf_yield(fund.get("fcf"), fund.get("market_cap")),
    }


def _momentum_components(
    closes: list[float], riskadj_peers: dict[str, list[float]]
) -> dict[str, comp.ComponentScore]:
    result: dict[str, comp.ComponentScore] = {}
    for label, bars in PERIODS.items():
        name = f"ret_{label}_riskadj"
        result[name] = comp.score_riskadj_return(
            name, ind.risk_adjusted_return(closes, bars), riskadj_peers.get(label, []))
    result["dist_52w_high"] = comp.score_dist_52w_high(ind.dist_from_high(closes, 252))
    result["ma_signal"] = comp.score_ma_signal(
        closes[-1] if closes else None,
        ind.moving_average(closes, 50), ind.moving_average(closes, 200))
    result["rsi"] = comp.score_rsi(ind.rsi(closes, 14))
    return result


def _growth_components(fund: dict[str, float]) -> dict[str, comp.ComponentScore]:
    return {
        "revenue_growth": comp.score_growth_rate("revenue_growth", fund.get("revenue_growth")),
        "eps_growth": comp.score_growth_rate("eps_growth", fund.get("eps_growth")),
        "revision_trend": comp.not_yet_available("revision_trend", "MS8 (Earnings Center)"),
        "surprise_history": comp.not_yet_available("surprise_history", "MS8 (Earnings Center)"),
    }


def _aggregate_pillar(
    scores: dict[str, comp.ComponentScore], weights: dict[str, float]
) -> tuple[float, bool, dict[str, float]]:
    """Gewichteter Mittelwert über nicht-fehlende Komponenten; Gewichte werden auf
    die vorhandenen renormalisiert. Alle fehlend -> neutral 50 + missing-Flag."""
    available = {n: s for n, s in scores.items() if not s.missing and n in weights}
    if not available:
        return comp.NEUTRAL, True, dict.fromkeys(scores, 0.0)
    total_weight = sum(weights[n] for n in available)
    effective = {n: (weights.get(n, 0.0) / total_weight if n in available else 0.0)
                 for n in scores}
    pillar = sum(scores[n].score * effective[n] for n in available)
    return round(pillar, 1), False, effective


# ---------------------------------------------------------------- Risiko-Score

def _risk_score_stock(
    closes: list[float], volumes: list[float], fund: dict[str, float],
    universe_vols: list[float],
) -> tuple[float, str]:
    """Risiko 1–10 aus dokumentierten absoluten Transformationen (0–100 Risiko-Punkte):
    Vol: 2 Punkte je Prozentpunkt ann. Vol; Drawdown: 2 Punkte je Prozentpunkt;
    Beta: 50 Punkte je Beta-Einheit; Debt/EBITDA: 20 Punkte je x; Liquidität:
    unter 1 Mio Umsatz/Tag -> 100, über 100 Mio -> 0 (logarithmisch)."""
    import math

    cfg = load_config("scoring")["risk_score"]["stock"]
    parts: dict[str, float] = {}
    vol = ind.annualized_volatility(closes, 252)
    if vol is not None:
        if len(universe_vols) >= comp.MIN_PEERS:
            parts["volatility_1y"] = comp.percentile_rank(vol, universe_vols)
        else:
            parts["volatility_1y"] = comp.clip(vol * 200)
    dd = ind.max_drawdown(closes[-756:])
    if dd is not None:
        parts["max_drawdown_3y"] = comp.clip(abs(dd) * 200)
    beta = fund.get("beta")
    if beta is not None:
        parts["beta"] = comp.clip(beta * 50)
    dte = fund.get("debt_to_ebitda")
    if dte is not None and dte >= 0:
        parts["balance_sheet"] = comp.clip(dte * 20)
    adv = ind.avg_dollar_volume(closes, volumes)
    if adv is not None and adv > 0:
        parts["liquidity"] = comp.clip(100 - (math.log10(adv) - 6) * 50)
    if not parts:
        return 5.0, "keine Risikodaten — neutral 5.0"
    total_w = sum(cfg[n] for n in parts)
    raw = sum(parts[n] * cfg[n] for n in parts) / total_w
    score = round(1 + 9 * raw / 100, 1)
    detail = ", ".join(f"{n}={v:.0f}" for n, v in parts.items())
    return score, f"Risikopunkte (0–100): {detail}"


def _risk_score_etf(closes: list[float], fund: dict[str, float]) -> tuple[float, str]:
    cfg = load_config("scoring")["risk_score"]["etf"]
    parts: dict[str, float] = {}
    vol = ind.annualized_volatility(closes, 252)
    if vol is not None:
        parts["volatility_1y"] = comp.clip(vol * 200)
    dd = ind.max_drawdown(closes[-756:])
    if dd is not None:
        parts["max_drawdown_3y"] = comp.clip(abs(dd) * 200)
    ter = fund.get("ter")
    if ter is not None:
        parts["ter"] = comp.clip(ter * 100 * 50)  # TER 2 % -> 100 Risikopunkte
    if not parts:
        return 5.0, "keine Risikodaten — neutral 5.0"
    total_w = sum(cfg[n] for n in parts)
    raw = sum(parts[n] * cfg[n] for n in parts) / total_w
    detail = ", ".join(f"{n}={v:.0f}" for n, v in parts.items())
    note = "Diversifikation folgt mit Holdings-Daten"
    return round(1 + 9 * raw / 100, 1), f"Risikopunkte (0–100): {detail} ({note})"


# ---------------------------------------------------------------- Hauptlauf

def compute_scores(session: Session, day: date | None = None) -> dict[str, Any]:
    """Scores für alle Aktien (Composite + Risiko) und ETFs/Krypto (Risiko) am Stichtag."""
    day = day or date.today()
    cfg = load_config("scoring")["pillars"]
    instruments = list(session.scalars(
        select(Instrument).where(Instrument.asset_type.in_(["stock", "etf", "crypto"]))
    ))
    stocks = [i for i in instruments if i.asset_type == "stock"]
    tickers = [i.ticker for i in instruments]
    fundamentals = _fundamentals_asof(session, tickers, day)
    prices: dict[str, tuple[list[float], list[float]]] = {
        i.ticker: _price_series(session, i.ticker, day) for i in instruments
    }

    # Peer-Gruppen für Bewertungs-Multiples: Sektor, Fallback Gesamtuniversum
    def peer_values(members: list[Instrument], metric: str, exclude: str) -> list[float]:
        return [fundamentals[i.ticker][metric] for i in members
                if i.ticker != exclude and metric in fundamentals.get(i.ticker, {})
                and fundamentals[i.ticker][metric] > 0]

    by_sector: dict[str, list[Instrument]] = {}
    for inst in stocks:
        by_sector.setdefault(inst.sector or "?", []).append(inst)

    # Cross-Sectional-Momentum: risikoadjustierte Renditen aller Aktien je Fenster
    riskadj_all: dict[str, list[float]] = {label: [] for label in PERIODS}
    riskadj_by_ticker: dict[str, dict[str, float]] = {}
    for inst in stocks:
        closes, _ = prices[inst.ticker]
        for label, bars in PERIODS.items():
            value = ind.risk_adjusted_return(closes, bars)
            if value is not None:
                riskadj_all[label].append(value)
                riskadj_by_ticker.setdefault(inst.ticker, {})[label] = value

    universe_vols = [
        v for i in stocks
        if (v := ind.annualized_volatility(prices[i.ticker][0], 252)) is not None
    ]

    session.execute(delete(ScoreRow).where(ScoreRow.date == day))
    scored = 0
    for inst in instruments:
        ticker = inst.ticker
        closes, volumes = prices[ticker]
        fund = fundamentals.get(ticker, {})
        rows: list[ScoreRow] = []

        if inst.asset_type == "stock":
            sector_members = by_sector.get(inst.sector or "?", [])
            if len(sector_members) - 1 >= comp.MIN_PEERS:
                peers_src, peer_label = sector_members, f"Sektor {inst.sector}"
            else:
                peers_src, peer_label = stocks, "Gesamtuniversum"
            sector_peers = {m: peer_values(peers_src, m, ticker)
                            for m in ("pe_ttm", "ev_ebitda", "pb")}
            # Peers für Momentum: alle anderen Aktien
            riskadj_peers = {
                label: [v for t, d in riskadj_by_ticker.items()
                        if t != ticker and label in d for v in [d[label]]]
                for label in PERIODS
            }
            pillar_scores: dict[str, float] = {}
            all_components = {
                "value": _value_components(
                    ticker, fund, sector_peers,
                    _metric_history(session, ticker, "pe_ttm", day), peer_label),
                "quality": _quality_components(
                    fund, _metric_history(session, ticker, "net_margin", day)),
                "momentum": _momentum_components(closes, riskadj_peers),
                "growth": _growth_components(fund),
            }
            for pillar, comps in all_components.items():
                weights = {str(k): float(v) for k, v in cfg[pillar]["components"].items()}
                pillar_score, pillar_missing, effective = _aggregate_pillar(comps, weights)
                pillar_scores[pillar] = pillar_score
                rows.append(ScoreRow(
                    ticker=ticker, date=day, kind="pillar", name=pillar,
                    value=pillar_score, weight=float(cfg[pillar]["weight"]),
                    missing=int(pillar_missing),
                    detail=(
                        f"gewichteter Mittelwert über "
                        f"{sum(1 for c in comps.values() if not c.missing)}"
                        f"/{len(comps)} verfügbare Komponenten")))
                for name, c in comps.items():
                    rows.append(ScoreRow(
                        ticker=ticker, date=day, kind="component",
                        name=f"{pillar}.{name}", value=c.score, raw_value=c.raw_value,
                        weight=round(effective.get(name, 0.0), 4),
                        missing=int(c.missing), detail=c.detail))
            composite = round(sum(
                pillar_scores[p] * float(cfg[p]["weight"]) for p in pillar_scores), 1)
            rows.append(ScoreRow(
                ticker=ticker, date=day, kind="composite", name="composite",
                value=composite,
                detail="Summe der Säulen x Säulengewicht (Gewichte: scoring.yaml)"))
            risk, risk_detail = _risk_score_stock(closes, volumes, fund, universe_vols)
        elif inst.asset_type == "etf":
            risk, risk_detail = _risk_score_etf(closes, fund)
        else:  # crypto: nur Markt-Risiko aus Kursdaten
            risk, risk_detail = _risk_score_etf(closes, {})
        rows.append(ScoreRow(
            ticker=ticker, date=day, kind="risk", name="risk_score",
            value=risk, detail=risk_detail))
        session.add_all(rows)
        scored += 1
    log.info("Scoring %s: %d Instrumente bewertet", day, scored)
    return {"date": day.isoformat(), "instruments_scored": scored}


# ---------------------------------------------------------------- Lesezugriffe (API)

def latest_score_date(session: Session) -> date | None:
    return session.scalar(select(ScoreRow.date).order_by(ScoreRow.date.desc()).limit(1))


def score_breakdown(
    session: Session, ticker: str, day: date | None = None
) -> dict[str, Any] | None:
    day = day or latest_score_date(session)
    if day is None:
        return None
    rows = list(session.scalars(
        select(ScoreRow).where(ScoreRow.ticker == ticker, ScoreRow.date == day)
    ))
    if not rows:
        return None

    def row_dict(r: ScoreRow) -> dict[str, Any]:
        return {"name": r.name, "score": r.value, "raw_value": r.raw_value,
                "weight": r.weight, "missing": bool(r.missing), "detail": r.detail,
                "as_of": r.as_of.isoformat()}

    composite = next((r for r in rows if r.kind == "composite"), None)
    risk = next((r for r in rows if r.kind == "risk"), None)
    pillars = []
    for p in (r for r in rows if r.kind == "pillar"):
        comps = [row_dict(r) for r in rows
                 if r.kind == "component" and r.name.startswith(f"{p.name}.")]
        pillars.append({**row_dict(p), "components": comps})
    return {
        "ticker": ticker, "date": day.isoformat(),
        "composite": composite.value if composite else None,
        "risk_score": risk.value if risk else None,
        "risk_detail": risk.detail if risk else "",
        "pillars": pillars,
    }


def top_scores(session: Session, limit: int = 50, day: date | None = None) -> list[dict[str, Any]]:
    day = day or latest_score_date(session)
    if day is None:
        return []
    rows = list(session.scalars(select(ScoreRow).where(ScoreRow.date == day)))
    by_ticker: dict[str, dict[str, Any]] = {}
    for r in rows:
        entry = by_ticker.setdefault(r.ticker, {"ticker": r.ticker, "date": day.isoformat(),
                                                "pillars": {}})
        if r.kind == "composite":
            entry["composite"] = r.value
        elif r.kind == "risk":
            entry["risk_score"] = r.value
        elif r.kind == "pillar":
            entry["pillars"][r.name] = r.value
    ranked = [e for e in by_ticker.values() if "composite" in e]
    ranked.sort(key=lambda e: e["composite"], reverse=True)
    return ranked[:limit]
