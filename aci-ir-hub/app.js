/* ============================================================
   ACI · IR Hub MVP — application logic
   Client-side only. State persists in localStorage so approvals,
   confirmations and scenario runs survive a reload.
   ============================================================ */

const STORE_KEY = "aci-ir-hub-v1";

/* ---------- state ---------- */
function freshState() {
  return {
    emails: structuredClone(SEED.emails),
    deadlines: structuredClone(SEED.deadlines),
    memory: structuredClone(SEED.memory),
    companyModel: structuredClone(SEED.companyModel),
    audit: structuredClone(SEED.audit),
    briefingDone: {},          // todoId -> true
    selectedMail: SEED.emails[0].id,
    scenarioArpu: 0,           // pp delta on German ARPU growth
  };
}

let S;
try {
  S = JSON.parse(localStorage.getItem(STORE_KEY)) || freshState();
} catch { S = freshState(); }

function save() { localStorage.setItem(STORE_KEY, JSON.stringify(S)); }

function logAudit(actor, text) {
  const t = new Date();
  const time = `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`;
  S.audit.push({ time, actor, text });
  save();
}

/* ---------- helpers ---------- */
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("show"), 2600);
}

function prioChip(p) {
  return `<span class="chip chip-p${p}">P${p}</span>`;
}
function confChip(c) {
  return `<span class="chip chip-prelim" title="Agent confidence, shown on every AI output">confidence ${Math.round(c * 100)}%</span>`;
}
function aiChip(label = "AI-generated") {
  return `<span class="chip chip-ai">✦ ${label}</span>`;
}

/* Single-series sparkline (blue), 2px line per mark spec. */
function sparkline(values, w = 180, h = 36) {
  const min = Math.min(...values), max = Math.max(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * (w - 8) + 4;
    const y = h - 5 - ((v - min) / range) * (h - 10);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const last = pts[pts.length - 1].split(",");
  return `<svg class="kpi-spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="trend, last 8 periods">
    <polyline points="${pts.join(" ")}" fill="none" stroke="var(--series-1)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="${last[0]}" cy="${last[1]}" r="3.5" fill="var(--series-1)" stroke="var(--surface)" stroke-width="2"/>
  </svg>`;
}

/* ============================================================
   VIEW: Morning Briefing
   Generated from inbox + deadline state — not hand-maintained.
   ============================================================ */
function buildBriefingTodos() {
  const todos = [];
  for (const m of S.emails) {
    if (m.status === "approved" || m.status === "filed") continue;
    todos.push({
      id: "mail-" + m.id,
      priority: m.priority,
      title: m.subject + (m.status === "escalated" ? " — ESCALATED" : ""),
      note: m.aiNote,
      action: m.status === "escalated" ? null : { label: "Approve draft", type: "approve-mail", mailId: m.id },
      goto: "inbox", mailId: m.id,
    });
  }
  for (const d of S.deadlines) {
    if (d.done) continue;
    if (d.severity === "critical" || d.severity === "high") {
      todos.push({
        id: "dl-" + d.id,
        priority: d.severity === "critical" ? 1 : 2,
        title: d.title,
        note: `${d.legalBasis} · due in ${d.dueInTradingDays} trading day(s) · ${d.escalation}`,
        action: null,
        goto: "deadlines",
      });
    }
  }
  todos.sort((a, b) => a.priority - b.priority);
  return todos;
}

function renderBriefing() {
  const todos = buildBriefingTodos();
  const open = todos.filter((t) => !S.briefingDone[t.id]);
  const p1 = open.filter((t) => t.priority === 1).length;
  const newMails = S.emails.length;

  const rows = todos.map((t) => {
    const done = S.briefingDone[t.id];
    return `<div class="todo ${done ? "done" : ""}">
      ${prioChip(t.priority)}
      <div class="todo-body">
        <div class="todo-title">${esc(t.title)}</div>
        <div class="todo-note">${esc(t.note)}</div>
      </div>
      <div class="btn-row">
        ${t.action && !done ? `<button class="btn btn-primary" data-act="${t.action.type}" data-mail="${t.action.mailId}" data-todo="${t.id}">${t.action.label}</button>` : ""}
        <button class="btn btn-ghost" data-act="goto" data-view="${t.goto}" ${t.mailId ? `data-mail="${t.mailId}"` : ""}>Open →</button>
      </div>
    </div>`;
  }).join("");

  $("#view-briefing").innerHTML = `
    <div class="briefing-hero">
      <div class="btn-row" style="justify-content:space-between">
        <div>
          <div class="big">${newMails} new mails · ${open.length} need you today${p1 ? ` · ${p1} × P1` : ""}</div>
          <div class="sub">Triage, drafting and filing ran automatically overnight. Everything below is prepared — you approve.</div>
        </div>
        ${aiChip("Briefing agent · 08:00")}
      </div>
    </div>
    <div class="card">
      <h3>Prioritized to-do list</h3>
      <div class="card-sub" style="margin-bottom:6px">Assembled from the inbox agent, the deadline engine and the KPI layer — one click per item.</div>
      ${rows || `<div class="empty">All done. The agents keep watching.</div>`}
    </div>`;
}

/* ============================================================
   VIEW: Inbox Agent
   ============================================================ */
function renderInbox() {
  const sel = S.emails.find((m) => m.id === S.selectedMail) || S.emails[0];

  const list = S.emails.map((m) => `
    <div class="mail-row ${m.id === sel.id ? "selected" : ""} ${m.status === "approved" || m.status === "filed" ? "done" : ""}" data-act="select-mail" data-mail="${m.id}">
      <div class="mail-row-top"><span class="mail-from">${esc(m.from)}</span><span class="mail-time">${m.received}</span></div>
      <div class="mail-subject">${esc(m.subject)}</div>
      <div class="btn-row">${prioChip(m.priority)}
        <span class="chip chip-muted">${esc(m.category)}</span>
        ${m.status === "approved" ? `<span class="chip chip-good">✓ sent</span>` : ""}
        ${m.status === "escalated" ? `<span class="chip chip-p1">escalated</span>` : ""}
      </div>
    </div>`).join("");

  const canApprove = sel.status === "needs_approval";
  const detail = `
    <div class="card mail-detail">
      <div class="btn-row" style="justify-content:space-between">
        <h3>${esc(sel.subject)}</h3>${prioChip(sel.priority)}
      </div>
      <div class="card-sub">${esc(sel.from)} &lt;${esc(sel.fromEmail)}&gt; · ${sel.received}</div>
      <div class="mail-body">${esc(sel.body)}</div>

      <div class="ai-note">✦ ${esc(sel.aiNote)}</div>

      <div class="ai-draft">
        <div class="ai-draft-label">${aiChip(sel.status === "escalated" ? "Escalation memo" : "Reply draft")} ${confChip(sel.confidence)}</div>
        <textarea id="draft-text" ${sel.status !== "needs_approval" ? "readonly" : ""}>${esc(sel.aiDraft)}</textarea>
      </div>

      <div class="btn-row">
        ${canApprove ? `<button class="btn btn-primary" data-act="approve-mail" data-mail="${sel.id}">Approve &amp; send</button>` : ""}
        ${canApprove ? `<button class="btn" data-act="file-mail" data-mail="${sel.id}">File without reply</button>` : ""}
        ${sel.status === "approved" ? `<span class="chip chip-good">✓ Approved and sent — logged in the audit trail</span>` : ""}
        ${sel.status === "filed" ? `<span class="chip chip-muted">Filed — logged in the audit trail</span>` : ""}
        ${sel.status === "escalated" ? `<span class="chip chip-p1">Blocked: awaiting Art. 17 MAR sign-off by Head of IR / Comms</span>` : ""}
      </div>
    </div>`;

  $("#view-inbox").innerHTML = `
    <div class="inbox-layout">
      <div class="mail-list">${list}</div>
      <div>${detail}</div>
    </div>`;
}

/* ============================================================
   VIEW: Deadlines
   ============================================================ */
function renderDeadlines() {
  const rows = S.deadlines.map((d) => {
    const cls = d.severity === "critical" ? "dl-critical" : d.severity === "high" ? "dl-high" : "dl-normal";
    const count = d.done
      ? `<div class="dl-count dl-normal">✓<small>done</small></div>`
      : `<div class="dl-count ${cls}">${d.dueInTradingDays}<small>trading day(s)</small></div>`;
    return `<div class="dl-row">
      ${count}
      <div style="flex:1">
        <div style="font-weight:700">${esc(d.title)}</div>
        <div class="dl-meta">${esc(d.legalBasis)}</div>
        <div class="dl-meta">${d.done ? "Completed — full audit trail available" : esc(d.state) + " · " + esc(d.escalation)}</div>
      </div>
      ${!d.done && d.sourceEmail && (S.emails.find((m) => m.id === d.sourceEmail) || {}).status === "needs_approval"
        ? `<button class="btn btn-primary" data-act="approve-mail" data-mail="${d.sourceEmail}">Approve workflow</button>`
        : ""}
    </div>`;
  }).join("");

  $("#view-deadlines").innerHTML = `
    <div class="card">
      <div class="btn-row" style="justify-content:space-between">
        <h3>Statutory &amp; internal deadlines</h3>${aiChip("Deadline engine")}
      </div>
      <div class="card-sub" style="margin-bottom:4px">
        Deadlines are detected in incoming mail and filings, tracked in trading days, and escalate automatically.
        Agents prepare — a human approves every publication. Nothing can slip silently.
      </div>
      ${rows}
    </div>`;
}

/* ============================================================
   VIEW: Leadership dashboard + Scenario Lab
   ============================================================ */
function scenarioOutputs(arpuDelta) {
  const m = SEED.scenarioModel;
  const s = m.perArpuPp;
  const revPct = s.revenuePct * arpuDelta;               // arpuDelta is negative for "lower"
  const revenue = m.base.revenue * (1 + revPct / 100);
  const ebitdaPp = s.ebitdaPp * arpuDelta;
  const eps = s.eps * arpuDelta;
  const vsConsensus = ((revenue - m.base.consensusRevenue) / m.base.consensusRevenue) * 100;
  const missProb = Math.max(2, Math.min(97, m.base.missProbability - s.missProbability * arpuDelta));
  return { revPct, revenue, ebitdaPp, eps, vsConsensus, missProb };
}

function fmtSigned(v, digits = 1, unit = "") {
  const n = v.toFixed(digits);
  return (v > 0 ? "+" : "") + n + unit;
}

function renderDashboard() {
  const kpiTiles = SEED.kpis.map((k) => {
    const dir = k.deltaPct >= 0 ? "up" : "down";
    const unit = k.deltaUnit || "%";
    const children = k.children.map((c) =>
      `<div class="kpi-child"><span>${esc(c.name)} <span style="color:var(--muted)">· ${esc(c.note)}</span></span>
       <b class="kpi-delta ${c.deltaPct >= 0 ? "up" : "down"}">${fmtSigned(c.deltaPct, 1, "%")}</b></div>`).join("");
    return `<div class="card kpi-tile">
      <div class="kpi-name">${esc(k.name)}
        ${k.preliminary ? `<span class="chip chip-prelim" title="Computed by agents from source systems before the official close; reconciled automatically once official numbers land">PRELIMINARY · ${Math.round(k.confidence * 100)}%</span>` : ""}
      </div>
      <div class="kpi-value">${esc(k.value)}</div>
      <div class="kpi-delta ${dir}">${fmtSigned(k.deltaPct, 1, unit)} <span class="kpi-plan">vs. plan ${esc(k.plan)}</span></div>
      ${sparkline(k.spark)}
      <div class="kpi-children">${children}</div>
    </div>`;
  }).join("");

  const decisionCards = SEED.decisions.map((d, i) => {
    const drivers = d.drivers.map((dr) => {
      const col = dr.direction === "up" ? "var(--good)" : dr.direction === "down" ? "var(--critical)" : "var(--muted)";
      const arrow = dr.direction === "up" ? "▲" : dr.direction === "down" ? "▼" : "•";
      return `<div class="driver"><span class="dot" style="background:${col}"></span>${esc(dr.text)} <span style="color:${col};font-size:10px">${arrow}</span></div>`;
    }).join("");
    return `<div class="card decision-card">
      <div class="decision-head">
        <div>
          <div class="card-sub">DECISION ${i + 1} / ${SEED.decisions.length}</div>
          <h3>${esc(d.title)}</h3>
          <div class="card-sub">${esc(d.metric)}</div>
        </div>
        ${d.probability !== null ? `<div class="decision-prob">${d.probability}%<small>miss probability</small></div>` : ""}
      </div>
      <div style="margin-top:10px">${drivers}</div>
      <div class="readout">✦ ${esc(d.readout)}</div>
      <div class="btn-row" style="margin-top:12px">
        ${d.action === "scenario"
          ? `<button class="btn btn-primary" data-act="goto-scenario">Run scenario ↓</button>`
          : `<button class="btn" data-act="goto" data-view="${d.action}">Open ${d.action} →</button>`}
      </div>
    </div>`;
  }).join("");

  const scenario = `
    <div class="card scenario-box" id="scenario-lab">
      <div class="btn-row" style="justify-content:space-between">
        <h3>Scenario Lab</h3>${aiChip("One model — computed through to the capital market")}
      </div>
      <div class="scenario-q">“What happens if German ARPU growth is <b id="scn-q">${fmtSigned(S.scenarioArpu, 1, " pp")}</b> vs. plan?”</div>
      <div class="slider-row">
        <span class="card-sub">−4 pp</span>
        <input type="range" id="arpu-slider" min="-4" max="2" step="0.5" value="${S.scenarioArpu}"
               aria-label="German ARPU growth delta in percentage points">
        <span class="card-sub">+2 pp</span>
        <span class="slider-val" id="scn-val">${fmtSigned(S.scenarioArpu, 1, " pp")}</span>
      </div>
      <div class="scenario-out">
        <div class="scn-tile"><div class="lab">Revenue</div><div class="val" id="scn-rev"></div><div class="card-sub" id="scn-rev-abs"></div></div>
        <div class="scn-tile"><div class="lab">EBITDA margin</div><div class="val" id="scn-ebitda"></div><div class="card-sub" id="scn-ebitda-abs"></div></div>
        <div class="scn-tile"><div class="lab">EPS</div><div class="val" id="scn-eps"></div><div class="card-sub" id="scn-eps-abs"></div></div>
        <div class="scn-tile"><div class="lab">vs. consensus</div><div class="val" id="scn-cons"></div><div class="card-sub">consensus €${SEED.scenarioModel.base.consensusRevenue}m</div></div>
      </div>
      <div style="margin-top:14px">
        <div class="btn-row" style="justify-content:space-between">
          <span class="card-sub"><b id="scn-prob-text"></b> (base case 27%)</span>
          <button class="btn btn-primary" data-act="save-scenario">Save as decision record</button>
        </div>
        <div class="prob-bar"><div class="prob-fill" id="scn-prob-fill"></div></div>
        <div class="card-sub" style="margin-top:8px">Saving a scenario run creates a Decision Memory record automatically — memory as a by-product of the workflow, not extra documentation.</div>
      </div>
    </div>`;

  $("#view-dashboard").innerHTML = `
    <div class="section-label">Instead of 38 dashboards: ${SEED.decisions.length} decisions require attention</div>
    <div class="grid-3">${decisionCards}</div>
    <div class="section-label">Scenario Lab</div>
    ${scenario}
    <div class="section-label">KPI tree — real time, preliminary figures clearly labeled</div>
    <div class="grid-4">${kpiTiles}</div>`;

  updateScenario();
}

/* Writes scenario outputs in place so dragging the slider never
   replaces the slider element mid-drag. */
function updateScenario() {
  const o = scenarioOutputs(S.scenarioArpu);
  const sign = (el, v) => { el.classList.toggle("neg", v < 0); el.classList.toggle("pos", v > 0); };

  $("#scn-q").textContent = fmtSigned(S.scenarioArpu, 1, " pp");
  $("#scn-val").textContent = fmtSigned(S.scenarioArpu, 1, " pp");

  const rev = $("#scn-rev"); rev.textContent = fmtSigned(o.revPct, 1, "%"); sign(rev, o.revPct);
  $("#scn-rev-abs").textContent = `€${o.revenue.toFixed(0)}m`;

  const eb = $("#scn-ebitda"); eb.textContent = fmtSigned(o.ebitdaPp, 1, " pp"); sign(eb, o.ebitdaPp);
  $("#scn-ebitda-abs").textContent = `${(SEED.scenarioModel.base.ebitdaMarginPct + o.ebitdaPp).toFixed(1)}%`;

  const eps = $("#scn-eps"); eps.textContent = fmtSigned(o.eps, 2, " €"); sign(eps, o.eps);
  $("#scn-eps-abs").textContent = `€${(SEED.scenarioModel.base.eps + o.eps).toFixed(2)}`;

  const cons = $("#scn-cons"); cons.textContent = fmtSigned(o.vsConsensus, 1, "%"); sign(cons, o.vsConsensus);

  $("#scn-prob-text").textContent = `Guidance-miss probability: ${o.missProb.toFixed(0)}%`;
  $("#scn-prob-fill").style.width = `${o.missProb}%`;
}

/* ============================================================
   VIEW: Decision Memory
   ============================================================ */
function renderMemory(query = "") {
  const q = query.trim().toLowerCase();
  const records = S.memory.filter((r) =>
    !q || [r.title, r.objective, r.learning, r.scenarios, (r.tags || []).join(" ")].join(" ").toLowerCase().includes(q));

  const cards = records.slice().reverse().map((r) => `
    <div class="card mem-record">
      <div class="btn-row" style="justify-content:space-between">
        <h3>${esc(r.title)}</h3>
        <span class="chip chip-muted">${esc(r.date)}</span>
      </div>
      <div class="card-sub">${esc(r.owner)}</div>
      <dl class="fields">
        <dt>Objective / assumptions</dt><dd>${esc(r.objective)}</dd>
        <dt>Scenarios</dt><dd>${esc(r.scenarios)}</dd>
        <dt>Expected / actual</dt><dd>${esc(r.expected)} · ${esc(r.actual)}</dd>
        <div class="learning" style="display:contents"><dt>Learning</dt><dd>${esc(r.learning)}</dd></div>
      </dl>
      <div style="margin-top:10px">${(r.tags || []).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
    </div>`).join("");

  $("#view-memory").innerHTML = `
    <input class="mem-search" id="mem-search" placeholder='Ask the company: e.g. “Why 12% and not 8%?”' value="${esc(query)}">
    <div class="card-sub" style="margin-bottom:12px">
      ${records.length} structured decision record(s)${q ? ` for “${esc(query)}”` : ""} —
      an answer in seconds instead of a search through 1,300 PowerPoints. Records survive every personnel change
      and calibrate future scenarios (e.g. churn elasticity 0.95, learned from the 2023 price increase).
    </div>
    ${cards || `<div class="empty">No record matches. Try “pricing”, “guidance” or “12%”.</div>`}`;

  const input = $("#mem-search");
  input.addEventListener("input", () => renderMemory(input.value));
  if (q) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); }
}

/* ============================================================
   VIEW: Company model (draft-and-confirm)
   ============================================================ */
function renderModel() {
  const confirmed = S.companyModel.filter((c) => c.status === "confirmed").length;
  const rows = S.companyModel.map((c) => `
    <div class="model-row">
      <div style="flex:1">
        <div class="model-kind">${esc(c.kind)}</div>
        <div style="font-weight:700">${esc(c.name)}</div>
        <div class="card-sub">${esc(c.detail)}</div>
        <div class="model-evidence">${esc(c.evidence)}</div>
      </div>
      <div style="text-align:right;flex-shrink:0">
        <div class="card-sub" style="margin-bottom:4px">extraction confidence ${Math.round(c.confidence * 100)}%</div>
        <div class="conf-bar"><div class="conf-fill" style="width:${c.confidence * 100}%"></div></div>
        <div class="btn-row" style="margin-top:8px;justify-content:flex-end">
          ${c.status === "confirmed"
            ? `<span class="chip chip-good">✓ confirmed</span>`
            : `<button class="btn btn-primary" data-act="confirm-model" data-model="${c.id}">Confirm</button>
               <button class="btn" data-act="reject-model" data-model="${c.id}">Needs review</button>`}
        </div>
      </div>
    </div>`).join("");

  $("#view-model").innerHTML = `
    <div class="card">
      <div class="btn-row" style="justify-content:space-between">
        <h3>Draft-and-confirm: the extracted company model</h3>
        <span class="chip chip-muted">${confirmed} / ${S.companyModel.length} confirmed</span>
      </div>
      <div class="card-sub" style="margin-bottom:4px">
        The platform read reports, models and mailbox history and drafted the decision graph below.
        Your team confirms each element — so the model stays correct. Extraction accuracy is a measurable onboarding KPI.
      </div>
      ${rows}
    </div>`;
}

/* ============================================================
   VIEW: Audit trail
   ============================================================ */
function renderAudit() {
  const rows = S.audit.slice().reverse().map((a) => `
    <div class="audit-row">
      <span class="audit-time">${esc(a.time)}</span>
      <span class="audit-actor">${esc(a.actor)}</span>
      <span class="audit-text">${esc(a.text)}</span>
    </div>`).join("");
  $("#view-audit").innerHTML = `
    <div class="card">
      <h3>Every agent action, logged</h3>
      <div class="card-sub" style="margin-bottom:4px">Agents prepare, humans approve — and everything is auditable. This is what sells in regulated processes (MAR / WpHG).</div>
      ${rows}
    </div>`;
}

/* ============================================================
   Navigation & rendering
   ============================================================ */
const VIEWS = {
  briefing: { title: "Morning Briefing", sub: "Employee level — a prioritized to-do list every morning; drafts prepared, one-click approval.", render: renderBriefing },
  inbox: { title: "Inbox Agent", sub: "Reads every mail in the shared IR mailbox, triages, drafts replies, files cases — humans approve.", render: renderInbox },
  deadlines: { title: "Deadline Engine", sub: "Statutory deadlines cannot slip: tracked in trading days, escalated automatically, fully audited.", render: renderDeadlines },
  dashboard: { title: "Leadership Dashboard", sub: "Real-time KPIs and AI readouts instead of waiting days for analyses — and instead of 38 dashboards: “3 decisions require attention.”", render: renderDashboard },
  memory: { title: "Decision Memory", sub: "Every significant decision, stored as a structured record — captured as a by-product of the workflow.", render: renderMemory },
  model: { title: "Company Model", sub: "CONNECT → UNDERSTAND: the platform drafts how your company works; your team confirms it.", render: renderModel },
  audit: { title: "Audit Trail", sub: "Compliance as a barrier — and as a feature: a full log of every agent action.", render: renderAudit },
};

let currentView = "briefing";

function refreshBadges() {
  const openMails = S.emails.filter((m) => m.status === "needs_approval").length;
  const escalated = S.emails.filter((m) => m.status === "escalated").length;
  const critDl = S.deadlines.filter((d) => !d.done && d.severity === "critical").length;
  const pendingModel = S.companyModel.filter((c) => c.status === "pending").length;
  const openTodos = buildBriefingTodos().filter((t) => !S.briefingDone[t.id]).length;
  $("#badge-inbox").textContent = openMails + escalated || "";
  $("#badge-deadlines").textContent = critDl || "";
  $("#badge-model").textContent = pendingModel || "";
  $("#badge-briefing").textContent = openTodos || "";
}

function show(view, opts = {}) {
  currentView = view;
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + view));
  $("#view-title").textContent = VIEWS[view].title;
  $("#view-sub").textContent = VIEWS[view].sub;
  if (opts.mailId) S.selectedMail = opts.mailId;
  VIEWS[view].render();
  refreshBadges();
  if (opts.scroll) {
    requestAnimationFrame(() => document.getElementById(opts.scroll)?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }
}

/* ---------- actions ---------- */
function approveMail(id, todoId) {
  const m = S.emails.find((x) => x.id === id);
  if (!m || m.status !== "needs_approval") return;
  m.status = "approved";
  if (m.deadlineId) {
    const d = S.deadlines.find((x) => x.id === m.deadlineId);
    if (d) {
      d.done = true;
      logAudit("Deadline engine", `Deadline "${d.title}" completed after human approval. Filing archived.`);
    }
  }
  if (todoId) S.briefingDone[todoId] = true;
  S.briefingDone["mail-" + id] = true;
  logAudit("Inbox agent", `Draft for "${m.subject}" approved by user and sent. Case filed.`);
  save();
  toast("Approved and sent — logged in the audit trail");
}

function fileMail(id) {
  const m = S.emails.find((x) => x.id === id);
  if (!m) return;
  m.status = "filed";
  S.briefingDone["mail-" + id] = true;
  logAudit("Inbox agent", `"${m.subject}" filed without reply on user instruction.`);
  save();
  toast("Filed");
}

function saveScenario() {
  const arpu = S.scenarioArpu;
  const o = scenarioOutputs(arpu);
  const today = new Date().toISOString().slice(0, 10);
  S.memory.push({
    id: "r" + Date.now(),
    date: today,
    title: `Scenario run: German ARPU growth ${fmtSigned(arpu, 1, "pp")} vs. plan`,
    owner: "CFO / IR (Scenario Lab)",
    objective: "Assess FY26 guidance risk; assumptions from the calibrated decision graph (churn elasticity 0.95)",
    scenarios: `ARPU ${fmtSigned(arpu, 1, "pp")} → revenue ${fmtSigned(o.revPct, 1, "%")}, EBITDA ${fmtSigned(o.ebitdaPp, 1, "pp")}, EPS ${fmtSigned(o.eps, 2, "€")}, vs. consensus ${fmtSigned(o.vsConsensus, 1, "%")}`,
    expected: `Guidance-miss probability ${o.missProb.toFixed(0)}%`,
    actual: "open — reconciled automatically against actuals",
    learning: "Pending: expectation vs. outcome will calibrate the ARPU sensitivity",
    tags: ["scenario-lab", "guidance", "arpu"],
  });
  logAudit("Scenario Lab", `Scenario run saved as decision record (ARPU ${fmtSigned(arpu, 1, "pp")}, miss probability ${o.missProb.toFixed(0)}%).`);
  save();
  toast("Decision record created — see Decision Memory");
}

function setModelStatus(id, status) {
  const c = S.companyModel.find((x) => x.id === id);
  if (!c) return;
  c.status = status;
  logAudit("Model extraction", status === "confirmed"
    ? `"${c.name}" confirmed by user — element is now part of the decision graph.`
    : `"${c.name}" flagged for review — extraction team notified, accuracy KPI updated.`);
  save();
  toast(status === "confirmed" ? "Confirmed — added to the decision graph" : "Flagged for review");
}

/* ---------- global event delegation ---------- */
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-act]");
  if (!el) return;
  const act = el.dataset.act;

  if (act === "select-mail") { S.selectedMail = el.dataset.mail; save(); renderInbox(); }
  if (act === "approve-mail") { approveMail(el.dataset.mail, el.dataset.todo); show(currentView, { mailId: el.dataset.mail }); }
  if (act === "file-mail") { fileMail(el.dataset.mail); show(currentView); }
  if (act === "goto") { show(el.dataset.view, { mailId: el.dataset.mail }); }
  if (act === "goto-scenario") { show("dashboard", { scroll: "scenario-lab" }); }
  if (act === "save-scenario") { saveScenario(); refreshBadges(); }
  if (act === "confirm-model") { setModelStatus(el.dataset.model, "confirmed"); renderModel(); refreshBadges(); }
  if (act === "reject-model") { setModelStatus(el.dataset.model, "review"); renderModel(); refreshBadges(); }
});

document.addEventListener("input", (e) => {
  if (e.target.id === "arpu-slider") {
    S.scenarioArpu = parseFloat(e.target.value);
    save();
    updateScenario();
  }
});

document.querySelectorAll(".nav-item").forEach((b) =>
  b.addEventListener("click", () => show(b.dataset.view)));

$("#reset-demo").addEventListener("click", () => {
  localStorage.removeItem(STORE_KEY);
  S = freshState();
  show("briefing");
  toast("Demo state reset");
});

/* ---------- boot ---------- */
$("#today-chip").textContent = new Date().toLocaleDateString("en-GB", {
  weekday: "long", day: "numeric", month: "long", year: "numeric",
});
show("briefing");
