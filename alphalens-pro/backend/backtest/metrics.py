"""Backtest-Kennzahlen — pure Funktionen mit Golden-Value-Tests.

Jede Renditekennzahl bekommt ein Block-Bootstrap-Konfidenzintervall (USP 1):
statt einer Punktschätzung zeigen wir die Bandbreite, die mit denselben Daten
statistisch verträglich ist. Blöcke erhalten die Autokorrelation der Renditen."""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from typing import Any

TRADING_DAYS_PER_YEAR = 252


def to_returns(equity: list[float]) -> list[float]:
    return [equity[i] / equity[i - 1] - 1.0
            for i in range(1, len(equity)) if equity[i - 1] != 0]


def cagr(equity: list[float], periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float | None:
    if len(equity) < 2 or equity[0] <= 0 or equity[-1] <= 0:
        return None
    years = (len(equity) - 1) / periods_per_year
    if years <= 0:
        return None
    return float((equity[-1] / equity[0]) ** (1 / years)) - 1.0


def sharpe(returns: list[float], periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float | None:
    """Annualisierte Sharpe Ratio (risikofreier Zins 0 — als Caveat ausgewiesen)."""
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    if var == 0:
        return None
    return mean / math.sqrt(var) * math.sqrt(periods_per_year)


def sortino(returns: list[float], periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float | None:
    """Wie Sharpe, aber nur Abwärtsvolatilität im Nenner."""
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    downside = [min(0.0, r) for r in returns]
    dvar = sum(d ** 2 for d in downside) / len(returns)
    if dvar == 0:
        return None
    return mean / math.sqrt(dvar) * math.sqrt(periods_per_year)


def max_drawdown(equity: list[float]) -> float | None:
    if len(equity) < 2:
        return None
    peak = equity[0]
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1.0)
    return worst


def hit_rate(trade_returns: list[float]) -> float | None:
    if not trade_returns:
        return None
    return sum(1 for r in trade_returns if r > 0) / len(trade_returns)


def annual_turnover(traded_notional: float, avg_equity: float, n_days: int) -> float | None:
    """Gehandeltes Volumen (Kauf+Verkauf) relativ zum Durchschnittskapital, p.a."""
    if avg_equity <= 0 or n_days <= 0:
        return None
    years = n_days / TRADING_DAYS_PER_YEAR
    return traded_notional / avg_equity / years


def block_bootstrap_ci(
    returns: list[float],
    stat_fn: Callable[[list[float]], float | None],
    *,
    n_boot: int = 500,
    block_size: int = 20,
    seed: int = 42,
    ci: float = 0.95,
) -> tuple[float, float] | None:
    """Block-Bootstrap-Konfidenzintervall: Renditeserie in Blöcken neu ziehen,
    Kennzahl je Resample berechnen, Perzentile zurückgeben. Deterministisch (seed)."""
    if len(returns) < block_size * 2:
        return None
    rng = random.Random(seed)
    n_blocks = math.ceil(len(returns) / block_size)
    stats: list[float] = []
    for _ in range(n_boot):
        sample: list[float] = []
        for _ in range(n_blocks):
            start = rng.randint(0, len(returns) - block_size)
            sample.extend(returns[start:start + block_size])
        value = stat_fn(sample[: len(returns)])
        if value is not None:
            stats.append(value)
    if len(stats) < n_boot // 2:
        return None
    stats.sort()
    alpha = (1 - ci) / 2
    lo = stats[max(0, int(alpha * len(stats)))]
    hi = stats[min(len(stats) - 1, int((1 - alpha) * len(stats)))]
    return (lo, hi)


def _equity_from_returns(returns: list[float]) -> list[float]:
    equity = [1.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r))
    return equity


def summarize_equity(
    equity: list[float], trade_returns: list[float] | None = None,
    traded_notional: float = 0.0,
) -> dict[str, Any]:
    """Komplettes Kennzahlen-Paket inkl. Konfidenzintervallen für eine Equity-Kurve."""
    returns = to_returns(equity)
    avg_equity = sum(equity) / len(equity) if equity else 0.0

    def ci_of(fn: Callable[[list[float]], float | None]) -> list[float] | None:
        interval = block_bootstrap_ci(returns, fn)
        return [round(interval[0], 4), round(interval[1], 4)] if interval else None

    def r(value: float | None, digits: int = 4) -> float | None:
        return round(value, digits) if value is not None else None

    return {
        "total_return_pct": r((equity[-1] / equity[0] - 1) * 100, 2) if len(equity) > 1 else None,
        "cagr": r(cagr(equity)),
        "cagr_ci95": ci_of(lambda rs: cagr(_equity_from_returns(rs))),
        "sharpe": r(sharpe(returns)),
        "sharpe_ci95": ci_of(sharpe),
        "sortino": r(sortino(returns)),
        "max_drawdown": r(max_drawdown(equity)),
        "hit_rate": r(hit_rate(trade_returns or [])),
        "n_trades": len(trade_returns or []),
        "annual_turnover": r(annual_turnover(traded_notional, avg_equity, len(equity))),
        "n_days": len(equity),
    }
