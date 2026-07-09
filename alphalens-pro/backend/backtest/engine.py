"""Backtest-Engine (USP 1): Point-in-Time, ehrliche Kosten, kein Lookahead.

Grundregeln:
- Entscheidungen am Tag t nutzen ausschließlich Daten mit date/as_of <= t.
- Ausgeführt wird am NÄCHSTEN Handelstag zum Schlusskurs — die Entscheidung
  kann ihren eigenen Ausführungskurs nicht sehen.
- Kosten je Seite (halber Spread + Slippage) plus Ordergebühr, aus costs.yaml.
- EUR-Basis: USD-Kurse werden mit dem EURUSD-Stand des Tages umgerechnet;
  fehlen FX-Daten, wird das als Caveat ausgewiesen statt still ignoriert.
- Jeder Report trägt ein verpflichtendes Caveats-Panel und Overfitting-Warnungen."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.backtest import metrics
from backend.models import BacktestReportRow, FundamentalRow, Instrument, PriceBarRow, ScoreRow
from backend.settings import load_config

log = logging.getLogger(__name__)

EPS_TRADE_EUR = 1.0  # Umschichtungen unter 1 EUR werden ignoriert (keine Mikro-Orders)


# ---------------------------------------------------------------- Marktdaten

def load_ohlc(
    session: Session, tickers: list[str], start: date, end: date
) -> dict[str, list[tuple[date, float, float, float, float]]]:
    """Je Ticker chronologische Liste (date, close, high, low, volume).
    Nutzt adj_close falls vorhanden (Dividenden), sonst close."""
    result: dict[str, list[tuple[date, float, float, float, float]]] = {}
    rows = session.execute(
        select(PriceBarRow)
        .where(PriceBarRow.ticker.in_(tickers),
               PriceBarRow.date >= start, PriceBarRow.date <= end)
        .order_by(PriceBarRow.ticker, PriceBarRow.date)
    ).scalars()
    for bar in rows:
        px = bar.adj_close if bar.adj_close is not None else bar.close
        if px is None:
            continue
        result.setdefault(bar.ticker, []).append((
            bar.date, float(px),
            float(bar.high if bar.high is not None else px),
            float(bar.low if bar.low is not None else px),
            float(bar.volume if bar.volume is not None else 0.0),
        ))
    return result


def trading_days(ohlc: dict[str, list[tuple[date, float, float, float, float]]]) -> list[date]:
    days = {row[0] for series in ohlc.values() for row in series}
    return sorted(days)


def fx_usd_to_eur(session: Session, start: date, end: date) -> dict[date, float]:
    """EURUSD=X-Schlusskurse (USD je EUR). Leeres Dict = keine FX-Daten."""
    rows = session.execute(
        select(PriceBarRow.date, PriceBarRow.close)
        .where(PriceBarRow.ticker == "EURUSD=X",
               PriceBarRow.date >= start, PriceBarRow.date <= end)
        .order_by(PriceBarRow.date)
    ).all()
    return {d: float(c) for d, c in rows if c is not None and c > 0}


class FxConverter:
    """USD->EUR mit Forward-Fill; ohne Daten Faktor 1.0 (wird als Caveat gemeldet)."""

    def __init__(self, rates: dict[date, float]) -> None:
        self._rates = rates
        self._sorted = sorted(rates)
        self.available = bool(rates)
        self._last: float | None = None

    def to_eur(self, price: float, currency: str, day: date) -> float:
        if currency != "USD" or not self.available:
            return price
        if day in self._rates:
            self._last = self._rates[day]
        elif self._last is None:
            earlier = [d for d in self._sorted if d <= day]
            self._last = self._rates[earlier[-1]] if earlier else self._rates[self._sorted[0]]
        return price / self._last


# ---------------------------------------------------------------- Kosten & Ehrlichkeit

def default_cost_bps_per_side() -> float:
    cfg = load_config("costs")
    return round(float(cfg["spread_bps"]["eu_large_cap"]) / 2 + float(cfg["slippage_bps"]), 1)


def build_caveats(
    session: Session, start: date, end: date, *,
    fx_available: bool, cost_bps: float, fee_eur: float, extra: list[str],
) -> list[str]:
    """Das verpflichtende Data-Caveats-Panel: welche Verzerrungen stecken im Ergebnis."""
    caveats = [
        "Universum = heutige Indexmitglieder — Survivorship-Bias für Zeiträume vor "
        "Beginn der eigenen Datensammlung (Pleite-/Absteiger-Titel fehlen historisch).",
        f"Kosten modelliert: {cost_bps} bp je Seite (halber Spread + Slippage) + "
        f"{fee_eur:.2f} € je Order. Reale Kosten können abweichen.",
        "Risikofreier Zins in Sharpe/Sortino = 0.",
        "Jeder zusätzlich getestete Parametersatz erhöht die Wahrscheinlichkeit zufällig "
        "guter Ergebnisse (Multiple Testing) — Playground-Läufe sind Hypothesen, "
        "keine Beweise.",
    ]
    earliest = session.scalar(
        select(FundamentalRow.as_of).order_by(FundamentalRow.as_of).limit(1)
    )
    if earliest is None or earliest.date() > start:
        since = earliest.date().isoformat() if earliest else "—"
        caveats.append(
            f"Fundamentaldaten liegen erst ab {since} point-in-time vor — Scores vor "
            "diesem Datum sind primär preisgetrieben (Fundamental-Komponenten neutral)."
        )
    if not fx_available:
        caveats.append(
            "Keine EURUSD-Daten im Zeitraum — USD-Positionen NICHT in EUR umgerechnet "
            "(Währungseffekt fehlt im Ergebnis)."
        )
    caveats.extend(extra)
    return caveats


def overfitting_warnings(param_count: int, n_days: int, n_trades: int | None) -> list[str]:
    warnings: list[str] = []
    if n_days < 252:
        warnings.append(f"Zeitraum nur {n_days} Handelstage (< 1 Jahr) — Kennzahlen "
                        "statistisch schwach.")
    n_eff = max(1, n_days // 20)  # unabhängige 20-Tage-Blöcke
    if param_count * 10 > n_eff:
        warnings.append(
            f"{param_count} freie Parameter bei nur ~{n_eff} unabhängigen Blöcken — "
            "Overfitting-Verdacht: Ergebnis kann Anpassung ans Rauschen sein.")
    if n_trades is not None and n_trades < 30:
        warnings.append(f"Nur {n_trades} Trades — Hit-Rate und Ø-Rendite haben breite "
                        "Unsicherheit (siehe Konfidenzintervalle).")
    return warnings


# ---------------------------------------------------------------- Score-Ranking-Strategie

def _rebalance_days(days: list[date], frequency: str) -> set[date]:
    marks: set[date] = set()
    last_key = None
    for d in days:
        if frequency == "weekly":
            key = (d.isocalendar().year, d.isocalendar().week)
        elif frequency == "quarterly":
            key = (d.year, (d.month - 1) // 3)
        else:  # monthly
            key = (d.year, d.month)
        if key != last_key:
            marks.add(d)
            last_key = key
    return marks


def _ensure_scores(session: Session, day: date) -> None:
    exists = session.scalar(
        select(ScoreRow.id).where(ScoreRow.date == day, ScoreRow.kind == "composite").limit(1)
    )
    if exists is None:
        from backend.scoring.engine import compute_scores

        compute_scores(session, day)


def _top_composite(session: Session, day: date, top_n: int) -> list[str]:
    from backend.scoring.engine import top_scores

    return [str(r["ticker"]) for r in top_scores(session, limit=top_n, day=day)]


def run_score_ranking(
    session: Session, *, start: date, end: date, top_n: int = 10,
    rebalance: str = "monthly", cost_bps_per_side: float | None = None,
    fee_eur: float | None = None, initial_capital: float = 100_000.0,
) -> dict[str, Any]:
    """Portfolio aus den Top-N nach Composite Score, gleichgewichtet.
    Entscheidung am Rebalance-Tag t (Scores PIT für t), Ausführung am Tag t+1."""
    costs_cfg = load_config("costs")
    cost_bps = cost_bps_per_side if cost_bps_per_side is not None else default_cost_bps_per_side()
    fee = fee_eur if fee_eur is not None else float(costs_cfg["fees"]["per_trade_eur"])

    stocks = list(session.scalars(select(Instrument).where(Instrument.asset_type == "stock")))
    currency = {i.ticker: (i.currency or "EUR") for i in stocks}
    ohlc = load_ohlc(session, [i.ticker for i in stocks], start, end)
    days = trading_days(ohlc)
    if len(days) < 30:
        raise ValueError(f"Nur {len(days)} Handelstage mit Kursen im Zeitraum — zu wenig")
    fx = FxConverter(fx_usd_to_eur(session, start, end))
    rebalance_marks = _rebalance_days(days, rebalance)

    px_by_day: dict[str, dict[date, float]] = {
        t: {row[0]: row[1] for row in series} for t, series in ohlc.items()
    }
    last_px: dict[str, float] = {}

    def price_eur(ticker: str, day: date) -> float | None:
        px = px_by_day.get(ticker, {}).get(day)
        if px is not None:
            last_px[ticker] = px
        px = px if px is not None else last_px.get(ticker)
        if px is None:
            return None
        return fx.to_eur(px, currency.get(ticker, "EUR"), day)

    cash = initial_capital
    shares: dict[str, float] = {}
    cost_basis: dict[str, float] = {}
    trade_returns: list[float] = []
    traded_notional = 0.0
    total_costs = 0.0
    pending_targets: list[str] | None = None
    equity_curve: list[tuple[date, float]] = []

    for day in days:
        # 1. Ausführung der GESTERN entschiedenen Ziel-Positionen (kein Lookahead)
        if pending_targets is not None:
            targets = [t for t in pending_targets if price_eur(t, day) is not None]
            equity_now = cash + sum(
                s * (price_eur(t, day) or 0.0) for t, s in shares.items()
            )
            target_value = equity_now / len(targets) if targets else 0.0
            for ticker in [t for t in list(shares) if t not in targets]:
                px = price_eur(ticker, day)
                if px is None:
                    continue
                proceeds = shares[ticker] * px
                cost = proceeds * cost_bps / 10_000 + fee
                cash += proceeds - cost
                total_costs += cost
                traded_notional += proceeds
                if cost_basis.get(ticker, 0) > 0:
                    trade_returns.append(proceeds / cost_basis[ticker] - 1.0)
                shares.pop(ticker)
                cost_basis.pop(ticker, None)
            for ticker in targets:
                px = price_eur(ticker, day)
                if px is None or px <= 0:
                    continue
                current_value = shares.get(ticker, 0.0) * px
                delta = target_value - current_value
                if abs(delta) < EPS_TRADE_EUR:
                    continue
                cost = abs(delta) * cost_bps / 10_000 + fee
                cash -= delta + cost
                total_costs += cost
                traded_notional += abs(delta)
                new_shares = shares.get(ticker, 0.0) + delta / px
                if delta > 0:
                    cost_basis[ticker] = cost_basis.get(ticker, 0.0) + delta
                else:
                    frac_sold = -delta / current_value if current_value > 0 else 0.0
                    cost_basis[ticker] = cost_basis.get(ticker, 0.0) * (1 - frac_sold)
                if new_shares <= 1e-9:
                    shares.pop(ticker, None)
                    cost_basis.pop(ticker, None)
                else:
                    shares[ticker] = new_shares
            pending_targets = None

        # 2. Entscheidung am Rebalance-Tag: Scores point-in-time für HEUTE
        if day in rebalance_marks:
            _ensure_scores(session, day)
            pending_targets = _top_composite(session, day, top_n)

        equity = cash + sum(s * (price_eur(t, day) or 0.0) for t, s in shares.items())
        equity_curve.append((day, round(equity, 2)))

    values = [v for _, v in equity_curve]
    summary = metrics.summarize_equity(values, trade_returns, traded_notional)
    summary["total_costs_eur"] = round(total_costs, 2)
    benchmark = _benchmark_curve(session, days, fx, initial_capital)
    caveats = build_caveats(
        session, start, end, fx_available=fx.available, cost_bps=cost_bps, fee_eur=fee,
        extra=["Score-Gewichte (scoring.yaml) wurden nicht auf diesen Daten optimiert — "
               "sobald du sie nach Backtest-Ergebnissen tunst, gilt das Multiple-Testing-"
               "Caveat umso mehr."],
    )
    return {
        "strategy": "score_ranking",
        "config": {"start": start.isoformat(), "end": end.isoformat(), "top_n": top_n,
                   "rebalance": rebalance, "cost_bps_per_side": cost_bps, "fee_eur": fee,
                   "initial_capital": initial_capital},
        "metrics": summary,
        "equity": [[d.isoformat(), v] for d, v in equity_curve],
        "benchmark": benchmark,
        "caveats": caveats,
        "warnings": overfitting_warnings(2, len(days), summary["n_trades"]),
    }


def _benchmark_curve(
    session: Session, days: list[date], fx: FxConverter, initial: float
) -> list[list[Any]] | None:
    """^GSPC auf dasselbe Startkapital normiert (EUR). Ohne Daten ehrlich None."""
    rows = session.execute(
        select(PriceBarRow.date, PriceBarRow.close)
        .where(PriceBarRow.ticker == "^GSPC",
               PriceBarRow.date >= days[0], PriceBarRow.date <= days[-1])
        .order_by(PriceBarRow.date)
    ).all()
    closes = {d: float(c) for d, c in rows if c is not None}
    if len(closes) < 2:
        return None
    curve: list[list[Any]] = []
    base: float | None = None
    last: float | None = None
    for day in days:
        px = closes.get(day, last)
        if px is None:
            continue
        last = px
        eur = fx.to_eur(px, "USD", day)
        if base is None:
            base = eur
        curve.append([day.isoformat(), round(initial * eur / base, 2)])
    return curve


# ---------------------------------------------------------------- Signal-Setup-Strategie

def run_signal_setup(
    session: Session, *, signal_type: str, start: date, end: date,
    cost_bps_per_side: float | None = None, stake_pct: float = 10.0,
    max_tickers: int = 50, n_folds: int = 4,
) -> dict[str, Any]:
    """Historischer Test eines Setups: Einstieg am Folgetag des Signals, Exit per
    Stop/Ziel/Horizont (konservativ: Stop vor Ziel am selben Tag). Walk-Forward:
    Hit-Rate des Trainingsfensters vs. Out-of-Sample-Ergebnis je Fold."""
    from backend.signals.setups import ACTIVE_SETUPS, SeriesBundle

    if signal_type not in ACTIVE_SETUPS:
        raise ValueError(f"Setup {signal_type!r} nicht aktiv (verfügbar: "
                         f"{sorted(ACTIVE_SETUPS)})")
    check = ACTIVE_SETUPS[signal_type]
    cost_bps = cost_bps_per_side if cost_bps_per_side is not None else default_cost_bps_per_side()
    round_trip_cost = 2 * cost_bps / 10_000

    stocks = list(session.scalars(select(Instrument).where(Instrument.asset_type == "stock")))
    ohlc = load_ohlc(session, [i.ticker for i in stocks], start, end)
    # Liquideste Titel zuerst, Kappung für Laufzeit (dokumentiert im Report)
    ranked = sorted(
        ((t, series) for t, series in ohlc.items() if len(series) >= 220),
        key=lambda item: -sum(r[1] * r[4] for r in item[1][-60:]) / min(60, len(item[1])),
    )[:max_tickers]

    trades: list[dict[str, Any]] = []
    for ticker, series in ranked:
        closes = [r[1] for r in series]
        highs = [r[2] for r in series]
        lows = [r[3] for r in series]
        volumes = [r[4] for r in series]
        dates = [r[0] for r in series]
        open_until: int = -1  # keine überlappenden Trades je Ticker
        for i in range(210, len(series) - 1):
            if i <= open_until:
                continue
            bundle = SeriesBundle(closes=closes[: i + 1], highs=highs[: i + 1],
                                  lows=lows[: i + 1], volumes=volumes[: i + 1])
            candidate = check(bundle)
            if candidate is None:
                continue
            entry_idx = i + 1  # Ausführung am Folgetag (kein Lookahead)
            entry_px = closes[entry_idx]
            stop = entry_px - (candidate.entry - candidate.stop)   # ATR-Abstand übertragen
            target = entry_px + (candidate.target - candidate.entry)
            exit_idx, exit_px, result = _walk_exit(
                highs, lows, closes, entry_idx, stop, target, candidate.horizon_days)
            if exit_idx is None or exit_px is None:
                break  # Zeitraum endet mit offenem Trade — nicht gewertet
            gross = exit_px / entry_px - 1.0
            trades.append({
                "ticker": ticker, "entry_date": dates[entry_idx].isoformat(),
                "exit_date": dates[exit_idx].isoformat(), "result": result,
                "return_pct": round((gross - round_trip_cost) * 100, 3),
            })
            open_until = exit_idx

    trades.sort(key=lambda t: t["exit_date"])
    trade_returns = [t["return_pct"] / 100 for t in trades]

    # Equity: je Trade fester Einsatz von stake_pct des aktuellen Kapitals
    equity = [1.0]
    for r in trade_returns:
        equity.append(equity[-1] * (1 + stake_pct / 100 * r))
    summary = metrics.summarize_equity(equity, trade_returns)
    summary["stake_pct_per_trade"] = stake_pct

    folds = _walk_forward_folds(trades, start, end, n_folds)
    caveats = build_caveats(
        session, start, end, fx_available=True, cost_bps=cost_bps, fee_eur=0.0,
        extra=[f"Auf die {len(ranked)} liquidesten Titel begrenzt (Laufzeit) — "
               "illiquidere Werte fehlen.",
               "Renditen je Trade in Lokalwährung (kein FX-Effekt auf Trade-Ebene).",
               f"Equity-Kurve: fester Einsatz {stake_pct} % je Trade, sequenziell — "
               "vereinfachtes Kapitalmodell."],
    )
    return {
        "strategy": "signal_setup",
        "config": {"signal_type": signal_type, "start": start.isoformat(),
                   "end": end.isoformat(), "cost_bps_per_side": cost_bps,
                   "stake_pct": stake_pct, "max_tickers": max_tickers,
                   "n_folds": n_folds},
        "metrics": summary,
        "equity": [[str(i), round(v, 4)] for i, v in enumerate(equity)],
        "benchmark": None,
        "trades": trades[-200:],
        "walk_forward": folds,
        "caveats": caveats,
        "warnings": overfitting_warnings(5, (end - start).days * 5 // 7,
                                         summary["n_trades"]),
    }


def _walk_exit(
    highs: list[float], lows: list[float], closes: list[float],
    entry_idx: int, stop: float, target: float, horizon: int,
) -> tuple[int | None, float | None, str]:
    for days_held, j in enumerate(range(entry_idx + 1, len(closes)), start=1):
        if lows[j] <= stop:
            return j, stop, "stop_hit"      # konservativ: Stop vor Ziel
        if highs[j] >= target:
            return j, target, "target_hit"
        if days_held >= horizon:
            return j, closes[j], "expired"
    return None, None, "open"


def _walk_forward_folds(
    trades: list[dict[str, Any]], start: date, end: date, n_folds: int
) -> list[dict[str, Any]]:
    """Fold i: Training = alle Trades davor, Test = Trades im Segment.
    Zeigt ehrlich, ob die historische Hit-Rate out-of-sample hält."""
    if n_folds < 2 or not trades:
        return []
    total_days = (end - start).days
    folds: list[dict[str, Any]] = []
    for i in range(1, n_folds):
        cut = start.fromordinal(start.toordinal() + total_days * i // n_folds)
        seg_end = start.fromordinal(start.toordinal() + total_days * (i + 1) // n_folds)
        train = [t for t in trades if t["entry_date"] < cut.isoformat()]
        test = [t for t in trades
                if cut.isoformat() <= t["entry_date"] < seg_end.isoformat()]
        if not test:
            continue
        train_hit = (sum(1 for t in train if t["return_pct"] > 0) / len(train)
                     if train else None)
        test_hit = sum(1 for t in test if t["return_pct"] > 0) / len(test)
        folds.append({
            "fold": i, "test_from": cut.isoformat(), "test_to": seg_end.isoformat(),
            "n_train": len(train), "n_test": len(test),
            "train_hit_rate": round(train_hit, 4) if train_hit is not None else None,
            "test_hit_rate": round(test_hit, 4),
            "test_avg_return_pct": round(
                sum(t["return_pct"] for t in test) / len(test), 3),
        })
    return folds


# ---------------------------------------------------------------- Reports

def save_report(session: Session, name: str, result: dict[str, Any]) -> int:
    row = BacktestReportRow(
        name=name or f"{result['strategy']} {datetime.utcnow():%Y-%m-%d %H:%M}",
        strategy=str(result["strategy"]),
        config_json=json.dumps(result["config"], ensure_ascii=False),
        metrics_json=json.dumps(result["metrics"], ensure_ascii=False),
        equity_json=json.dumps(result["equity"]),
        caveats_json=json.dumps(result["caveats"], ensure_ascii=False),
        warnings_json=json.dumps(result["warnings"], ensure_ascii=False),
    )
    session.add(row)
    session.flush()
    return row.id


def list_reports(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(BacktestReportRow).order_by(BacktestReportRow.id.desc()).limit(50))
    return [
        {"id": r.id, "name": r.name, "strategy": r.strategy,
         "created_at": r.created_at.isoformat(),
         "metrics": json.loads(r.metrics_json)}
        for r in rows
    ]


def get_report(session: Session, report_id: int) -> dict[str, Any] | None:
    r = session.get(BacktestReportRow, report_id)
    if r is None:
        return None
    return {
        "id": r.id, "name": r.name, "strategy": r.strategy,
        "created_at": r.created_at.isoformat(),
        "config": json.loads(r.config_json), "metrics": json.loads(r.metrics_json),
        "equity": json.loads(r.equity_json), "caveats": json.loads(r.caveats_json),
        "warnings": json.loads(r.warnings_json),
    }
