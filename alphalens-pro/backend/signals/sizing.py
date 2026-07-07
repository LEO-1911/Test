"""Positionsgrößen (USP 4): capped Fractional Kelly, volatilitätsskaliert.

Jeder Rechenschritt wird einzeln zurückgegeben — das UI zeigt die komplette
Herleitung ("Why this size?"), nicht nur die Endzahl."""

from __future__ import annotations

from typing import Any

from backend.settings import load_config


def kelly_fraction(p: float, payoff_b: float) -> float:
    """Kelly-Formel f* = p - (1-p)/b. Negativ (Erwartungswert < 0) -> 0."""
    if payoff_b <= 0:
        return 0.0
    return max(0.0, p - (1.0 - p) / payoff_b)


def position_size(
    probability: float,
    entry: float,
    stop: float,
    target: float | None,
    realized_vol: float | None,
    regime_factor: float = 1.0,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Vollständige Größenherleitung in Prozent des Portfolios.

    1. Payoff b = (Ziel-Entry)/(Entry-Stop)  (ohne Ziel: konservativ b=1.5)
    2. Kelly f* = p - (1-p)/b, dann Fractional-Faktor (Default 0.25)
    3. Volatilitäts-Skalierung: min(1, Zielvol/realisierte Vol)
    4. Cap (Default 25 %) und Regime-Faktor"""
    cfg = cfg or load_config("signals")["position_sizing"]
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return {"final_pct": 0.0, "error": "Stop liegt nicht unter dem Entry"}
    payoff_b = ((target - entry) / risk_per_share) if target is not None else 1.5
    kelly_full = kelly_fraction(probability, payoff_b)
    kelly_scaled = kelly_full * float(cfg["kelly_fraction"])
    target_vol = float(cfg["target_volatility_pct"]) / 100.0
    if realized_vol is not None and realized_vol > 0:
        vol_scale = min(1.0, target_vol / realized_vol)
        vol_note = f"Zielvol {target_vol:.0%} / realisiert {realized_vol:.0%}"
    else:
        vol_scale = 1.0
        vol_note = "keine Vol-Daten — Skalierung 1.0"
    raw_pct = kelly_scaled * vol_scale * 100.0
    capped_pct = min(raw_pct, float(cfg["max_position_pct"]))
    final_pct = round(capped_pct * regime_factor, 2)
    return {
        "probability": probability,
        "payoff_b": round(payoff_b, 3),
        "kelly_full": round(kelly_full, 4),
        "kelly_fraction_cfg": float(cfg["kelly_fraction"]),
        "kelly_scaled": round(kelly_scaled, 4),
        "vol_scale": round(vol_scale, 3),
        "vol_note": vol_note,
        "raw_pct": round(raw_pct, 2),
        "cap_pct": float(cfg["max_position_pct"]),
        "regime_factor": regime_factor,
        "final_pct": final_pct,
        "steps": (
            f"Kelly f*={kelly_full:.3f} (p={probability:.2f}, b={payoff_b:.2f}) "
            f"x {cfg['kelly_fraction']} = {kelly_scaled:.3f}; "
            f"x Vol-Skalierung {vol_scale:.2f} ({vol_note}) = {raw_pct:.1f} %; "
            f"Cap {cfg['max_position_pct']} %; x Regime {regime_factor} "
            f"= {final_pct} %"
        ),
    }
