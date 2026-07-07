"""Regime-Gate (USP 4): In Risk-off-Phasen werden Long-Signale gedrosselt,
nicht versteckt. Drei Kriterien, 2-von-3-Regel, jede Bewertung mit Begründung.

Ehrlichkeit bei Datenlücken: nicht bewertbare Kriterien zählen NICHT als
gerissen, werden aber ausgewiesen (data_complete=False) — kein stilles Raten."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import MarketStateRow, PriceBarRow
from backend.scoring.components import percentile_rank
from backend.scoring.indicators import moving_average
from backend.settings import load_config


def _latest_metric(session: Session, metric: str) -> float | None:
    row = session.scalar(
        select(MarketStateRow)
        .where(MarketStateRow.metric == metric)
        .order_by(MarketStateRow.date.desc())
        .limit(1)
    )
    return float(row.value) if row is not None and row.value is not None else None


def _closes(session: Session, ticker: str, day: date, limit: int = 300) -> list[float]:
    rows = list(session.scalars(
        select(PriceBarRow.close)
        .where(PriceBarRow.ticker == ticker, PriceBarRow.date <= day)
        .order_by(PriceBarRow.date.desc())
        .limit(limit)
    ))
    rows.reverse()
    return [float(c) for c in rows if c is not None]


def current_regime(session: Session, day: date | None = None) -> dict[str, Any]:
    day = day or date.today()
    cfg = load_config("signals")["regime_gate"]
    criteria: list[dict[str, Any]] = []

    # 1. VIX: Niveau ODER 1-Jahres-Perzentil
    vix = _latest_metric(session, "vix")
    vix_closes = _closes(session, "^VIX", day, limit=252)
    if vix is None and vix_closes:
        vix = vix_closes[-1]
    if vix is not None:
        pct = percentile_rank(vix, vix_closes) / 100 if len(vix_closes) >= 60 else None
        breach = vix > float(cfg["vix_level"]) or (
            pct is not None and pct > float(cfg["vix_percentile_1y"]))
        detail = f"VIX {vix:.1f} (Schwelle {cfg['vix_level']}"
        detail += (f", Perzentil 1J {pct:.0%})" if pct is not None
                   else ", Perzentil: zu wenig Historie)")
        criteria.append({"name": "vix", "breach": breach, "evaluable": True, "detail": detail})
    else:
        criteria.append({"name": "vix", "breach": False, "evaluable": False,
                         "detail": "keine VIX-Daten (make update lädt ^VIX)"})

    # 2. Marktbreite
    breadth = _latest_metric(session, "breadth_pct_above_ma200")
    if breadth is not None:
        threshold = float(cfg["breadth_min_pct_above_ma200"])
        criteria.append({
            "name": "breadth", "breach": breadth < threshold, "evaluable": True,
            "detail": f"{breadth:.0f} % der Aktien über MA200 (Schwelle {threshold:.0f} %)",
        })
    else:
        criteria.append({"name": "breadth", "breach": False, "evaluable": False,
                         "detail": "keine Marktbreite-Daten (braucht 200 Tage Kurshistorie)"})

    # 3. Leitindex-Trend (S&P 500; EuroStoxx informativ im Detail)
    spx = _closes(session, "^GSPC", day)
    ma200 = moving_average(spx, 200)
    if spx and ma200 is not None:
        breach = spx[-1] < ma200
        stoxx = _closes(session, "^STOXX50E", day)
        stoxx_ma = moving_average(stoxx, 200)
        stoxx_note = ""
        if stoxx and stoxx_ma is not None:
            stoxx_note = (f"; EuroStoxx {'unter' if stoxx[-1] < stoxx_ma else 'über'} MA200"
                          f" (informativ)")
        criteria.append({
            "name": "index_trend", "breach": breach, "evaluable": True,
            "detail": f"S&P 500 {spx[-1]:.0f} {'unter' if breach else 'über'} "
                      f"MA200 {ma200:.0f}{stoxx_note}",
        })
    else:
        criteria.append({"name": "index_trend", "breach": False, "evaluable": False,
                         "detail": "keine S&P-500-Kurshistorie (make update lädt ^GSPC)"})

    breaches = sum(1 for c in criteria if c["breach"])
    evaluable = sum(1 for c in criteria if c["evaluable"])
    if breaches >= 2:
        regime = "risk_off"
    elif breaches == 1:
        regime = "neutral"
    else:
        regime = "risk_on"
    factor = float(cfg["scaling"][regime])
    return {
        "date": day.isoformat(),
        "regime": regime,
        "factor": factor,
        "breaches": breaches,
        "criteria": criteria,
        "data_complete": evaluable == len(criteria),
    }
