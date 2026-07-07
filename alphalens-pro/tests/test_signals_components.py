"""Golden-Value-Tests für Signal-Bausteine: ATR, Kelly-Sizing, Setups."""

from __future__ import annotations

import pytest

from backend.scoring.indicators import atr
from backend.signals.setups import (
    SeriesBundle,
    check_breakout,
    check_earnings_momentum,
    check_mean_reversion,
    check_pullback_ma50,
)
from backend.signals.sizing import kelly_fraction, position_size

SIZING_CFG = {
    "kelly_fraction": 0.25, "max_position_pct": 25.0,
    "target_volatility_pct": 20.0, "stop_atr_multiple": 2.0,
}


# ---------------------------------------------------------------- ATR

def test_atr_constant_range() -> None:
    # Flache Kurse, Spanne konstant 2 -> ATR exakt 2
    n = 30
    closes = [100.0] * n
    highs = [101.0] * n
    lows = [99.0] * n
    assert atr(highs, lows, closes, 14) == pytest.approx(2.0)


def test_atr_includes_gaps() -> None:
    # Kurssprung: TR nutzt |High - Vorschluss| -> ATR > reine Tagesspanne
    closes = [100.0] * 20 + [110.0]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    value = atr(highs, lows, closes, 14)
    assert value is not None and value > 2.0


def test_atr_needs_enough_bars() -> None:
    assert atr([1.0] * 5, [1.0] * 5, [1.0] * 5, 14) is None


# ---------------------------------------------------------------- Kelly / Sizing

def test_kelly_fraction_known_values() -> None:
    assert kelly_fraction(0.6, 2.0) == pytest.approx(0.4)   # 0.6 - 0.4/2
    assert kelly_fraction(0.5, 1.0) == pytest.approx(0.0)   # fairer Münzwurf -> 0
    assert kelly_fraction(0.3, 1.0) == pytest.approx(0.0)   # negativer Erwartungswert -> 0
    assert kelly_fraction(0.9, 0.0) == pytest.approx(0.0)   # kaputter Payoff -> 0


def test_position_size_full_derivation() -> None:
    # p=0.6, Entry 100, Stop 95, Ziel 110 -> b=2; Kelly 0.4 -> x0.25 = 0.10
    # Vol 40 % vs Ziel 20 % -> Skalierung 0.5 -> 5 %
    result = position_size(0.6, 100.0, 95.0, 110.0, realized_vol=0.40, cfg=SIZING_CFG)
    assert result["payoff_b"] == pytest.approx(2.0)
    assert result["kelly_full"] == pytest.approx(0.4)
    assert result["kelly_scaled"] == pytest.approx(0.1)
    assert result["vol_scale"] == pytest.approx(0.5)
    assert result["final_pct"] == pytest.approx(5.0)
    assert "Kelly" in result["steps"]


def test_position_size_cap_applies() -> None:
    # Extrem günstiger Fall würde >25 % ergeben -> Cap greift
    cfg = {**SIZING_CFG, "kelly_fraction": 1.0}
    result = position_size(0.9, 100.0, 99.0, 120.0, realized_vol=0.10, cfg=cfg)
    assert result["raw_pct"] > 25.0
    assert result["final_pct"] == pytest.approx(25.0)


def test_position_size_regime_throttles() -> None:
    calm = position_size(0.6, 100.0, 95.0, 110.0, 0.20, regime_factor=1.0, cfg=SIZING_CFG)
    stressed = position_size(0.6, 100.0, 95.0, 110.0, 0.20, regime_factor=0.25, cfg=SIZING_CFG)
    assert stressed["final_pct"] == pytest.approx(calm["final_pct"] * 0.25)


def test_position_size_invalid_stop() -> None:
    result = position_size(0.6, 100.0, 105.0, 110.0, 0.2, cfg=SIZING_CFG)
    assert result["final_pct"] == 0.0
    assert "Stop" in result["error"]


# ---------------------------------------------------------------- Setups

def _series(closes: list[float], volumes: list[float] | None = None,
            spread: float = 1.0) -> SeriesBundle:
    volumes = volumes or [1_000_000.0] * len(closes)
    return SeriesBundle(
        closes=closes,
        highs=[c + spread for c in closes],
        lows=[c - spread for c in closes],
        volumes=volumes,
    )


def _uptrend(n: int = 300, start: float = 100.0, step: float = 0.3) -> list[float]:
    return [start + i * step for i in range(n)]


def test_mean_reversion_fires_on_dip_in_uptrend() -> None:
    # Langer Aufwärtstrend, dann Rücksetzer: RSI < 30 (nur Verlusttage),
    # aber flach genug, dass der Kurs über dem MA200 bleibt (Trendfilter)
    closes = _uptrend(300)
    closes += [closes[-1] - 1.2 * i for i in range(1, 16)]  # 15 moderate Verlusttage
    candidate = check_mean_reversion(_series(closes))
    assert candidate is not None
    assert candidate.signal_type == "mean_reversion"
    assert candidate.stop < candidate.entry < candidate.target
    assert any("RSI" in w for w in candidate.why)


def test_mean_reversion_blocked_in_downtrend() -> None:
    # Fallende Kurse: RSI ist niedrig, aber Kurs unter MA200 -> Trendfilter blockt
    closes = [400.0 - i * 1.0 for i in range(300)]
    assert check_mean_reversion(_series(closes)) is None


def test_breakout_fires_on_high_with_volume() -> None:
    closes = _uptrend(300)  # letzter Kurs = Allzeithoch
    volumes = [1_000_000.0] * 299 + [2_000_000.0]  # 2x Durchschnitt am Ausbruchstag
    candidate = check_breakout(_series(closes, volumes))
    assert candidate is not None
    assert any("52W-Hoch" in w for w in candidate.why)


def test_breakout_blocked_without_volume() -> None:
    closes = _uptrend(300)
    assert check_breakout(_series(closes)) is None  # Volumen nur 1x Durchschnitt


def test_pullback_ma50_fires_near_ma50_in_uptrend() -> None:
    # Aufwärtstrend, letzter Kurs künstlich auf MA50-Niveau gesetzt
    closes = _uptrend(300)
    ma50 = sum(closes[-50:]) / 50
    closes[-1] = ma50  # exakt am MA50
    candidate = check_pullback_ma50(_series(closes))
    assert candidate is not None
    assert any("MA50" in w for w in candidate.why)


def test_pullback_blocked_far_from_ma50() -> None:
    closes = _uptrend(300)  # steiler Trend: Kurs deutlich über MA50
    assert check_pullback_ma50(_series(closes)) is None


def test_earnings_momentum_honestly_inactive() -> None:
    assert check_earnings_momentum(_series(_uptrend(300))) is None


def test_setups_need_enough_history() -> None:
    short = _series(_uptrend(100))
    assert check_mean_reversion(short) is None
    assert check_breakout(short) is None
    assert check_pullback_ma50(short) is None
