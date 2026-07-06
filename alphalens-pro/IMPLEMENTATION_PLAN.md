# AlphaLens Pro — Implementierungsplan

**Stand:** 2026-07-06 · **Branch:** `claude/alphalens-pro-strategy-spe3uh` · **Status:** Zur Freigabe durch den Auftraggeber

Lokale Quant-Analyse-Plattform im Stil von Intellectia AI — aber methodisch ehrlich: Point-in-Time-Backtests, volle Erklärbarkeit, manipulationssicheres Track-Record-Ledger, kalibrierte Wahrscheinlichkeiten, Risk-first-Signale, US + Europa, Paper-Trading statt Auto-Trading.

---

## 0. Leitprinzipien (nicht verhandelbar)

Diese acht Regeln sind als technische Invarianten in Code und Tests verankert — nicht als Marketing-Text:

1. **Ehrliches Backtesting** — Point-in-Time-Daten, Walk-Forward, Kosten modelliert, In-Sample/Out-of-Sample strikt getrennt. Wenn eine Strategie 8 % p.a. schafft, zeigen wir 8 %.
2. **Volle Erklärbarkeit** — jedes Signal bis auf Rohdatenpunkte rückverfolgbar ("Why this signal?"-Panel überall).
3. **Unbestechliches Ledger** — jedes Signal bei Entstehung mit Zeitstempel + Preis in eine append-only Hash-Chain; automatische Auswertung gegen die reale Kursentwicklung.
4. **Risk-first** — kein "Buy" ohne Positionsgröße, Stop-Loss, Portfolio-Impact und Regime-Gate.
5. **Kalibrierte Wahrscheinlichkeiten** — Prognosen immer als Prozentzahl, laufend gegen die Realität kalibriert (Brier-Score, Reliability-Diagramm). Bei zu wenig Historie: ehrliches "unkalibriert"-Badge statt Scheinpräzision.
6. **US + Europa** — S&P 500, Nasdaq 100, DAX 40, MDAX, EuroStoxx 50, UCITS-ETFs; EUR-Basis für den deutschen Anleger.
7. **Lokal & kostenarm** — nur kostenlose Daten-APIs; Claude-API mit hartem Tagesbudget; Daten bleiben auf dem Rechner.
8. **Niemals echte Orders** — Paper-Trading beweist das System, bevor Geld bewegt wird. Disclaimer im UI.

---

## 1. Architektur

### Stack

| Schicht | Technologie |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (SQLite), Pydantic v2, APScheduler |
| Frontend | React 18 + Vite + TypeScript, TailwindCSS, lightweight-charts (Kurscharts), Recharts (übrige Diagramme) |
| KI | Anthropic API: `claude-haiku-4-5` (Routine), `claude-sonnet-5` (Deep-Dives, Chat) |
| Daten | yfinance (primär), Finnhub Free (News/Earnings), Alpha Vantage (Fallback), SEC EDGAR, Senate/House Stock Watcher |
| Tests/Qualität | pytest + coverage, mypy (strict für scoring/backtest), Ruff |

### Komponenten & Datenfluss

```
   yfinance / Finnhub / AlphaVantage / EDGAR / StockWatcher
        │  (Provider-Interface + Adapter, Cache, Backoff)
        ▼
 ┌─ backend/data ────────┐   täglicher Job (APScheduler, werktags 07:30)
 │ SQLite, alles mit     │──► Scoring-Engine ──► Signal-Engine ──► KI-Analyse
 │ as_of-Zeitstempel     │        │                  │        (Haiku/Sonnet,
 └───────────────────────┘        │                  │         Budget-Gate)
                                  ▼                  ▼
                          Track-Record-Ledger (append-only, Hash-Chain)
                                  │                  │
                                  ▼                  ▼
                          Paper-Portfolio      Daily Brief
                                  │                  │
                                  └──── FastAPI (REST + WebSocket) ────► React-UI
```

### Projektstruktur

```
alphalens-pro/
├── Makefile                 # make dev / make test / make lint / make update
├── README.md                # Laien-Setup: .env, API-Keys, Start
├── .env.example
├── config/
│   ├── universe.yaml        # Indizes, ETF-Liste, Watchlist, Krypto
│   ├── scoring.yaml         # alle Gewichte & Schwellen der 4 Säulen + Risiko-Score
│   ├── signals.yaml         # Signaltyp-Parameter, Regime-Gate-Schwellen, Kelly-Cap
│   ├── ai.yaml              # Modelle, Tagesbudget (Hard-Stop), Batch-Größen
│   ├── costs.yaml           # Spread/Gebühren-Defaults für Backtest & Paper-Trading
│   └── schedule.yaml        # Job-Zeiten, Stale-Data-Schwelle, SMTP (default: aus)
├── backend/
│   ├── data/                # Provider-Interface, Adapter, Cache, Universum, FX
│   ├── scoring/             # Value/Quality/Momentum/Growth + Risiko-Score
│   ├── signals/             # 4 Signaltypen, Regime-Gate, Positionsgrößen
│   ├── ai/                  # Claude-Client, Budget-Guard, Prompts, Caching
│   ├── backtest/            # PIT-Engine, Walk-Forward, Kennzahlen, Reports
│   ├── ledger/              # Hash-Chain, Outcome-Auswertung, Kalibrierung
│   ├── jobs/                # Scheduler, Daily-Update-Pipeline, Daily Brief
│   └── api/                 # FastAPI-Router, WebSocket, Pydantic-Schemas
├── frontend/
│   └── src/ (pages/, components/, lib/)   # Sidebar-Navigation, 12 Seiten
└── tests/                   # Spiegel der Backend-Struktur, Golden-Value-Tests
```

---

## 2. Datenmodell & Point-in-Time-Disziplin

**Grundregel:** Jede Kennzahl wird mit zwei Zeitachsen gespeichert — `period` (worauf sie sich bezieht, z.B. Q1/2026) und `as_of` (wann wir sie kannten). Scoring, Signale und Backtests dürfen nur Daten mit `as_of <= t` verwenden. Das ist die technische Absicherung gegen Lookahead-Bias und wird per Unit-Test erzwungen.

Kerntabellen (SQLite):

| Tabelle | Inhalt |
|---|---|
| `instruments` | Ticker, Name, Börse, Währung, Sektor, Index-Zugehörigkeit (mit Gültigkeitszeitraum → mildert Survivorship-Bias ab dem Start) |
| `prices_daily` | OHLCV, adjustiert + unadjustiert, 5 Jahre Backfill |
| `fundamentals` | P/E, PEG, P/B, EV/EBITDA, Margen, Wachstum, Debt/EBITDA, FCF, ROIC — je `(ticker, metric, period, as_of)` |
| `earnings` | Termine, Schätzungen, Actuals, Beat/Miss-Historie, Kursreaktion |
| `news` | Headlines mit Hash (Dedup), Haiku-Sentiment, `as_of` |
| `market_state` | VIX, Marktbreite (% über MA200), Index-Trends, EURUSD |
| `scores` | Composite + alle Teilkomponenten einzeln (→ Erklärbarkeit), je `as_of` |
| `ledger_entries` | append-only Hash-Chain (siehe §5) |
| `paper_*` / `portfolio_*` | Paper-Trades, echte Positionen, Bewertungen |

**Ehrlichkeit bei historischen Daten:** Kostenlose Quellen liefern für die Vergangenheit nur die *heutige* Indexzusammensetzung (Survivorship-Bias) und teils revidierte Fundamentals. Wir können das nicht wegzaubern — also: (a) ab Projektstart bauen wir unsere eigene, saubere PIT-Historie auf, (b) jeder Backtest-Report zeigt ein verpflichtendes **"Data Caveats"-Panel**, das genau ausweist, welche Bias-Quellen im getesteten Zeitraum stecken. Das ist USP 1 in der Praxis: lieber ein ehrlicher Backtest mit ausgewiesenen Grenzen als eine erfundene 200-%-Kurve.

---

## 3. Meilensteine

Reihenfolge wie vorgegeben. Jeder Meilenstein endet mit einer lauffähigen Demo (Referenz-Ticker: **AAPL, SAP.DE, VWCE.DE**) und grünen Tests. Aufwand in "Sessions" (eine Session ≈ ein konzentrierter Arbeitsblock).

### MS0 — Fundament (1 Session)
- Projekt-Scaffold wie oben, `make dev` startet Backend (uvicorn) + Frontend (Vite) mit einem Befehl.
- Tooling: Ruff, mypy, pytest, Coverage-Gate; `.env`-Handling; Logging; SQLite-Setup mit Alembic-Migrationen.
- Alle YAML-Configs mit dokumentierten Defaults angelegt.
- **Demo:** `make dev` → dunkles Dashboard-Grundgerüst mit Sidebar erreichbar unter `localhost:5173`.

### MS1 — M1: Datenpipeline & Universum (2 Sessions)
- Provider-Interface (`MarketDataProvider`, `NewsProvider`, `EarningsProvider`) + Adapter yfinance/Finnhub/AlphaVantage; später einsteckbar: Polygon/FMP.
- Universum-Loader: S&P 500, Nasdaq 100, DAX 40, MDAX, EuroStoxx 50 (~650–700 eindeutige Ticker), kuratierte ETF-Liste (VWCE, IWDA, EUNL, SPY, QQQ …), BTC/ETH optional, manuelle Watchlist.
- Einmaliger 5-Jahres-Backfill (OHLCV, batched), danach täglich inkrementell. Fundamentals rollierend (~1/7 des Universums pro Tag) + eventgetrieben nach Earnings. VIX, Marktbreite, EURUSD täglich.
- SQLite-Cache, Exponential Backoff, Rate-Limit-Buchhaltung pro Provider; Ausfall eines Tickers → skip + log, nie Crash. Stale-Data-Erkennung.
- **Demo:** CLI `python -m backend.data.demo AAPL SAP.DE VWCE.DE` zeigt frische Kurse, Fundamentals mit `as_of`, Cache-Hit beim zweiten Lauf. Voll-Update des Universums < 15 min.

### MS2 — M2: Quant-Scoring-Engine (2 Sessions)
- Composite Score 0–100: **Value 30 %** (Multiples relativ zu Sektor-Median und eigener 5J-Historie), **Quality 25 %** (ROE, ROIC, Margenstabilität, Verschuldung, FCF-Konversion), **Momentum 25 %** (3/6/12M risikoadjustiert, 52W-Hoch-Abstand, MA-Signale, RSI), **Growth 20 %** (Umsatz-/EPS-Wachstum, Revisionen, Surprise-Historie). Gewichte aus `scoring.yaml`.
- Risiko-Score 1–10 (Volatilität, Max Drawdown, Beta, Bilanzrisiko, Liquidität; ETFs: TER, Diversifikation, Tracking-Differenz).
- Jede Teilkomponente einzeln persistiert und per API abfragbar → Grundlage für das "Why?"-Panel.
- **Tests:** Golden-Value-Unit-Tests für *jede* Komponente (bekannte Eingaben → erwartete Werte), Ziel ≥ 80 % Coverage in `scoring/`. Fehlende Datenpunkte → Neutralwert + Kennzeichnung, nie stiller Ausfall.
- **Demo:** Score-Breakdown für AAPL, SAP.DE, VWCE.DE als Tabelle mit allen Teilwerten.

### MS3 — M11-Kern: Ledger & Kalibrierungs-Infrastruktur (1–2 Sessions) — bewusst früh
- `ledger_entries(id, ts_utc, entry_type, ticker, payload_json, price_at_creation, prev_hash, entry_hash)` mit `entry_hash = SHA-256(prev_hash ‖ kanonisches JSON)`. UPDATE/DELETE per SQLite-Trigger blockiert; `verify`-Endpoint rechnet die Kette komplett nach. Outcomes werden als *neue verkettete Einträge* geschrieben, nie durch Mutation.
- Outcome-Evaluator-Job: offene Einträge gegen Kursverlauf auswerten (Stop/Ziel/Zeitfenster) → Hit-Rate, Ø-Rendite pro Signaltyp, Brier-Score.
- Kalibrierungs-Modul: rollierende Trefferquoten mit Laplace-Glättung; ab n ≥ 200 pro Signaltyp isotonische Regression; darunter ehrliches "unkalibriert (n=…)"-Badge. Reliability-Diagramm-Daten als API.
- **Demo:** Testsignal einbuchen → Manipulationsversuch an der DB → `verify` schlägt Alarm; simulierte Outcomes → Brier-Score erscheint.

### MS4 — API + Frontend-Grundgerüst (2 Sessions)
- FastAPI-Router: Universum, Kurse, Scores, Ledger, Health; WebSocket/Polling für Live-Updates während der Handelszeiten.
- UI im Intellectia-Look, aber Terminal-Seriosität: Dark Mode (Default), Inter, Karten-Layout, Grün/Rot-Signalfarben, Electric-Blue-Akzent, **jede Zahl mit Quelle + `as_of` im Tooltip**, Stale-Data-Badge, Disclaimer-Footer.
- Seiten: Märkte-Übersicht, tabellarischer Screener (Filter/Sortierung auf lokaler DB), Instrument-Detailseite (lightweight-charts-Kurschart, Score-Breakdown aufklappbar = "Why?"-Panel v1), Track-Record-Rohansicht.
- **Demo:** Im Browser durch AAPL/SAP.DE/VWCE.DE navigieren, Scores aufklappen, Screener filtern.

### MS5 — M4 Signal-Engine + M3 Stock Picker (2–3 Sessions)
- Vier Long-Setups: Mean-Reversion (RSI-Oversold im Aufwärtstrend), Breakout (52W-Hoch mit Volumen), Pullback-auf-MA50 im Trend, Earnings-Momentum. Jedes Signal: Entry-Zone, ATR-Stop, Zielzone, kalibrierte Erfolgswahrscheinlichkeit (aus MS3), Positionsgröße, "Why?"-Panel mit konkreten Datenpunkten.
- **Positionsgröße:** Fractional Kelly (Faktor 0,25) auf Basis kalibrierter Wahrscheinlichkeit und Payoff-Verhältnis, volatilitätsskaliert, hart gekappt bei 25 % — Formel und alle Parameter in `signals.yaml`.
- **Regime-Gate:** Komposit aus VIX-Niveau/-Perzentil, Marktbreite (% Universum über MA200), Index-Trend (S&P 500 & EuroStoxx vs. MA200) → Risk-on / Neutral / Risk-off mit Skalierungsfaktoren 1,0 / 0,6 / 0,25 auf alle Long-Positionsgrößen. Begründung wird angezeigt.
- **Stock Picker:** montags vor US-Open — Quant-Score-Ranking → Regime-Gate → Sonnet-Deep-Dive der Top-Kandidaten (These, Bull/Bear, Katalysatoren, Konfidenz). Jeder Pick sofort ins Ledger; kumulative Performance aller bisherigen Wochen gegen S&P 500 (EUR-bereinigt) auf der Picker-Seite.
- **Tests:** Signal-Logik mit synthetischen Kursreihen (konstruierte Setups müssen feuern / nicht feuern), Kelly- und Gate-Berechnung mit Golden Values.
- **Demo:** Tagessignale mit vollständigem Risiko-Kontext im UI; ein kompletter Montags-Lauf.

### MS6 — M9 Backtesting Playground (2–3 Sessions, kritischster Code)
- Engine: Point-in-Time-Joins, Walk-Forward (Parameter nur auf Trainingsfenster fitten, auf Folgefenster anwenden), Kosten-Modell (Spread + Gebühren aus `costs.yaml`, Default realistisch), Benchmark-Vergleich.
- Kennzahlen: CAGR, Sharpe, Sortino, Max Drawdown, Hit-Rate, Turnover, Equity-Kurve — **jede mit Block-Bootstrap-Konfidenzintervall**.
- Overfitting-Warnung: Heuristik aus Parameteranzahl vs. Anzahl unabhängiger Beobachtungen, Warnung bei zu kurzem Zeitraum; Hinweis auf Multiple-Testing bei vielen Läufen. Verpflichtendes Data-Caveats-Panel (§2).
- UI: Strategie wählen (Score-Ranking, Signaltypen, Filter-Kombis), Zeitraum, Rebalancing, Kosten; Report speicherbar.
- **Tests:** Ziel ≥ 80 % Coverage in `backtest/`; Anti-Lookahead-Test (Engine mit absichtlich "geleakten" Zukunftsdaten muss den Zugriff verweigern); deterministische Mini-Backtests mit bekanntem Ergebnis.
- **Demo:** "Top-Dezil Composite Score, monatliches Rebalancing, 2021–2026" mit ehrlichen Zahlen inkl. Konfidenzintervallen und Caveats.

### MS7 — M10 Paper-Portfolio & echtes Portfolio (1–2 Sessions)
- Paper-Portfolio führt ab Aktivierung jedes Signal/jeden Pick automatisch virtuell aus (inkl. Slippage aus `costs.yaml`), P&L laufend vs. Benchmark, EUR-Basis. Das ist der Live-Beweis (USP 8) und speist die Equity-Kurve auf der Track-Record-Seite.
- Echtes Portfolio: manuelle Erfassung mit Einstandskurs; P&L, Portfolio-Risiko-Score, Klumpen-/Korrelationsanalyse, Alert wenn ein Halten auf Sell dreht.
- **Demo:** Nach ein paar Tagen Laufzeit: Paper-P&L vs. S&P 500; ein manuell erfasstes Depot mit Risikoanalyse.

### MS8 — M7 Earnings Center + M8 Pattern Detection (2 Sessions)
- Earnings: Kalender (Universum + Watchlist); je Termin kalibrierte Beat-Wahrscheinlichkeit (logistische Regression auf Surprise-Historie, Revisionstrend, Sektor-Momentum; Walk-Forward-Refit quartalsweise), erwartete Kursreaktion aus historischen Earnings-Moves, Sonnet-Preview. Nach Earnings automatische Auswertung → fließt in Kalibrierung (MS3).
- Patterns algorithmisch: Support/Resistance, Trendkanäle, Golden/Death Cross, Double Bottom/Top, vereinfachtes Cup-and-Handle, Volumen-Anomalien. Jedes Muster mit Trefferquote aus *unserem eigenen* Backtest — steht im UI auch dann, wenn sie ernüchternd ist.
- **Demo:** Earnings-Woche mit Wahrscheinlichkeiten; erkannte Muster auf AAPL/SAP.DE-Charts mit historischer Hit-Rate.

### MS9 — M6 Whales & Insider (1–2 Sessions)
- SEC EDGAR Form 4 (Insider-Trades, Cluster-Buys hervorgehoben), 13F-Änderungen großer Fonds (quartalsweise), Congress-Trades (Senate/House Stock Watcher JSON).
- Ehrlichkeit: **Reporting-Lag prominent** ("Trade war vor 21 Tagen") + Backtest, ob Follow-the-Whale nach Lag überhaupt noch Alpha liefert — Ergebnis transparent im UI, egal wie es ausfällt.
- **Demo:** Whales-Seite mit Lag-Anzeige und Alpha-Backtest-Fazit.

### MS10 — M5 AI-Screener + M12 Chat-Agent (2 Sessions)
- AI-Screener: Freitext → Haiku übersetzt in strukturierte Filter (JSON-Schema-validiert) → **Filter werden dem Nutzer zur Bestätigung angezeigt** (kein Black-Box-Query) → lokale Filter-Engine → Ergebnistabelle. Presets speicherbar.
- Chat-Agent "Alphio, aber ehrlich": Sonnet mit Tool-Zugriff auf die lokale DB (Kurse, Scores, Signale, News, Portfolio). Antworten zitieren konkrete Datenpunkte mit `as_of`; ohne Datengrundlage sagt der Agent "weiß ich nicht". System-Prompt gecacht (Prompt Caching), Budget-Guard aktiv.
- **Demo:** "Profitable Tech-Werte unter P/E 20 mit steigendem Momentum" → bestätigte Filter → Ergebnis; Chat: "Vergleiche NVDA und AMD", "Wie riskant ist mein Portfolio?".

### MS11 — M13 Daily Brief + Scheduler + Politur (1–2 Sessions)
- Werktags 07:30 (konfigurierbar): Datenupdate → Scores → Signale → KI → Brief. Inhalt: Marktregime mit Begründung, 3–5 Top-Ideen mit Ein-Satz-These + Wahrscheinlichkeit, Änderungen zu gestern, Portfolio-Warnungen, heutige Earnings/Makro-Events. Im Dashboard; optional E-Mail (SMTP, default aus).
- Politur: Coverage-Gates final prüfen, mypy-clean, README für Laien (Schritt-für-Schritt inkl. .env und API-Keys), Performance-Check Voll-Update < 15 min.

**Gesamtaufwand: ~17–22 Sessions.** Ab MS5 produziert das System echte, geloggte Signale — der Track Record beginnt zu laufen, während spätere Meilensteine gebaut werden.

---

## 4. KI-Kostenkontrolle (USP 7)

Modelle und Preise (Stand Juli 2026, pro 1 Mio. Tokens):

| Aufgabe | Modell | Preis (Input/Output) | Frequenz |
|---|---|---|---|
| News-Sentiment, Klassifikation, Screener-Übersetzung | `claude-haiku-4-5` | $1 / $5 | täglich, gebatcht |
| Deep-Dives Top-Kandidaten, Daily-Brief-Text, Chat | `claude-sonnet-5` | $3 / $15 (bis 31.08.2026: $2 / $10) | wöchentlich / täglich 1× / on-demand |

Kostenmechanik in `backend/ai/`:
- **Budget-Guard:** jeder API-Call bucht geschätzte Kosten (Token-Zählung) gegen ein Tagesbudget aus `ai.yaml`; bei Überschreitung **Hard-Stop** — KI-Features zeigen "Budget erschöpft", alle Quant-Features laufen uneingeschränkt weiter. Kosten-Zähler im UI (Einstellungen).
- **Nur bei Datenänderung analysieren:** Analysen werden mit Input-Hash gecacht; unveränderte News/Fundamentals → kein neuer Call.
- **Batching:** News-Sentiment gesammelt 1× täglich über die Batches-API (−50 %); Prompt Caching für den Chat-System-Prompt und Deep-Dive-Vorlagen.

**Erwartete Kosten:** ~$0,10–0,20/Tag Routine + ~$0,35/Woche Deep-Dives + Chat nach Nutzung (~$0,02–0,05 pro Frage) → realistisch **$5–10/Monat**. Default-Tagesbudget: **$1,00 Hard-Stop** (änderbar in `ai.yaml`).

---

## 5. Rate-Limits & Performance (Free-Tier-Realität)

| Quelle | Limit | Strategie |
|---|---|---|
| yfinance | inoffiziell, drosselt bei Missbrauch | Batch-Downloads (~100 Ticker/Request), täglich nur inkrementell, 5J-Backfill einmalig, Cache |
| Finnhub Free | 60 Calls/min | nur News + Earnings-Kalender, nur Watchlist + Top-Kandidaten |
| Alpha Vantage Free | 25 Requests/Tag | reiner Fallback, nie im Regelbetrieb |
| SEC EDGAR | 10 Req/s, User-Agent-Pflicht | 1 täglicher Job, konservativ gedrosselt |
| Stock Watcher | statische JSON-Dumps | 1× täglich |

Priorisierung im Tagesbudget: Watchlist + gehaltene Positionen + Top-100-Scores immer zuerst; Rest des Universums rollierend. Ziel Voll-Update < 15 min wird in MS1 gemessen und ist Abnahmekriterium.

---

## 6. Methodische Kernentscheidungen

- **Kalibrierung:** Signalwahrscheinlichkeiten aus historischer Hit-Rate des jeweiligen Signaltyps (rollierendes Fenster, Laplace-Glättung), ab n ≥ 200 isotonische Regression. Earnings-Beat: logistische Regression, quartalsweiser Walk-Forward-Refit. Brier-Score und Reliability-Diagramm je Prognosetyp auf der Track-Record-Seite. Cold-Start wird nie kaschiert.
- **Positionsgrößen:** Kelly-Anteil `f = p − (1−p)/b` mit kalibriertem `p` und Payoff `b` aus Entry/Stop/Ziel; Fractional-Faktor 0,25; Skalierung auf Ziel-Volatilität; Cap 25 %; multipliziert mit Regime-Faktor.
- **Regime-Gate:** Risk-off, wenn ≥ 2 von 3 Kriterien reißen (VIX > 25 oder > 80. Perzentil 1J; Marktbreite < 40 %; Leitindex < MA200). Faktoren 1,0 / 0,6 / 0,25 — alles in `signals.yaml`.
- **Ledger:** SHA-256-Hash-Chain, Schreibschutz per DB-Trigger, `verify`-Endpoint. Kein nachträgliches Ändern — Korrekturen sind neue, verkettete Einträge.
- **Benchmark & Währung:** Alle Performance-Angaben in EUR; Benchmarks S&P 500 (EUR-bereinigt) und EuroStoxx 50 wählbar.
- **Backtest-Ehrlichkeit:** Walk-Forward statt Einmal-Fit, Kosten-Default konservativ (10 bp Spread US Large Caps / 20 bp EU Mid Caps + Gebührenmodell), Konfidenzintervalle statt Punktschätzungen, Data-Caveats-Panel verpflichtend.

---

## 7. Getroffene Defaults (alle in `config/` änderbar)

| Entscheidung | Default | Begründung |
|---|---|---|
| Claude-Tagesbudget | **$1,00 Hard-Stop** | deckt Normalbetrieb ~5-fach ab; schützt vor Runaway-Kosten |
| Modell-Split | Haiku 4.5 Routine / Sonnet 5 Deep-Dive+Chat | bestes Preis-Leistungs-Verhältnis je Aufgabe |
| Paper-Startkapital | **100.000 € virtuell** | genug für realistische Positionsgrößen bei 25-%-Cap |
| Universum | **voll** (~650–700 Ticker) ab Start | rollierende Fundamentals machen es Free-Tier-tauglich |
| Kelly-Faktor / Cap | 0,25 / 25 % | Branchenüblich konservativ; Cap wie von dir vorgegeben |
| Regime-Faktoren | 1,0 / 0,6 / 0,25 | Drosselung statt Abschaltung — Signale bleiben sichtbar |
| Kosten im Backtest | 10–20 bp Spread + Gebührenmodell | konservativ-realistisch für Privatanleger-Broker |
| Krypto | BTC + ETH aktiv (via yfinance) | von dir als optional genannt; kostenlos verfügbar |
| E-Mail-Versand | aus | erst aktivieren, wenn SMTP konfiguriert |

---

## 8. Offene Punkte (betreffen deine Kosten / dein Risiko)

1. **Tagesbudget Claude-API:** $1,00/Tag Hard-Stop okay? (≈ max. $30/Monat Worst Case, realistisch $5–10.)
2. **Paper-Startkapital:** 100.000 € virtuell okay? (Sollte grob deiner realen Größenordnung entsprechen, damit Positionsgrößen übertragbar sind.)
3. **Universum ab Start:** voll (~700 Ticker) oder schlanker Start (S&P 100 + DAX 40 + EuroStoxx 50 + ETFs ≈ 250 Ticker, schnellere Updates, später erweiterbar)?

Ohne Rückmeldung baue ich mit den Defaults aus §7 weiter — alles bleibt per YAML umstellbar.

---

## 9. Risiken & Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| yfinance-Instabilität (inoffizielle API) | Provider-Abstraktion, Fallback-Kette, Cache; Ausfall → Stale-Badge statt Crash |
| Survivorship-/Revisionsbias in Gratis-Historie | eigene PIT-Historie ab Start, Caveats-Panel, konservative Interpretation |
| Zu kleine Stichproben für Kalibrierung | Laplace-Glättung, "unkalibriert"-Badge, Mindest-n vor Kalibrierungs-Anspruch |
| Overfitting im Playground | Walk-Forward-Pflicht, Parameter-Warnung, Konfidenzintervalle, Multiple-Testing-Hinweis |
| KI-Kosten laufen davon | Budget-Guard mit Hard-Stop, Caching, Batching, Kosten-Anzeige im UI |
| Verwechslung Paper/Real | strikte Trennung in Schema und UI; das Tool kann technisch keine Orders senden |

---

## 10. Definition of Done (Projekt)

- [ ] `make dev` startet alles auf macOS; README von einem Laien nachvollziehbar
- [ ] Voll-Update < 15 min innerhalb der Free-Tier-Limits
- [ ] Coverage ≥ 80 % in `scoring/` und `backtest/`; mypy-clean; Ruff sauber
- [ ] Ledger-`verify` besteht; Manipulationstest schlägt nachweislich an
- [ ] Jede angezeigte Zahl hat Quelle + `as_of` im Tooltip; Stale-Badge funktioniert
- [ ] Jedes Signal: Wahrscheinlichkeit, Größe, Stop, Regime-Status, "Why?"-Panel
- [ ] Paper-Portfolio läuft automatisch; Track-Record-Seite zeigt echte Hit-Rate, Brier-Score, Reliability-Diagramm
- [ ] Kein Code-Pfad kann echte Orders auslösen; Disclaimer sichtbar
