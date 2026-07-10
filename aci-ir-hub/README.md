# ACI · IR Hub — Adaptive Corporate Intelligence (MVP)

A clickable MVP of the **first hub** from the "Adaptive Corporate Intelligence"
pitch: the Investor Relations beachhead (roadmap phase 0–6 months, one design
partner). It demonstrates the full product loop — agents prepare, humans
approve, and every workflow feeds the Decision Memory.

## Run it

Open `index.html` in a browser. No installation, no backend, no API key —
everything runs client-side. State (approvals, scenario runs, confirmations)
persists in `localStorage`; use **Reset demo data** in the sidebar to start over.

## What's inside — mapped to the pitch

| Pitch element (slide) | Where in the MVP |
|---|---|
| Morning priority list (9, 14) | **Morning Briefing** — "7 new mails · 3 need you today", P1–P3, one-click approval |
| Shared-inbox agent: triage, drafts, filing (9) | **Inbox Agent** — every mail classified with confidence, reply drafted, human approves or files |
| Statutory deadlines cannot slip (9, 15) | **Deadline Engine** — § 40 WpHG / Art. 19 MAR tracked in trading days, auto-escalation, MAR rumour case auto-escalated and blocked from direct reply |
| "3 decisions require attention" + AI readout (8) | **Dashboard** — decision cards with drivers and miss probability instead of 38 dashboards |
| Scenario Lab, computed to the capital market (8) | **Scenario Lab** — ARPU slider → revenue / EBITDA / EPS / vs. consensus / miss probability (calibrated to the deck's example: −2pp → −1.8% / −0.7pp / −€0.04 / −2.1%) |
| Preliminary numbers with confidence (7) | KPI tree tiles labeled **PRELIMINARY · 92%**, reconciled once official numbers land |
| Decision Memory as a by-product (10, 15) | **Decision Memory** — the "+12% price increase 2023" record; saving a scenario run creates a new record automatically; search answers "Why 12% and not 8%?" in seconds |
| Draft-and-confirm extraction (4, 15) | **Company Model** — extracted BUs, KPI definitions, decision rights with evidence + confidence; team confirms each element |
| Agents prepare, humans approve; audit trail (15) | **Audit Trail** — every agent action logged; no autonomous publication anywhere in the app |

## What is real vs. simulated

- **Real:** the product loop (triage → draft → approve → file → audit → memory),
  the deadline engine, the driver-based scenario model, draft-and-confirm,
  state persistence.
- **Simulated:** the AI outputs (drafts, readouts, extraction) are seeded, not
  produced by a live LLM, and the connectors (SAP, Salesforce, mailbox) are
  represented by seed data. That is deliberate for an MVP: the pitch itself
  argues the moat is the decision graph and the workflow, not the model —
  swapping the seeded drafts for live LLM calls behind the same
  `needs_approval` state machine is the next increment.

## Next increments (toward roadmap phase 2)

1. Backend with a real mailbox connector (IMAP/Graph) + LLM drafting behind the same approve gate.
2. Decision-graph store (the `companyModel` entities as a real graph) feeding the Scenario Lab sensitivities.
3. Reconciliation job: preliminary KPI vs. official close, writing the delta into Decision Memory.
