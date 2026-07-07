"""Kalibrierungs-Infrastruktur (USP 5): Wahrscheinlichkeiten müssen zur Realität
passen — und solange die Stichprobe klein ist, sagen wir das ehrlich dazu.

Pure Funktionen mit Golden-Value-Tests; die Signal-Engine (MS5) und das
Earnings-Center (MS8) bauen darauf auf."""

from __future__ import annotations

from typing import Any

from backend.settings import load_config


def laplace_rate(successes: int, n: int, alpha: float = 1.0) -> float:
    """Laplace-geglättete Trefferquote: (s + a) / (n + 2a). Bei n=0 -> 0.5 (ehrliches
    'wir wissen nichts'), konvergiert mit wachsendem n gegen die rohe Quote."""
    if n < 0 or successes < 0 or successes > n:
        raise ValueError(f"unplausibel: {successes}/{n}")
    return (successes + alpha) / (n + 2 * alpha)


def brier_score(pairs: list[tuple[float, int]]) -> float | None:
    """Mittlerer quadratischer Fehler der Wahrscheinlichkeitsprognosen.
    pairs = [(prognostizierte Wahrscheinlichkeit, Ausgang 0/1), ...].
    0 = perfekt, 0.25 = uninformiert (immer 0.5), 1 = maximal falsch."""
    if not pairs:
        return None
    return sum((p - outcome) ** 2 for p, outcome in pairs) / len(pairs)


def reliability_bins(
    pairs: list[tuple[float, int]], n_bins: int = 10
) -> list[dict[str, Any]]:
    """Daten fürs Reliability-Diagramm: je Wahrscheinlichkeits-Bin die mittlere
    Prognose vs. die beobachtete Trefferquote. Perfekte Kalibrierung = Diagonale."""
    bins: list[dict[str, Any]] = []
    for b in range(n_bins):
        low, high = b / n_bins, (b + 1) / n_bins
        members = [(p, o) for p, o in pairs
                   if (low <= p < high) or (b == n_bins - 1 and p == 1.0)]
        if not members:
            continue
        bins.append({
            "bin_low": low,
            "bin_high": high,
            "mean_predicted": sum(p for p, _ in members) / len(members),
            "observed_rate": sum(o for _, o in members) / len(members),
            "count": len(members),
        })
    return bins


def isotonic_fit(xs: list[float], ys: list[float]) -> list[float]:
    """Isotonische Regression per Pool-Adjacent-Violators (PAVA): monotone
    Kalibrierungskurve durch (Prognose, Ausgang)-Paare. xs muss sortiert sein."""
    if len(xs) != len(ys):
        raise ValueError("xs und ys müssen gleich lang sein")
    if any(xs[i] > xs[i + 1] for i in range(len(xs) - 1)):
        raise ValueError("xs muss aufsteigend sortiert sein")
    # Blöcke: (Summe, Anzahl); verletzen zwei Nachbarn die Monotonie, werden sie gepoolt
    blocks: list[tuple[float, int]] = []
    for y in ys:
        blocks.append((y, 1))
        while len(blocks) >= 2 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            s2, n2 = blocks.pop()
            s1, n1 = blocks.pop()
            blocks.append((s1 + s2, n1 + n2))
    fitted: list[float] = []
    for total, count in blocks:
        fitted.extend([total / count] * count)
    return fitted


def calibrate_probability(p: float, xs: list[float], fitted: list[float]) -> float:
    """Wendet eine gefittete Isotonic-Kurve auf eine neue Prognose an
    (lineare Interpolation, außerhalb des Bereichs: Randwert)."""
    if not xs:
        return p
    if p <= xs[0]:
        return fitted[0]
    if p >= xs[-1]:
        return fitted[-1]
    for i in range(1, len(xs)):
        if p <= xs[i]:
            if xs[i] == xs[i - 1]:
                return fitted[i]
            frac = (p - xs[i - 1]) / (xs[i] - xs[i - 1])
            return fitted[i - 1] + frac * (fitted[i] - fitted[i - 1])
    return fitted[-1]


def calibration_status(n_closed: int) -> dict[str, Any]:
    """Ehrlichkeits-Badge: erst ab min_samples_calibrated gilt eine Quote als
    kalibriert; davor zeigt das UI 'unkalibriert (n=…)'."""
    cfg = load_config("signals")["calibration"]
    min_n = int(cfg["min_samples_calibrated"])
    return {
        "calibrated": n_closed >= min_n,
        "n_closed": n_closed,
        "min_required": min_n,
        "label": ("kalibriert" if n_closed >= min_n
                  else f"unkalibriert (n={n_closed}, benötigt {min_n})"),
    }
