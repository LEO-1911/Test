"""Golden-Value-Tests für alle technischen Indikatoren (bekannte Eingaben ->
von Hand nachrechenbare Ergebnisse)."""

from __future__ import annotations

import math

import pytest

from backend.scoring import indicators as ind


def test_simple_return_known_values() -> None:
    closes = [100.0, 110.0, 121.0]
    assert ind.simple_return(closes, 1) == pytest.approx(0.10)   # 121/110 - 1
    assert ind.simple_return(closes, 2) == pytest.approx(0.21)   # 121/100 - 1
    assert ind.simple_return(closes, 5) is None                  # Reihe zu kurz


def test_moving_average_known_values() -> None:
    closes = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert ind.moving_average(closes, 3) == pytest.approx(4.0)   # (3+4+5)/3
    assert ind.moving_average(closes, 5) == pytest.approx(3.0)
    assert ind.moving_average(closes, 6) is None


def test_max_drawdown_known_values() -> None:
    # Hoch 120, Tief danach 60 -> -50 %
    assert ind.max_drawdown([100.0, 120.0, 60.0, 90.0]) == pytest.approx(-0.5)
    # Monoton steigend -> kein Drawdown
    assert ind.max_drawdown([1.0, 2.0, 3.0]) == pytest.approx(0.0)
    assert ind.max_drawdown([100.0]) is None


def test_dist_from_high_known_values() -> None:
    closes = [80.0, 100.0, 75.0]
    assert ind.dist_from_high(closes, 252) == pytest.approx(-0.25)  # 75/100 - 1
    assert ind.dist_from_high(closes[-1:], 252) == pytest.approx(0.0)  # letzter = Hoch


def test_rsi_invariants() -> None:
    # Nur Gewinne -> RSI 100
    rising = [float(i) for i in range(1, 31)]
    assert ind.rsi(rising, 14) == pytest.approx(100.0)
    # Nur Verluste -> RSI nahe 0
    falling = [float(i) for i in range(60, 30, -1)]
    assert ind.rsi(falling, 14) == pytest.approx(0.0, abs=1e-6)
    # Symmetrisches Auf und Ab gleicher Größe -> RSI pendelt um 50 (Wilder-Glättung
    # lässt den Wert je nach letztem Tag leicht über/unter 50 stehen)
    alternating = [100.0 + (1.0 if i % 2 else 0.0) for i in range(40)]
    assert ind.rsi(alternating, 14) == pytest.approx(50.0, abs=3.0)
    assert ind.rsi([1.0, 2.0], 14) is None


def test_annualized_volatility_constant_series_is_zero() -> None:
    flat = [100.0] * 260
    assert ind.annualized_volatility(flat, 252) == pytest.approx(0.0)


def test_annualized_volatility_known_alternation() -> None:
    # Renditen alternieren +1 % / -1 % (ungefähr): Tages-Std ~1 %, annualisiert ~15.9 %
    closes = [100.0]
    for i in range(300):
        closes.append(closes[-1] * (1.01 if i % 2 == 0 else 0.99))
    vol = ind.annualized_volatility(closes, 252)
    assert vol is not None
    assert vol == pytest.approx(0.01 * math.sqrt(252), rel=0.05)


def test_risk_adjusted_return_guards() -> None:
    flat = [100.0] * 260
    assert ind.risk_adjusted_return(flat, 252) is None  # Vol 0 -> nicht definiert


def test_avg_dollar_volume_known_values() -> None:
    closes = [10.0, 20.0]
    volumes = [100.0, 200.0]
    # (10*100 + 20*200)/2 = 2500
    assert ind.avg_dollar_volume(closes, volumes, window=60) == pytest.approx(2500.0)
    assert ind.avg_dollar_volume([], [], 60) is None
