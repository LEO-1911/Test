"""Die vier Long-Setups — jede Bedingung wird mit Ist-Wert und Schwelle
protokolliert (Why-Panel). Ein Setup feuert nur, wenn ALLE Bedingungen erfüllt
sind; earnings_momentum ist bis MS8 (Earnings-Daten) ehrlich deaktiviert."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.scoring import indicators as ind
from backend.settings import load_config

MIN_BARS = 210  # MA200 + Puffer


@dataclass(frozen=True)
class SeriesBundle:
    closes: list[float]
    highs: list[float]
    lows: list[float]
    volumes: list[float]


@dataclass(frozen=True)
class SignalCandidate:
    signal_type: str
    entry: float
    stop: float
    target: float
    horizon_days: int
    atr_value: float
    why: list[str] = field(default_factory=list)


def _levels(
    entry: float, atr_value: float, setup_cfg: dict[str, Any], sizing_cfg: dict[str, Any]
) -> tuple[float, float]:
    stop = entry - float(sizing_cfg["stop_atr_multiple"]) * atr_value
    target = entry + float(setup_cfg["reward_multiple"]) * (entry - stop)
    return round(stop, 4), round(target, 4)


def _base(series: SeriesBundle) -> tuple[float, float] | None:
    """Gemeinsame Vorbedingungen: genug Historie, ATR berechenbar."""
    if len(series.closes) < MIN_BARS:
        return None
    atr_value = ind.atr(series.highs, series.lows, series.closes, 14)
    if atr_value is None or atr_value <= 0:
        return None
    return series.closes[-1], atr_value


def check_mean_reversion(series: SeriesBundle) -> SignalCandidate | None:
    """RSI-Oversold im intakten Aufwärtstrend (Kurs über MA200)."""
    cfg = load_config("signals")
    setup = cfg["setups"]["mean_reversion"]
    base = _base(series)
    if base is None:
        return None
    close, atr_value = base
    rsi = ind.rsi(series.closes, int(setup["rsi_period"]))
    ma200 = ind.moving_average(series.closes, 200)
    if rsi is None or ma200 is None:
        return None
    if rsi >= float(setup["rsi_oversold"]) or close <= ma200:
        return None
    stop, target = _levels(close, atr_value, setup, cfg["position_sizing"])
    return SignalCandidate(
        signal_type="mean_reversion", entry=close, stop=stop, target=target,
        horizon_days=int(setup["horizon_days"]), atr_value=round(atr_value, 4),
        why=[
            f"RSI(14) {rsi:.1f} < {setup['rsi_oversold']} (überverkauft)",
            f"Kurs {close:.2f} über MA200 {ma200:.2f} (Aufwärtstrend intakt)",
            f"Stop {stop:.2f} = Entry - {cfg['position_sizing']['stop_atr_multiple']} x ATR "
            f"{atr_value:.2f}; Ziel {target:.2f} (R/R {setup['reward_multiple']})",
        ],
    )


def check_breakout(series: SeriesBundle) -> SignalCandidate | None:
    """Neues 52-Wochen-Hoch mit überdurchschnittlichem Volumen."""
    cfg = load_config("signals")
    setup = cfg["setups"]["breakout"]
    base = _base(series)
    if base is None:
        return None
    close, atr_value = base
    lookback = int(setup["lookback_days"])
    high_52w = max(series.closes[-lookback:])
    avg_vol20 = ind.moving_average(series.volumes, 20)
    if avg_vol20 is None or avg_vol20 <= 0:
        return None
    volume = series.volumes[-1]
    volume_factor = float(setup["volume_factor"])
    if close < high_52w or volume < volume_factor * avg_vol20:
        return None
    stop, target = _levels(close, atr_value, setup, cfg["position_sizing"])
    return SignalCandidate(
        signal_type="breakout", entry=close, stop=stop, target=target,
        horizon_days=int(setup["horizon_days"]), atr_value=round(atr_value, 4),
        why=[
            f"Schluss {close:.2f} = 52W-Hoch (Lookback {lookback} Tage)",
            f"Volumen {volume:.0f} >= {volume_factor} x 20-Tage-Schnitt {avg_vol20:.0f}",
            f"Stop {stop:.2f} (ATR-basiert); Ziel {target:.2f} "
            f"(R/R {setup['reward_multiple']})",
        ],
    )


def check_pullback_ma50(series: SeriesBundle) -> SignalCandidate | None:
    """Rücksetzer auf den MA50 im Aufwärtstrend (MA50 > MA200, Kurs > MA200)."""
    cfg = load_config("signals")
    setup = cfg["setups"]["pullback_ma50"]
    base = _base(series)
    if base is None:
        return None
    close, atr_value = base
    ma50 = ind.moving_average(series.closes, 50)
    ma200 = ind.moving_average(series.closes, 200)
    if ma50 is None or ma200 is None or ma50 <= ma200 or close <= ma200:
        return None
    dist_pct = abs(close / ma50 - 1.0) * 100
    if dist_pct > float(setup["max_dist_ma50_pct"]):
        return None
    stop, target = _levels(close, atr_value, setup, cfg["position_sizing"])
    return SignalCandidate(
        signal_type="pullback_ma50", entry=close, stop=stop, target=target,
        horizon_days=int(setup["horizon_days"]), atr_value=round(atr_value, 4),
        why=[
            f"MA50 {ma50:.2f} > MA200 {ma200:.2f} (Aufwärtstrend)",
            f"Kurs {close:.2f} nur {dist_pct:.1f} % vom MA50 entfernt "
            f"(max. {setup['max_dist_ma50_pct']} %)",
            f"Stop {stop:.2f} (ATR-basiert); Ziel {target:.2f} "
            f"(R/R {setup['reward_multiple']})",
        ],
    )


def check_earnings_momentum(series: SeriesBundle) -> SignalCandidate | None:  # noqa: ARG001
    """Deaktiviert bis MS8: braucht Earnings-Surprise-Daten, die die Pipeline
    noch nicht lädt. Ehrlich aus statt heimlich raten."""
    return None


ACTIVE_SETUPS = {
    "mean_reversion": check_mean_reversion,
    "breakout": check_breakout,
    "pullback_ma50": check_pullback_ma50,
}

INACTIVE_SETUPS = {
    "earnings_momentum": "Datenquelle (Earnings-Historie) kommt in MS8",
}
