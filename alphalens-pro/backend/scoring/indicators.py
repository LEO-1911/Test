"""Technische Indikatoren als pure Funktionen auf Kursreihen (ältester Wert zuerst).

Keine DB, kein Netz — jede Funktion ist mit bekannten Beispielwerten getestet.
Alle Funktionen geben None zurück, wenn die Reihe zu kurz ist (nie raten)."""

from __future__ import annotations

import math


def simple_return(closes: list[float], periods: int) -> float | None:
    """Gesamtrendite über die letzten `periods` Bars: last/close[-1-periods] - 1."""
    if len(closes) <= periods or closes[-1 - periods] == 0:
        return None
    return closes[-1] / closes[-1 - periods] - 1.0


def annualized_volatility(closes: list[float], window: int = 252) -> float | None:
    """Annualisierte Volatilität der Tagesrenditen über die letzten `window` Bars."""
    if len(closes) < min(window, 30) + 1:
        return None
    tail = closes[-(window + 1):]
    rets = [tail[i] / tail[i - 1] - 1.0 for i in range(1, len(tail)) if tail[i - 1] != 0]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252)


def moving_average(closes: list[float], window: int) -> float | None:
    if len(closes) < window:
        return None
    return sum(closes[-window:]) / window


def rsi(closes: list[float], period: int = 14) -> float | None:
    """Relative Strength Index nach Wilder (geglättete Mittelwerte)."""
    if len(closes) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def max_drawdown(closes: list[float]) -> float | None:
    """Maximaler Rückgang vom bisherigen Hoch, als negative Zahl (z.B. -0.5 = -50 %)."""
    if len(closes) < 2:
        return None
    peak = closes[0]
    worst = 0.0
    for price in closes:
        peak = max(peak, price)
        if peak > 0:
            worst = min(worst, price / peak - 1.0)
    return worst


def dist_from_high(closes: list[float], lookback: int = 252) -> float | None:
    """Abstand des letzten Kurses zum Hoch der letzten `lookback` Bars (<= 0)."""
    if not closes:
        return None
    window = closes[-lookback:]
    high = max(window)
    if high == 0:
        return None
    return closes[-1] / high - 1.0


def risk_adjusted_return(closes: list[float], periods: int) -> float | None:
    """Rendite über `periods` Bars geteilt durch annualisierte Vol im selben Fenster."""
    ret = simple_return(closes, periods)
    vol = annualized_volatility(closes, window=periods)
    if ret is None or vol is None or vol == 0:
        return None
    return ret / vol


def atr(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> float | None:
    """Average True Range nach Wilder: TR = max(H-L, |H-C_prev|, |L-C_prev|),
    geglättet über `period`. Basis für Stop-Loss-Abstände der Signal-Engine."""
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return None
    true_ranges: list[float] = []
    for i in range(1, n):
        prev_close = closes[i - 1]
        true_ranges.append(max(
            highs[i] - lows[i],
            abs(highs[i] - prev_close),
            abs(lows[i] - prev_close),
        ))
    value = sum(true_ranges[:period]) / period
    for tr in true_ranges[period:]:
        value = (value * (period - 1) + tr) / period
    return value


def avg_dollar_volume(closes: list[float], volumes: list[float], window: int = 60) -> float | None:
    """Durchschnittliches Handelsvolumen in Geldeinheiten (Liquiditätsmaß)."""
    n = min(len(closes), len(volumes))
    if n == 0:
        return None
    pairs = [(closes[i], volumes[i]) for i in range(n - min(n, window), n)]
    values = [c * v for c, v in pairs if c is not None and v is not None]
    if not values:
        return None
    return sum(values) / len(values)
