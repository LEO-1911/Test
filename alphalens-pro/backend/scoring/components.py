"""Teilkomponenten-Scorer: rohe Kennzahl -> Score 0–100 + Klartext-Begründung.

Transparenz-Regeln (USP 2):
- Jede Transformation ist eine benannte, dokumentierte, einzeln getestete Funktion.
- Peer-Vergleiche (Perzentilrang) nur, wenn genug Peers da sind (>= MIN_PEERS);
  sonst greift eine dokumentierte absolute Transformation oder — wo es keine
  seriöse gibt — ein ehrliches missing=True mit Neutralwert 50.
- Das "Why?"-Panel zeigt für jede Komponente: Rohwert, Score, Herkunft (detail)."""

from __future__ import annotations

from dataclasses import dataclass

MIN_PEERS = 5
NEUTRAL = 50.0


@dataclass(frozen=True)
class ComponentScore:
    name: str
    score: float  # 0-100
    raw_value: float | None
    missing: bool
    detail: str


def clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def percentile_rank(value: float, peers: list[float], *, higher_is_better: bool = True) -> float:
    """Perzentilrang von `value` innerhalb `peers` (0–100, Midrank bei Gleichstand)."""
    if not peers:
        return NEUTRAL
    less = sum(1 for p in peers if p < value)
    equal = sum(1 for p in peers if p == value)
    rank = 100.0 * (less + 0.5 * equal) / len(peers)
    return rank if higher_is_better else 100.0 - rank


def missing(name: str, reason: str) -> ComponentScore:
    return ComponentScore(name=name, score=NEUTRAL, raw_value=None, missing=True,
                          detail=f"fehlend: {reason} — neutral (50) gewertet")


# ---------------------------------------------------------------- Value

def score_multiple_vs_peers(
    name: str, value: float | None, peers: list[float], peer_label: str
) -> ComponentScore:
    """Bewertungs-Multiple (P/E, EV/EBITDA, P/B): niedriger = besser, Perzentil vs Peers."""
    if value is None or value <= 0:
        return missing(name, "kein positives Multiple verfügbar")
    if len(peers) < MIN_PEERS:
        return missing(name, f"nur {len(peers)} Peers ({peer_label}), mindestens {MIN_PEERS} nötig")
    score = percentile_rank(value, peers, higher_is_better=False)
    return ComponentScore(name, round(score, 1), value, False,
                          f"{value:.1f} vs. {len(peers)} Peers ({peer_label}): "
                          f"Perzentil {score:.0f} (niedriger = günstiger)")


def score_vs_own_history(name: str, value: float | None, history: list[float]) -> ComponentScore:
    """Aktuelles Multiple relativ zur eigenen Historie (Perzentil, niedriger = besser).
    Die Historie wächst mit jedem as_of-Snapshot — anfangs ehrlich 'fehlend'."""
    if value is None or value <= 0:
        return missing(name, "kein positives Multiple verfügbar")
    if len(history) < MIN_PEERS:
        return missing(name, f"erst {len(history)} historische Snapshots, {MIN_PEERS} nötig")
    score = percentile_rank(value, history, higher_is_better=False)
    return ComponentScore(name, round(score, 1), value, False,
                          f"{value:.1f} vs. eigene Historie ({len(history)} Snapshots): "
                          f"Perzentil {score:.0f}")


# ---------------------------------------------------------------- Quality

def score_roe(value: float | None) -> ComponentScore:
    """ROE (Dezimal): 0 % -> 0, 25 % -> 100, linear (clip)."""
    if value is None:
        return missing("roe", "ROE nicht verfügbar")
    score = clip(value * 100 * 4)
    return ComponentScore("roe", round(score, 1), value, False,
                          f"ROE {value * 100:.1f} % (25 % oder mehr = 100)")


def score_leverage(debt_to_ebitda: float | None) -> ComponentScore:
    """Debt/EBITDA: 0x -> 100, 5x -> 0, linear. Negatives EBITDA -> fehlend."""
    if debt_to_ebitda is None:
        return missing("leverage", "Debt/EBITDA nicht verfügbar")
    if debt_to_ebitda < 0:
        return missing("leverage", "negatives EBITDA — Kennzahl nicht interpretierbar")
    score = clip(100 - 20 * debt_to_ebitda)
    return ComponentScore("leverage", round(score, 1), debt_to_ebitda, False,
                          f"Debt/EBITDA {debt_to_ebitda:.2f}x (0x = 100, 5x = 0)")


def score_fcf_yield(fcf: float | None, market_cap: float | None) -> ComponentScore:
    """FCF-Konversion als FCF-Rendite (FCF/Marktkapitalisierung): 8 % -> 100, linear."""
    if fcf is None or market_cap is None or market_cap <= 0:
        return missing("fcf_conversion", "FCF oder Marktkapitalisierung nicht verfügbar")
    fcf_yield = fcf / market_cap
    score = clip(fcf_yield * 100 * 12.5)
    return ComponentScore("fcf_conversion", round(score, 1), fcf_yield, False,
                          f"FCF-Rendite {fcf_yield * 100:.1f} % (8 % oder mehr = 100)")


def score_margin_stability(margin_history: list[float]) -> ComponentScore:
    """Stabilität der Nettomarge: Standardabweichung der Marge (in Prozentpunkten)
    über die as_of-Historie. 0 pp -> 100, 5 pp -> 0, linear. Braucht >= 3 Snapshots."""
    if len(margin_history) < 3:
        return missing("margin_stability",
                       f"erst {len(margin_history)} Margen-Snapshots, 3 nötig")
    mean = sum(margin_history) / len(margin_history)
    var = sum((m - mean) ** 2 for m in margin_history) / (len(margin_history) - 1)
    std_pp = (var ** 0.5) * 100
    score = clip(100 - 20 * std_pp)
    return ComponentScore("margin_stability", round(score, 1), std_pp, False,
                          f"Margen-Streuung {std_pp:.2f} pp über "
                          f"{len(margin_history)} Snapshots (0 pp = 100)")


def score_roic(value: float | None) -> ComponentScore:
    """ROIC: 0 % -> 0, 20 % -> 100. yfinance liefert ROIC nicht — dann ehrlich fehlend."""
    if value is None:
        return missing("roic", "Datenquelle (yfinance) liefert ROIC nicht")
    score = clip(value * 100 * 5)
    return ComponentScore("roic", round(score, 1), value, False,
                          f"ROIC {value * 100:.1f} % (20 % oder mehr = 100)")


# ---------------------------------------------------------------- Momentum

def score_riskadj_return(
    name: str, value: float | None, peers: list[float]
) -> ComponentScore:
    """Risikoadjustierte Rendite (Rendite/Vol): Perzentil vs Peers; unter MIN_PEERS
    absolute Transformation 50 + 50*Wert (0 -> 50, +1.0 -> 100, -1.0 -> 0)."""
    if value is None:
        return missing(name, "zu wenig Kurshistorie für dieses Fenster")
    if len(peers) >= MIN_PEERS:
        score = percentile_rank(value, peers, higher_is_better=True)
        detail = f"Rendite/Vol {value:.2f}, Perzentil {score:.0f} vs. {len(peers)} Peers"
    else:
        score = clip(50 + 50 * value)
        detail = f"Rendite/Vol {value:.2f}, absolute Skala (nur {len(peers)} Peers)"
    return ComponentScore(name, round(score, 1), value, False, detail)


def score_dist_52w_high(dist: float | None) -> ComponentScore:
    """Abstand zum 52W-Hoch (<= 0): am Hoch -> 100, -25 % -> 50, -50 % -> 0."""
    if dist is None:
        return missing("dist_52w_high", "zu wenig Kurshistorie")
    score = clip(100 + 200 * dist)
    return ComponentScore("dist_52w_high", round(score, 1), dist, False,
                          f"{dist * 100:.1f} % unter 52W-Hoch (am Hoch = 100, -50 % = 0)")


def score_ma_signal(close: float | None, ma50: float | None, ma200: float | None) -> ComponentScore:
    """Diskretes Trendsignal: Kurs>MA50>MA200 -> 100; Kurs>MA200 -> 66;
    Kurs>MA50 -> 33; sonst 0."""
    if close is None or ma50 is None or ma200 is None:
        return missing("ma_signal", "zu wenig Kurshistorie für MA50/MA200")
    if close > ma50 > ma200:
        score, label = 100.0, "Kurs > MA50 > MA200 (intakter Aufwärtstrend)"
    elif close > ma200:
        score, label = 66.0, "Kurs > MA200, aber unter MA50"
    elif close > ma50:
        score, label = 33.0, "Kurs > MA50, aber unter MA200"
    else:
        score, label = 0.0, "Kurs unter MA50 und MA200 (Abwärtstrend)"
    return ComponentScore("ma_signal", score, close, False, label)


def score_rsi(value: float | None) -> ComponentScore:
    """RSI(14) direkt als Momentum-Score (0–100). Bewusst simpel und transparent;
    Überkauft-Warnungen übernimmt die Signal-Engine (MS5), nicht der Score."""
    if value is None:
        return missing("rsi", "zu wenig Kurshistorie für RSI(14)")
    return ComponentScore("rsi", round(value, 1), value, False, f"RSI(14) = {value:.0f}")


# ---------------------------------------------------------------- Growth

def score_growth_rate(name: str, value: float | None) -> ComponentScore:
    """Wachstumsrate (Dezimal): 0 % -> 50, +20 % -> 100, -20 % -> 0, linear."""
    if value is None:
        return missing(name, "Wachstumsrate nicht verfügbar")
    score = clip(50 + value * 100 * 2.5)
    return ComponentScore(name, round(score, 1), value, False,
                          f"Wachstum {value * 100:+.1f} % (±20 % = 100/0)")


def not_yet_available(name: str, source_milestone: str) -> ComponentScore:
    """Komponenten, deren Datenquelle erst in einem späteren Meilenstein kommt
    (z.B. Analysten-Revisionen, Surprise-Historie ab MS8)."""
    return missing(name, f"Datenquelle kommt in {source_milestone}")
