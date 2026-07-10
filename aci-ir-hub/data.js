/* ============================================================
   Adaptive Corporate Intelligence — IR Hub MVP
   Seed data: everything an onboarded design partner would see
   on day one. In the real product this is produced by the
   CONNECT → UNDERSTAND pipeline; here it is seeded so the MVP
   runs standalone in a browser.
   ============================================================ */

const SEED = {

  company: {
    name: "Nordwerk SE",
    unit: "Investor Relations",
    fiscalYear: "FY26",
  },

  /* ---------- Inbox: the shared IR mailbox ---------- */
  emails: [
    {
      id: "m1",
      from: "J.P. Morgan Securities plc",
      fromEmail: "regulatory.notifications@jpmorgan.com",
      subject: "Voting rights notification pursuant to § 33 WpHG",
      received: "07:12",
      body: "Please find attached our notification of voting rights in Nordwerk SE. Our holding crossed the 5% threshold on the last trading day. Kindly confirm receipt and proceed with publication as required.",
      category: "Regulatory",
      priority: 1,
      confidence: 0.97,
      deadlineId: "d1",
      aiDraft:
        "Dear Sir or Madam,\n\nWe confirm receipt of your voting rights notification pursuant to § 33 WpHG dated today. Publication pursuant to § 40 WpHG has been initiated and will be completed within the statutory period of three trading days.\n\nKind regards\nInvestor Relations, Nordwerk SE",
      aiNote: "Threshold crossing detected (5%). Statutory publication workflow prepared — § 40 WpHG requires publication within 3 trading days. Deadline tracker armed, escalation to Head of IR at T-1.",
      status: "needs_approval",
    },
    {
      id: "m2",
      from: "Helena Brandt — Ardent Capital",
      fromEmail: "h.brandt@ardentcap.com",
      subject: "Question on Q2 gross margin bridge",
      received: "07:48",
      body: "Hi team, in the Q2 statement the gross margin declined 90bps QoQ but the bridge only explains ~60bps (mix + energy). What accounts for the remaining 30bps? Is this a one-off?",
      category: "Investor question",
      priority: 2,
      confidence: 0.93,
      deadlineId: null,
      aiDraft:
        "Dear Ms Brandt,\n\nThank you for your question. The remaining ~30bps of the Q2 gross margin decline relate to a temporary under-absorption effect from the planned maintenance shutdown in our Hamburg plant, as referenced on slide 14 of the Q2 deck. This effect is one-off in nature and reversed in July.\n\nAll figures are consistent with the approved Q2 Q&A library (item 4.2).\n\nBest regards\nInvestor Relations, Nordwerk SE",
      aiNote: "Answer assembled from the approved Q&A library (item 4.2, 'Q2 margin bridge'). No new disclosure — MAR-safe, all facts already public.",
      status: "needs_approval",
    },
    {
      id: "m3",
      from: "Berenberg Equity Conferences",
      fromEmail: "conferences@berenberg.de",
      subject: "Invitation: European MidCap Conference, 22–23 Sep, London",
      received: "08:03",
      body: "We would be delighted to welcome Nordwerk SE at this year's European MidCap Conference in London. Please let us know whether CEO/CFO participation is possible; 1:1 slots are allocated first-come-first-served.",
      category: "Conference",
      priority: 3,
      confidence: 0.95,
      deadlineId: null,
      aiDraft:
        "Dear Berenberg team,\n\nThank you for the invitation. Nordwerk SE is pleased to participate in the European MidCap Conference on 22–23 September. Our CFO is provisionally available on 22 September; we kindly ask for a 1:1 schedule focused on that day.\n\nA calendar hold has been placed pending final confirmation.\n\nBest regards\nInvestor Relations, Nordwerk SE",
      aiNote: "CFO calendar checked: 22 Sep free, 23 Sep conflicts with Supervisory Board pre-meeting. Calendar hold created. Roadshow planner updated.",
      status: "needs_approval",
    },
    {
      id: "m4",
      from: "Marc-Oliver Fassbender — Kepler Cheuvreux",
      fromEmail: "mfassbender@keplercheuvreux.com",
      subject: "Model update — capex phasing FY26/27",
      received: "08:20",
      body: "Updating my model ahead of the CMD. Could you help me understand the capex phasing between FY26 and FY27 for the Iberia expansion? Guidance says 'weighted to FY27' — is 40/60 a fair split?",
      category: "Analyst question",
      priority: 2,
      confidence: 0.88,
      deadlineId: null,
      aiDraft:
        "Dear Mr Fassbender,\n\nAs communicated at the Q2 call, capex for the Iberia expansion is weighted towards FY27. We do not guide on the precise split; historical phasing of comparable projects (see FY23 annual report, p. 87) has been in the range you describe. Please treat this as directional, not guidance.\n\nBest regards\nInvestor Relations, Nordwerk SE",
      aiNote: "Caution: request approaches selective disclosure. Draft stays strictly within published material and flags it as directional. Consider routing to Head of IR before sending.",
      status: "needs_approval",
    },
    {
      id: "m5",
      from: "Peter Gruber (private shareholder)",
      fromEmail: "p.gruber1958@gmx.de",
      subject: "Dividend for fiscal year 2026?",
      received: "08:41",
      body: "As a long-standing shareholder I would like to know whether the dividend will be raised again this year. The peers are all paying more.",
      category: "Retail shareholder",
      priority: 3,
      confidence: 0.96,
      deadlineId: null,
      aiDraft:
        "Dear Mr Gruber,\n\nThank you for your message and your loyalty as a shareholder. Nordwerk SE pursues a dividend policy of distributing 40–50% of adjusted net income. The dividend proposal for FY26 will be published with the annual results in February and decided by the Annual General Meeting in May.\n\nBest regards\nInvestor Relations, Nordwerk SE",
      aiNote: "Standard reply generated from dividend policy (public). Filed under 'Retail correspondence'.",
      status: "needs_approval",
    },
    {
      id: "m6",
      from: "Finanz-Szene Redaktion",
      fromEmail: "redaktion@finanz-szene.de",
      subject: "PRESS: market rumour on Iberia divestment — request for comment by 12:00",
      received: "08:55",
      body: "We are hearing from two independent sources that Nordwerk is exploring a sale of its Spanish unit. We intend to publish today and ask for a statement by 12:00.",
      category: "Media / escalation",
      priority: 1,
      confidence: 0.91,
      deadlineId: "d4",
      aiDraft:
        "— NOT FOR DIRECT REPLY —\n\nEscalation memo for Head of IR & Corporate Communications:\nMedia inquiry from Finanz-Szene on an alleged Iberia divestment, deadline 12:00. Ad-hoc relevance must be assessed (Art. 17 MAR). Recommended holding statement: 'As a matter of principle, Nordwerk SE does not comment on market rumours.' No substantive reply from IR without Comms/Legal sign-off.",
      aiNote: "Rumour touches potential inside information (Art. 17 MAR). Auto-escalated to Head of IR and Corporate Communications at 08:55. Reply is blocked pending sign-off — the agent prepares, humans decide.",
      status: "escalated",
    },
    {
      id: "m7",
      from: "Dr. Anne Kessler — CFO Office",
      fromEmail: "a.kessler@nordwerk.example",
      subject: "Consensus overview before Thursday's ExCo",
      received: "09:10",
      body: "Can I get the current sell-side consensus vs. our internal FY26 view before Thursday? Ideally with the two or three largest deviations flagged.",
      category: "Internal request",
      priority: 2,
      confidence: 0.94,
      deadlineId: null,
      aiDraft:
        "Hi Anne,\n\nattached is the current consensus overview (14 estimates, updated this morning):\n\n• Revenue FY26: consensus €4,213m vs. internal €4,200m (+0.3% above internal)\n• EBITDA margin: consensus 31.9% vs. internal 31.5% (+0.4pp above internal)\n• Largest deviations: Kepler (revenue +4.2% above internal), HSBC (margin +0.9pp above internal)\n\nThe dispersion is driven mainly by Professional-segment ARPU assumptions — see the readout in the Leadership dashboard, Decision 1.\n\nBest, IR",
      aiNote: "Consensus assembled automatically from the estimates database; deviation analysis links to Decision 1 on the leadership dashboard.",
      status: "needs_approval",
    },
  ],

  /* ---------- Deadline engine ---------- */
  deadlines: [
    {
      id: "d1",
      title: "Publish voting rights notification (J.P. Morgan)",
      legalBasis: "§ 40 WpHG — within 3 trading days",
      dueInTradingDays: 2,
      severity: "critical",
      state: "Workflow prepared — awaiting approval",
      escalation: "Escalates to Head of IR at T-1, to CFO on due date",
      sourceEmail: "m1",
    },
    {
      id: "d2",
      title: "Q3 quarterly statement — publication",
      legalBasis: "Exchange rules / financial calendar",
      dueInTradingDays: 34,
      severity: "normal",
      state: "On track — draft in Controlling",
      escalation: "Escalates to Head of IR at T-10",
      sourceEmail: null,
    },
    {
      id: "d3",
      title: "Managers' transactions notification (COO share purchase)",
      legalBasis: "Art. 19 MAR — within 3 business days",
      dueInTradingDays: 3,
      severity: "high",
      state: "Data received — filing drafted",
      escalation: "Escalates to Head of IR at T-1",
      sourceEmail: null,
    },
    {
      id: "d4",
      title: "Ad-hoc assessment: Iberia rumour (Art. 17 MAR)",
      legalBasis: "Art. 17 MAR — without undue delay",
      dueInTradingDays: 0,
      severity: "critical",
      state: "ESCALATED — with Head of IR, Comms & Legal since 08:55",
      escalation: "Active now — decision required before 12:00 media deadline",
      sourceEmail: "m6",
    },
  ],

  /* ---------- Leadership: KPI tree ---------- */
  /* "Preliminary" = computed by agents straight from source systems,
     clearly labeled with confidence, reconciled once official numbers land. */
  kpis: [
    {
      id: "k1", name: "Revenue FY26 (run-rate)", value: "€4,168m", plan: "€4,200m",
      deltaPct: -0.8, preliminary: true, confidence: 0.92,
      spark: [3980, 4010, 4055, 4090, 4120, 4135, 4150, 4168],
      children: [
        { name: "Germany", value: "€2,251m", deltaPct: -1.9, note: "ARPU below plan" },
        { name: "Spain", value: "€917m", deltaPct: +2.4, note: "customer growth above plan" },
        { name: "Professional", value: "€1,000m", deltaPct: -1.2, note: "adoption slower" },
      ],
    },
    {
      id: "k2", name: "EBITDA margin", value: "31.1%", plan: "31.5%",
      deltaPct: -0.4, deltaUnit: "pp", preliminary: true, confidence: 0.89,
      spark: [30.2, 30.5, 30.9, 31.2, 31.4, 31.3, 31.2, 31.1],
      children: [
        { name: "Gross margin", value: "54.0%", deltaPct: -0.3, note: "energy + mix" },
        { name: "Opex ratio", value: "22.9%", deltaPct: -0.1, note: "in line" },
      ],
    },
    {
      id: "k3", name: "Net ARPU Germany", value: "€23.10", plan: "€23.80",
      deltaPct: -2.9, preliminary: true, confidence: 0.94,
      spark: [23.9, 23.8, 23.7, 23.6, 23.4, 23.3, 23.2, 23.1],
      children: [
        { name: "Consumer", value: "€19.40", deltaPct: -1.1, note: "stable" },
        { name: "Professional", value: "€41.20", deltaPct: -4.8, note: "discounting in renewals" },
      ],
    },
    {
      id: "k4", name: "Customers Spain", value: "1.84m", plan: "1.79m",
      deltaPct: +2.8, preliminary: false, confidence: 1.0,
      spark: [1.62, 1.66, 1.70, 1.73, 1.76, 1.79, 1.82, 1.84],
      children: [
        { name: "Gross adds (Q)", value: "96k", deltaPct: +8.1, note: "campaign effect" },
        { name: "Churn (Q)", value: "1.9%", deltaPct: -0.2, note: "improving" },
      ],
    },
  ],

  /* ---------- Leadership: decisions that require attention ---------- */
  decisions: [
    {
      id: "dec1",
      title: "FY26 revenue guidance risk",
      metric: "Probability of missing the guidance midpoint",
      probability: 27,
      drivers: [
        { text: "Professional ARPU below plan", direction: "down" },
        { text: "Spain customer growth above plan", direction: "up" },
        { text: "Product adoption in Germany slower", direction: "down" },
      ],
      readout:
        "AI readout: maintaining guidance remains reasonable. A further 3% ARPU decline lifts the miss probability to 54%. Recommended trigger point for a guidance review: preliminary October ARPU < €22.90.",
      action: "scenario",
    },
    {
      id: "dec2",
      title: "Statutory publication awaiting approval",
      metric: "Voting rights notification — due in 2 trading days",
      probability: null,
      drivers: [
        { text: "Workflow fully prepared by the agent", direction: "up" },
        { text: "Escalation armed at T-1", direction: "neutral" },
      ],
      readout:
        "AI readout: one click required. The publication text is validated against the notification; audit trail is complete.",
      action: "deadlines",
    },
    {
      id: "dec3",
      title: "Consensus gap before the earnings call",
      metric: "Sell-side consensus 0.3% above internal FY26 view — margin gap +0.4pp",
      probability: null,
      drivers: [
        { text: "Kepler revenue estimate +4.2% vs. internal", direction: "down" },
        { text: "Dispersion concentrated in Professional ARPU", direction: "down" },
      ],
      readout:
        "AI readout: without expectation management, a miss vs. consensus is likely even if guidance is met. Suggested narrative adjustments are drafted in the call script.",
      action: "inbox",
    },
  ],

  /* ---------- Scenario Lab: calibrated driver model ---------- */
  scenarioModel: {
    question: "What happens if German ARPU growth is X pp lower?",
    base: {
      revenue: 4200,       // €m internal FY26 view
      ebitdaMarginPct: 31.5,
      eps: 1.92,           // €
      consensusRevenue: 4213, // €m — 0.3% above internal view
      missProbability: 27, // %
    },
    /* Sensitivities calibrated on the decision graph
       (matches the readout: −2pp ARPU → rev −1.8%, EBITDA −0.7pp,
        EPS −€0.04, vs. consensus −2.1%, and −3% ARPU → 54% miss prob.) */
    perArpuPp: {
      revenuePct: 0.9,
      ebitdaPp: 0.35,
      eps: 0.02,
      missProbability: 9,
    },
  },

  /* ---------- Decision Memory ---------- */
  memory: [
    {
      id: "r1",
      date: "2023-03-15",
      title: "Price increase +12% (Consumer Germany)",
      owner: "CFO / Pricing Committee",
      objective: "Increase ARPU; assumption: churn elasticity < 0.8; competitor pricing stable",
      scenarios: "8% · 10% · 12% → chosen: 12%",
      expected: "+€24m revenue",
      actual: "+€21m realized",
      learning: "Churn elasticity underestimated (0.95 vs. assumed 0.8) → calibrates all future pricing scenarios",
      tags: ["pricing", "germany", "elasticity"],
    },
    {
      id: "r2",
      date: "2024-11-02",
      title: "FY25 guidance: narrow range instead of point guidance",
      owner: "CFO / IR",
      objective: "Reduce estimate dispersion after two quarters of misses; assumption: range narrows consensus spread",
      scenarios: "Point guidance · range ±1.5% · range ±3% → chosen: ±1.5%",
      expected: "Consensus spread < 2%",
      actual: "Spread fell from 4.1% to 1.8% within two quarters",
      learning: "Narrow range works when preliminary internal data is reliable — depends on data layer quality",
      tags: ["guidance", "ir", "consensus"],
    },
    {
      id: "r3",
      date: "2025-05-20",
      title: "Dividend policy: payout corridor 40–50%",
      owner: "Management Board / Supervisory Board",
      objective: "Predictability for income investors while retaining capex flexibility; assumption: corridor prevents anchoring on a single payout number",
      scenarios: "Fixed 45% · corridor 40–50% · progressive dividend → chosen: corridor",
      expected: "Shareholder structure shift towards long-only +3pp",
      actual: "+2pp after 12 months",
      learning: "Corridor accepted by the market; retail questions still anchor on the previous year's absolute amount",
      tags: ["dividend", "capital-markets"],
    },
  ],

  /* ---------- Company model (draft-and-confirm onboarding) ---------- */
  companyModel: [
    {
      id: "c1", kind: "Business unit", name: "Consumer Germany",
      evidence: "Extracted from: segment reporting FY25, management P&L, 47 board decks",
      detail: "Revenue €2.3bn · KPI owner: SVP Consumer · key drivers: ARPU, churn, gross adds",
      confidence: 0.96, status: "pending",
    },
    {
      id: "c2", kind: "Business unit", name: "Iberia (Spain & Portugal)",
      evidence: "Extracted from: segment reporting FY25, Iberia expansion business case",
      detail: "Revenue €0.9bn · KPI owner: MD Iberia · key drivers: customer growth, network capex",
      confidence: 0.94, status: "pending",
    },
    {
      id: "c3", kind: "KPI definition", name: "Net ARPU",
      evidence: "Extracted from: controlling handbook v4.2, BI layer (Snowflake), IR fact book",
      detail: "= (service revenue − discounts) / avg. customer base. Two conflicting variants found; controlling handbook version proposed.",
      confidence: 0.81, status: "pending",
    },
    {
      id: "c4", kind: "Decision right", name: "Pricing changes > 5%",
      evidence: "Extracted from: pricing committee minutes 2022–2025, approval matrix",
      detail: "Decided by Pricing Committee, chaired by CFO; requires elasticity scenario per policy",
      confidence: 0.88, status: "pending",
    },
    {
      id: "c5", kind: "Process", name: "Voting-rights publication workflow",
      evidence: "Extracted from: 23 historical cases in the IR mailbox, BaFin correspondence",
      detail: "Trigger: § 33 WpHG notification → validation → publication § 40 WpHG within 3 trading days → BaFin filing",
      confidence: 0.93, status: "confirmed",
    },
    {
      id: "c6", kind: "KPI definition", name: "Churn elasticity (pricing)",
      evidence: "Extracted from: 3 pricing decisions in Decision Memory, calibrated on realized outcomes",
      detail: "Current calibrated value: 0.95 (was assumed 0.8 before 2023 price increase)",
      confidence: 0.77, status: "pending",
    },
  ],

  /* ---------- Audit trail (agents log every action) ---------- */
  audit: [
    { time: "06:00", actor: "Platform", text: "Nightly sync completed: SAP FI, Salesforce, Snowflake, shared mailbox (read-only). 4,182 records processed." },
    { time: "06:04", actor: "KPI agent", text: "Preliminary FY26 run-rate computed from source systems. Confidence 92%. Labeled PRELIMINARY; reconciliation armed for official close." },
    { time: "07:12", actor: "Inbox agent", text: "Mail m1 (J.P. Morgan) classified as Regulatory/P1. § 40 WpHG workflow instantiated, deadline d1 armed (3 trading days)." },
    { time: "08:55", actor: "Inbox agent", text: "Mail m6 (Finanz-Szene) auto-escalated to Head of IR & Corporate Communications. Direct reply blocked pending Art. 17 MAR assessment." },
    { time: "09:15", actor: "Briefing agent", text: "Morning briefing generated: 7 new mails, 3 need action today, 2 statutory deadlines tracked." },
  ],
};
