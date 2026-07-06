"""Golden-Value-Tests für JEDE Score-Komponente (Anforderung aus M2):
bekannte Rohwerte -> erwartete Scores, plus Missing-Verhalten."""

from __future__ import annotations

import pytest

from backend.scoring import components as comp


def test_percentile_rank_known_values() -> None:
    peers = [10.0, 20.0, 30.0, 40.0]
    assert comp.percentile_rank(25.0, peers) == pytest.approx(50.0)
    assert comp.percentile_rank(5.0, peers) == pytest.approx(0.0)
    assert comp.percentile_rank(45.0, peers) == pytest.approx(100.0)
    # Gleichstand: Midrank — 20 ist größer als 1 von 4, gleich 1 von 4 -> (1+0.5)/4 = 37.5
    assert comp.percentile_rank(20.0, peers) == pytest.approx(37.5)
    # higher_is_better=False dreht die Skala
    assert comp.percentile_rank(5.0, peers, higher_is_better=False) == pytest.approx(100.0)


def test_multiple_vs_peers_lower_is_better() -> None:
    peers = [10.0, 15.0, 20.0, 25.0, 30.0]  # genau MIN_PEERS
    cheap = comp.score_multiple_vs_peers("pe_vs_sector", 10.0, peers, "Sektor Tech")
    expensive = comp.score_multiple_vs_peers("pe_vs_sector", 30.0, peers, "Sektor Tech")
    assert cheap.score > expensive.score
    assert cheap.score == pytest.approx(90.0)   # 100 - (0 + 0.5)/5*100
    assert expensive.score == pytest.approx(10.0)
    assert not cheap.missing


def test_multiple_vs_peers_too_few_peers_is_missing() -> None:
    result = comp.score_multiple_vs_peers("pe_vs_sector", 15.0, [10.0, 20.0], "Sektor X")
    assert result.missing
    assert result.score == comp.NEUTRAL
    assert "Peers" in result.detail


def test_vs_own_history() -> None:
    history = [10.0, 12.0, 14.0, 16.0, 18.0]
    low = comp.score_vs_own_history("pe_vs_own_history", 10.0, history)
    assert low.score == pytest.approx(90.0)  # niedriger als fast alles -> günstig
    short = comp.score_vs_own_history("pe_vs_own_history", 10.0, [10.0])
    assert short.missing


def test_score_roe_known_values() -> None:
    assert comp.score_roe(0.25).score == pytest.approx(100.0)  # 25 % ROE -> 100
    assert comp.score_roe(0.10).score == pytest.approx(40.0)   # 10 % -> 40
    assert comp.score_roe(0.0).score == pytest.approx(0.0)
    assert comp.score_roe(None).missing


def test_score_roic_known_values() -> None:
    assert comp.score_roic(0.20).score == pytest.approx(100.0)
    assert comp.score_roic(0.10).score == pytest.approx(50.0)
    assert comp.score_roic(None).missing  # yfinance liefert kein ROIC -> ehrlich fehlend


def test_score_leverage_known_values() -> None:
    assert comp.score_leverage(0.0).score == pytest.approx(100.0)
    assert comp.score_leverage(2.0).score == pytest.approx(60.0)
    assert comp.score_leverage(5.0).score == pytest.approx(0.0)
    assert comp.score_leverage(-1.0).missing  # negatives EBITDA
    assert comp.score_leverage(None).missing


def test_score_fcf_yield_known_values() -> None:
    # FCF 8 bei Marktkapitalisierung 100 -> 8 % Rendite -> 100
    assert comp.score_fcf_yield(8.0, 100.0).score == pytest.approx(100.0)
    assert comp.score_fcf_yield(4.0, 100.0).score == pytest.approx(50.0)
    assert comp.score_fcf_yield(None, 100.0).missing
    assert comp.score_fcf_yield(5.0, 0.0).missing


def test_score_margin_stability_known_values() -> None:
    # Perfekt stabil -> 100
    assert comp.score_margin_stability([0.20, 0.20, 0.20]).score == pytest.approx(100.0)
    # Std der Margen [0.10, 0.20, 0.30] = 0.10 = 10 pp -> 100 - 200 -> 0 (clip)
    assert comp.score_margin_stability([0.10, 0.20, 0.30]).score == pytest.approx(0.0)
    assert comp.score_margin_stability([0.2, 0.2]).missing  # < 3 Snapshots


def test_score_riskadj_return_absolute_fallback() -> None:
    # Ohne genug Peers: 50 + 50*Wert
    r = comp.score_riskadj_return("ret_12m_riskadj", 0.5, [])
    assert r.score == pytest.approx(75.0)
    assert "absolute Skala" in r.detail
    assert comp.score_riskadj_return("ret_12m_riskadj", None, []).missing


def test_score_riskadj_return_percentile_with_peers() -> None:
    peers = [-0.5, 0.0, 0.5, 1.0, 1.5]
    r = comp.score_riskadj_return("ret_6m_riskadj", 2.0, peers)
    assert r.score == pytest.approx(100.0)


def test_score_dist_52w_high_known_values() -> None:
    assert comp.score_dist_52w_high(0.0).score == pytest.approx(100.0)   # am Hoch
    assert comp.score_dist_52w_high(-0.25).score == pytest.approx(50.0)
    assert comp.score_dist_52w_high(-0.50).score == pytest.approx(0.0)
    assert comp.score_dist_52w_high(None).missing


def test_score_ma_signal_all_branches() -> None:
    assert comp.score_ma_signal(110.0, 105.0, 100.0).score == 100.0  # voller Aufwärtstrend
    assert comp.score_ma_signal(103.0, 105.0, 100.0).score == 66.0   # über MA200, unter MA50
    assert comp.score_ma_signal(96.0, 95.0, 100.0).score == 33.0     # über MA50, unter MA200
    assert comp.score_ma_signal(90.0, 95.0, 100.0).score == 0.0
    assert comp.score_ma_signal(None, 95.0, 100.0).missing


def test_score_rsi_passthrough() -> None:
    assert comp.score_rsi(62.4).score == pytest.approx(62.4)
    assert comp.score_rsi(None).missing


def test_score_growth_rate_known_values() -> None:
    assert comp.score_growth_rate("revenue_growth", 0.0).score == pytest.approx(50.0)
    assert comp.score_growth_rate("revenue_growth", 0.20).score == pytest.approx(100.0)
    assert comp.score_growth_rate("revenue_growth", -0.20).score == pytest.approx(0.0)
    assert comp.score_growth_rate("eps_growth", 0.08).score == pytest.approx(70.0)
    assert comp.score_growth_rate("eps_growth", None).missing


def test_not_yet_available_is_honest() -> None:
    r = comp.not_yet_available("revision_trend", "MS8")
    assert r.missing and r.score == comp.NEUTRAL and "MS8" in r.detail
