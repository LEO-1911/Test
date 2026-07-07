"""Golden-Value-Tests für die Kalibrierungs-Bausteine (USP 5)."""

from __future__ import annotations

import pytest

from backend.ledger import calibration as cal


def test_laplace_rate_known_values() -> None:
    assert cal.laplace_rate(0, 0) == pytest.approx(0.5)      # keine Daten -> 0.5
    assert cal.laplace_rate(1, 1) == pytest.approx(2 / 3)    # 1 Treffer aus 1
    assert cal.laplace_rate(50, 100) == pytest.approx(51 / 102)
    assert cal.laplace_rate(998, 1000) == pytest.approx(999 / 1002)  # konvergiert
    with pytest.raises(ValueError):
        cal.laplace_rate(5, 3)


def test_brier_score_known_values() -> None:
    assert cal.brier_score([]) is None
    assert cal.brier_score([(1.0, 1), (0.0, 0)]) == pytest.approx(0.0)   # perfekt
    assert cal.brier_score([(0.5, 1), (0.5, 0)]) == pytest.approx(0.25)  # uninformiert
    assert cal.brier_score([(1.0, 0)]) == pytest.approx(1.0)             # maximal falsch
    # Gemischt: (0.8-1)^2=0.04, (0.3-0)^2=0.09 -> 0.065
    assert cal.brier_score([(0.8, 1), (0.3, 0)]) == pytest.approx(0.065)


def test_reliability_bins_known_values() -> None:
    pairs = [(0.05, 0), (0.15, 0), (0.15, 1), (0.95, 1), (1.0, 1)]
    bins = cal.reliability_bins(pairs, n_bins=10)
    first = next(b for b in bins if b["bin_low"] == 0.0)
    assert first["count"] == 1 and first["observed_rate"] == 0.0
    second = next(b for b in bins if b["bin_low"] == pytest.approx(0.1))
    assert second["count"] == 2
    assert second["observed_rate"] == pytest.approx(0.5)
    last = next(b for b in bins if b["bin_high"] == pytest.approx(1.0))
    assert last["count"] == 2  # 0.95 und der Randfall p=1.0
    assert last["observed_rate"] == pytest.approx(1.0)


def test_isotonic_fit_pava_known_values() -> None:
    # Verletzung [1, 0] wird gepoolt: -> [0.5, 0.5, 1.0]
    assert cal.isotonic_fit([0.1, 0.5, 0.9], [1.0, 0.0, 1.0]) == pytest.approx([0.5, 0.5, 1.0])
    # Bereits monoton -> unverändert
    assert cal.isotonic_fit([0.1, 0.9], [0.2, 0.8]) == pytest.approx([0.2, 0.8])
    # Komplett fallend -> alles auf den Mittelwert gepoolt
    assert cal.isotonic_fit([0.1, 0.5, 0.9], [0.9, 0.5, 0.1]) == pytest.approx([0.5, 0.5, 0.5])
    with pytest.raises(ValueError):
        cal.isotonic_fit([0.9, 0.1], [0.0, 1.0])  # unsortiert


def test_calibrate_probability_interpolates() -> None:
    xs = [0.2, 0.8]
    fitted = [0.3, 0.7]
    assert cal.calibrate_probability(0.5, xs, fitted) == pytest.approx(0.5)
    assert cal.calibrate_probability(0.2, xs, fitted) == pytest.approx(0.3)
    assert cal.calibrate_probability(0.0, xs, fitted) == pytest.approx(0.3)   # Randwert
    assert cal.calibrate_probability(0.99, xs, fitted) == pytest.approx(0.7)
    assert cal.calibrate_probability(0.6, [], []) == pytest.approx(0.6)       # kein Fit


def test_calibration_status_badge() -> None:
    status = cal.calibration_status(3)
    assert status["calibrated"] is False
    assert "unkalibriert" in status["label"] and "n=3" in status["label"]
    status_ok = cal.calibration_status(10_000)
    assert status_ok["calibrated"] is True
