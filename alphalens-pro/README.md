# AlphaLens Pro

Lokale Quant-Analyse-Plattform: ehrliches Backtesting, erklärbare Signale, manipulationssicheres Track-Record-Ledger, kalibrierte Wahrscheinlichkeiten, US + Europa, Paper-Trading statt Auto-Trading.

> **Kein Anlageberatungs-Tool.** AlphaLens Pro analysiert, signalisiert und führt Paper-Trades — es sendet **niemals** echte Orders.

Der vollständige Bauplan steht in [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).

## Voraussetzungen (macOS)

1. **Python 3.11+** — prüfen mit `python3 --version` (sonst: `brew install python`)
2. **Node.js 20+** — prüfen mit `node --version` (sonst: `brew install node`)

## Setup (einmalig)

```bash
cd alphalens-pro

# 1. Abhängigkeiten installieren (Python-venv + Frontend-Pakete)
make setup

# 2. API-Keys eintragen (optional — die Kursdaten laufen auch ohne Keys)
cp .env.example .env
open -e .env   # ANTHROPIC_API_KEY für KI-Features eintragen
```

| Key | Wofür | Pflicht? |
|---|---|---|
| `ANTHROPIC_API_KEY` | KI-Features (Deep-Dives, Chat, Sentiment) — Tagesbudget-Hard-Stop: 1 $ (in `config/ai.yaml`) | nur für KI-Features |
| `FINNHUB_API_KEY` | News + Earnings-Kalender (kostenlos: finnhub.io) | optional |
| `ALPHAVANTAGE_API_KEY` | Kursdaten-Fallback (kostenlos: alphavantage.co) | optional |

## Starten

```bash
make dev        # Backend (http://localhost:8000) + Frontend (http://localhost:5173)
```

## Daten laden

```bash
make update     # tägliches Voll-Update (Universum, Kurse, Fundamentals, Marktzustand)
make demo       # Schnelltest mit AAPL, SAP.DE, VWCE.DE
```

Der erste `make update` lädt ~700 Ticker mit 5 Jahren Historie — das dauert einige Minuten. Danach wird nur noch inkrementell nachgeladen. Ohne Internet läuft die Demo mit synthetischen Fixture-Daten: `.venv/bin/python -m backend.data.demo --offline`.

## Entwickeln

```bash
make test       # pytest mit Coverage
make lint       # Ruff
make typecheck  # mypy
```

## Konfiguration

Alles Fachliche liegt als YAML in `config/` und ist ohne Code-Änderung anpassbar: Universum & Watchlist (`universe.yaml`), Score-Gewichte (`scoring.yaml`), Signal-Parameter & Regime-Gate (`signals.yaml`), KI-Budget (`ai.yaml`), Transaktionskosten & Paper-Startkapital (`costs.yaml`), Zeitplan (`schedule.yaml`).
