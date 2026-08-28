/* CashGuard AI — dashboard frontend (vanilla JS + Leaflet)
   Phase 7 UI: JWT login, drill-down filters (time/location/category), WS live
   feed, 3-field evidence, PDF reports, recovery queue + funnel, ledger + inbox.

   UI policy: fictional locations only; every name comes from the API. */
"use strict";

const COMPLAINT_TYPES = ["phishing", "investment_fraud", "job_fraud", "upi_fraud", "digital_arrest", "sextortion"];
const TOKEN_KEY = "cashguard_token";
const state = {
  user: null,           // {user_id, username, role, scope, display_name}
  stateFilter: "All", cityFilter: "All", bankFilter: "All",
  category: "All", asOf: null,
  risk: [], alerts: [], stats: null, banks: [],
  complaints: [], cityCoords: {}, recovery: [], funnel: null, inbox: [],
  showHeat: true, showForecast: true,
};

/* ------------------------------ helpers ------------------------------ */
function getToken() { return localStorage.getItem(TOKEN_KEY) || ""; }

async function api(path, opts = {}) {
  const token = getToken();
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    ...opts,
  });
  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    showLogin();
    throw new Error("Session expired — please sign in again");
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${path} -> ${res.status} ${body.slice(0, 120)}`);
  }
  return res.json();
}

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), 4500);
}

function esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function riskLevel(s) { return s >= 0.85 ? "CRITICAL" : s >= 0.7 ? "HIGH" : s >= 0.4 ? "MEDIUM" : "LOW"; }
function riskColor(s) { return { LOW: "#22c55e", MEDIUM: "#eab308", HIGH: "#ef4444", CRITICAL: "#b91c1c" }[riskLevel(s)]; }
function statusPill(s) { const c = { new: "bad", acknowledged: "warn", actioned: "ok" }[s] || "info"; return `<span class="pill ${c}">${esc(s)}</span>`; }
function riskPill(s) { const l = riskLevel(s); const c = { LOW: "ok", MEDIUM: "warn", HIGH: "bad", CRITICAL: "crit" }[l]; return `<span class="pill ${c}">${(s * 100).toFixed(1)}%</span>`; }
function fmtTime(iso) { const d = new Date(iso); return d.toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); }

function maskedAccount(token) { return token.length > 12 ? token.slice(0, 11) + "…" : token; }

function fmtMetric(v, dp = 2) {
  /* Metric values are read from artifacts/metrics.json; a sanitized artifact
     stores non-finite numbers as null — render those as "n/a" instead of null. */
  if (v === null || v === undefined || (typeof v === "number" && !Number.isFinite(v))) return "n/a";
  if (typeof v === "number") return dp ? v.toFixed(dp) : String(v);
  return String(v);
}

function emergingBadge(h) {
  /* Emerging vs historical: 'risk rising fast' vs 'usually risky' (Phase 8). */
  const e = h.emerging_risk || 0;
  if (e >= 0.6) return `<span class="pill bad">▲ Emerging ${(e * 100).toFixed(0)}%</span>`;
  if (e >= 0.35) return `<span class="pill warn">▲ rising ${(e * 100).toFixed(0)}%</span>`;
  return `<span class="pill info">● historical</span>`;
}

function priorityBadge(h) {
  const pr = h.intervention_priority || 0;
  const cls = pr >= 0.6 ? "bad" : pr >= 0.4 ? "warn" : "info";
  return `<span class="pill ${cls}" title="E=${h.priority_exposure} U=${h.priority_urgency} S=${h.priority_evidence} Q=${h.priority_confidence_weight}">⚡ ${(pr * 100).toFixed(0)}</span>`;
}

/* ------------------------------ map ------------------------------ */
let map = null, atmLayer = null, complaintLayer = null;

function initMap() {
  if (map) return;
  if (typeof L === "undefined") return;  // Leaflet failed to load — degrade gracefully
  map = L.map("map", { zoomControl: true }).setView([21.2, 78.5], 5);
  const tiles = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; OSM &copy; CARTO', maxZoom: 18,
  });
  tiles.on("tileerror", () => {
    // tile imagery unreachable (offline) — map engine + risk markers still work
    const mapEl = document.getElementById("map");
    if (mapEl && !mapEl._tileNotice) {
      mapEl._tileNotice = true;
      mapEl.insertAdjacentHTML("beforeend",
        `<div class="map-fallback" style="bottom:6px;top:auto">Tile imagery offline — risk markers remain live on the gray canvas.</div>`);
    }
  });
  tiles.addTo(map);
  atmLayer = L.layerGroup().addTo(map);
  complaintLayer = L.layerGroup().addTo(map);
}

function renderMap() {
  try {
    if (typeof L === "undefined" || !atmLayer) {
      const mapEl = document.getElementById("map");
      if (mapEl && !mapEl._notice) {
        mapEl._notice = true;
        mapEl.innerHTML = `<div class="map-fallback">Map tiles unavailable (offline?) — data tables below remain live.</div>`;
      }
      return;
    }
    initMap();
    atmLayer.clearLayers();
    complaintLayer.clearLayers();
    const rows = state.risk.filter((r) =>
      (state.cityFilter === "All" || r.city === state.cityFilter) &&
      (state.bankFilter === "All" || r.bank_name === state.bankFilter)
    );
    if (state.showForecast) {
      for (const r of rows) {
        const m = L.circleMarker([r.latitude, r.longitude], {
          radius: 5 + r.risk_score * 20, color: riskColor(r.risk_score), weight: 1,
          fillColor: riskColor(r.risk_score), fillOpacity: 0.35 + r.risk_score * 0.45,
        });
        m.bindPopup(
          `<b>${esc(r.atm_id)}</b><br/>${esc(r.branch_name)}<br/>${esc(r.bank_name)} · ${esc(r.city)}<br/>` +
          `Jurisdiction: ${esc(r.state)} / ${esc(r.district)} / ${esc(r.police_station_area)}<br/>` +
          `Risk: <b>${(r.risk_score * 100).toFixed(1)}% (${riskLevel(r.risk_score)})</b>`
        );
        atmLayer.addLayer(m);
      }
    }
    if (state.showHeat) {
      const counts = aggregateComplaints();
      for (const [city, coords] of Object.entries(state.cityCoords)) {
        const n = counts[city] || 0;
        if (!n) continue;
        const m = L.circle(coords, { radius: 4000 + n * 900, color: "#f97316", weight: 1, fillColor: "#f97316", fillOpacity: 0.18 });
        m.bindPopup(`<b>${esc(city)}</b><br/>${n} complaints in window (${esc(state.category)})<br/><span class="muted">fictional location</span>`);
        complaintLayer.addLayer(m);
      }
    }
    map.invalidateSize();
  } catch (err) {
    console.warn("renderMap degraded:", err);
  }
}

function aggregateComplaints() {
  const out = {};
  for (const c of state.complaints) {
    if (state.category !== "All" && c.complaint_type !== state.category) continue;
    if (state.stateFilter !== "All" && c.victim_state !== state.stateFilter) continue;
    out[c.victim_city] = (out[c.victim_city] || 0) + 1;
  }
  return out;
}

/* ------------------------------ data loading ------------------------------ */
async function loadCityCoords() {
  try {
    const atms = await api("/atms?limit=5000");
    const byCity = {};
    for (const a of atms) { (byCity[a.city] ||= []).push([a.latitude, a.longitude]); }
    state.cityCoords = {};
    for (const [city, pts] of Object.entries(byCity)) {
      state.cityCoords[city] = [pts.reduce((s, p) => s + p[0], 0) / pts.length, pts.reduce((s, p) => s + p[1], 0) / pts.length];
    }
    const states = [...new Set(atms.map((a) => a.state))].sort();
    const cities = [...new Set(atms.map((a) => a.city))].sort();
    const banks = [...new Set(atms.map((a) => a.bank_name))].sort();
    const fill = (id, opts) => { const el = document.getElementById(id); el.innerHTML = opts.map((o) => `<option>${esc(o)}</option>`).join(""); el.insertAdjacentHTML("afterbegin", `<option>All</option>`); };
    fill("dd-state", states); fill("dd-city", cities); fill("dd-bank", banks);
  } catch { /* non-fatal */ }
}

async function loadComplaints() {
  try {
    const to = state.asOf || new Date().toISOString();
    const from = new Date(new Date(to).getTime() - 7 * 864e5).toISOString();
    state.complaints = await api(`/complaints?date_from=${encodeURIComponent(from)}&date_to=${encodeURIComponent(to)}&limit=20000`);
  } catch { state.complaints = []; }
}

const ddH = document.getElementById("dd-horizon");
  if (ddH) ddH.addEventListener("change", async (e) => {
    state.horizon = e.target.value;
    await renderHorizonConfidence();
  });

async function renderHorizonConfidence() {
  try {
    const hz = await api("/horizons");
    const rows = hz.horizons || [];
    const h = state.horizon || "24";
    const row = rows.find((r) => String(r.horizon_hours) === h);
    const el = document.getElementById("horizon-confidence");
    if (!row) { if (el) el.textContent = "—"; return; }
    const cls = row.confidence.startsWith("HIGH") ? "ok" : row.confidence.startsWith("MEDIUM") ? "warn" : "bad";
    el.textContent = `${h}h: ${row.confidence}`;
    el.className = `pill ${cls}`;
    if (cls === "bad") {
      toast(`INSUFFICIENT CONFIDENCE at ${h}h horizon — HOLD ACTION for horizon-based recommendations (24h forecast still shown)`);
    }
  } catch { /* panel absent */ }
}

async function loadAll() {
  try {
    const q = state.asOf ? `&as_of=${encodeURIComponent(state.asOf)}` : "";
    const [risk, alerts, stats] = await Promise.all([
      api(`/risk-scores${q}`),
      api("/alerts?limit=200"),
      api("/stats/summary"),
    ]);
    state.risk = risk; state.alerts = alerts; state.stats = stats;
    await Promise.all([loadCityCoords(), loadComplaints()]);
    document.getElementById("as-of").textContent = state.asOf ? `Forecast replay as of ${fmtTime(state.asOf)}` : `Forecast as of ${fmtTime(stats.generated_at)}`;
    document.getElementById("role-badge").textContent = `${state.user.role} · ${state.user.scope}`;
    render();
  } catch (err) { toast("Load failed: " + err.message); }
}

/* ------------------------------ renderers ------------------------------ */
function render() {
  document.querySelectorAll("main.dash").forEach((d) => d.classList.add("hidden"));
  if (state.user.role === "BANK") { document.getElementById("dash-bank").classList.remove("hidden"); renderBank(); }
  else if (state.user.role === "I4C_ADMIN") { document.getElementById("dash-i4c").classList.remove("hidden"); renderI4C(); }
  else { document.getElementById("dash-police").classList.remove("hidden"); renderPolice(); }
}

function renderPolice() {
  renderMap();
  const hotspots = [...state.risk].sort((a, b) => b.risk_score - a.risk_score).slice(0, 20);
  document.getElementById("hotspot-count").textContent = `${hotspots.length} hotspots`;
  tbodyOf(document.getElementById("hotspot-table")).innerHTML = hotspots.map(
    (h, i) => `<tr><td>${i + 1}</td><td><b>${esc(h.atm_id)}</b></td><td>${esc(h.branch_name)}<br/><span class="muted">${esc(h.bank_name)}</span></td><td>${esc(h.city)}</td>
    <td>${riskPill(h.risk_score)}</td><td>${emergingBadge(h)}</td><td>${priorityBadge(h)}</td></tr>`
  ).join("");
  renderAlertTable("alert-table");
  loadThresholdCurve();
}

let THR_CURVE = null;
async function loadThresholdCurve() {
  if (THR_CURVE) return applyThresholdCurve();
  try {
    const data = await api("/threshold-explorer");
    THR_CURVE = data;
    applyThresholdCurve();
  } catch (e) { /* non-fatal: explorer panel stays on its placeholder */ }
}
function applyThresholdCurve() {
  const slider = document.getElementById("thr-slider");
  const out = document.getElementById("thr-metrics");
  if (!THR_CURVE || !slider || !out) return;
  const row = THR_CURVE.curve.find((r) => Math.abs(r.threshold * 100 - Number(slider.value)) < 0.01) || THR_CURVE.curve[0];
  document.getElementById("thr-value").textContent = row.threshold.toFixed(2);
  out.innerHTML = `at threshold <b>${row.threshold.toFixed(2)}</b>: precision <b>${(row.precision * 100).toFixed(1)}%</b> · recall ${(row.recall * 100).toFixed(1)}% · ${row.alert_volume} alerts · false-alert rate ${(row.false_alert_rate * 100).toFixed(1)}%`;
}
document.addEventListener("DOMContentLoaded", () => {
  const slider = document.getElementById("thr-slider");
  if (slider) slider.addEventListener("input", applyThresholdCurve);
});

function tbodyOf(el) {
  /* The data tables declare <tbody> explicitly; guard anyway so a stale-cache
     markup mix can never kill rendering. */
  return (el && el.querySelector && el.querySelector("tbody")) || el;
}

function renderAlertTable(tableId, alerts = state.alerts) {
  const countEl = document.getElementById("alert-count");
  if (countEl) countEl.textContent = `${alerts.filter((a) => a.status === "new").length} new`;
  const el = document.getElementById(tableId);
  if (!el) return;
  tbodyOf(el).innerHTML = alerts.map(
    (a) => `<tr><td>${fmtTime(a.created_at)}</td><td><b>${esc(a.atm_id)}</b></td><td>${esc(a.city)}</td>
    <td>${tierBadge(a.tier || tierOf(a.risk_score))}</td><td>${riskPill(a.risk_score)}</td><td>${esc(a.recommended_action)}</td><td>${statusPill(a.status)}</td>
    <td><button class="btn small" data-evid="${esc(a.alert_id)}">Details</button>
    ${hitlButtons(a)}</td></tr>`
  ).join("");
  el.querySelectorAll("button[data-act]").forEach((b) => b.addEventListener("click", () => hitlAction(b.dataset.id, b.dataset.act)));
  el.querySelectorAll("button[data-evid]").forEach((b) => b.addEventListener("click", () => openEvidence(b.dataset.evid)));
}

function tierBadge(tier) {
  const cls = tier === "dispatch" ? "tier dispatch" : tier === "action" ? "tier action" : "tier monitor";
  return `<span class="${cls}">${esc(tier || "monitor")}</span>`;
}
function tierOf(score) {
  if (score >= 0.85) return "dispatch";
  if (score >= 0.7) return "action";
  return "monitor";
}

function hitlButtons(a) {
  const base = `data-id="${esc(a.alert_id)}"`;
  if (a.status === "new" || a.status === "acknowledged" || a.status === "monitoring") {
    return `<button class="btn small ok" data-act="acknowledged" ${base}>Acknowledge</button>
      <button class="btn small" data-act="monitoring" ${base}>Monitor</button>
      <button class="btn small warn" data-act="dismissed" ${base}>Dismiss</button>
      <button class="btn small warn" data-act="escalated" ${base}>Escalate</button>
      <button class="btn small" data-act="review_requested" ${base}>More data</button>`;
  }
  return "";
}

function hitlAction(alertId, status) {
  let reason = "";
  if (status === "dismissed" || status === "escalated") {
    reason = prompt(`Reason required for "${status}" (recorded to the audit ledger):`);
    if (reason === null) return;
    if (!reason.trim()) { toast("A reason is required for " + status); return; }
  }
  setAlertStatus(alertId, status, reason);
}

async function setAlertStatus(alertId, status, reason = "") {
  try {
    await api(`/alerts/${alertId}/status`, { method: "POST", body: JSON.stringify({ status, reason }) });
    toast(`Alert ${alertId} → ${status} (ledger-recorded)`);
    loadAll();
  } catch (err) { toast("Update failed: " + err.message); }
}

async function renderBank() {
  renderMap();
  const bank = state.user.scope;
  const atms = state.risk.filter((r) => r.bank_name === bank);
  const alerts = state.alerts.filter((a) => a.bank_name === bank);
  const high = atms.filter((a) => a.risk_score >= 0.7).length;
  document.getElementById("bank-summary").textContent = `${bank} — ${atms.length} ATMs scored · ${high} high-risk · ${alerts.length} alerts`;
  tbodyOf(document.getElementById("bank-atm-table")).innerHTML = atms.map(
    (a) => `<tr><td><b>${esc(a.atm_id)}</b></td><td>${esc(a.branch_name)}</td><td>${esc(a.city)}</td><td>${riskPill(a.risk_score)}</td><td>${esc(bankAction(a.risk_score))}</td></tr>`
  ).join("");
  renderAlertTable("bank-alert-table", alerts);
  await renderRecovery();
}

async function renderRecovery() {
  try {
    state.recovery = await api("/recovery/recommendations");
    state.funnel = await api("/recovery/funnel?days=7");
  } catch { return; }
  const q = document.getElementById("recovery-queue");
  q.innerHTML = state.recovery.length ? state.recovery.map(
    (r) => `<div class="rec-row">
      <span><b>${esc(maskedAccount(r.account_token))}</b> · ${esc(r.home_bank)}</span>
      <span class="muted">₹${r.amount_at_risk.toLocaleString()} at risk · ${esc(r.suspected_atm)}</span>
      <span>${statusPill(r.status)}</span>
      <span>
        <button class="btn small ok" data-rec="${esc(r.rec_id)}" data-s="held">Hold</button>
        <button class="btn small warn" data-rec="${esc(r.rec_id)}" data-s="recovered">Recovered</button>
      </span></div>`
  ).join("") : `<p class="muted">No open fund-block recommendations.</p>`;
  q.querySelectorAll("button[data-rec]").forEach((b) => b.addEventListener("click", () => updateRecovery(b.dataset.rec, b.dataset.s)));
  const f = state.funnel || {};
  document.getElementById("bank-funnel").innerHTML = funnelBars(f);
}

function funnelBars(f) {
  const max = Math.max(f.amount_flagged || 1, 1);
  const bar = (label, v, color) => `<div class="bar-row"><span>${label}</span><div class="bar-track"><div class="bar-fill" style="width:${(v / max) * 100}%;background:${color}"></div></div><span class="muted">₹${Math.round(v).toLocaleString()}</span></div>`;
  return `${bar("Flagged", f.amount_flagged || 0, "#ef4444")}${bar("Held", f.amount_held || 0, "#eab308")}${bar("Recovered", f.amount_recovered || 0, "#22c55e")}
    <p class="ev-notice">Recovery rate ${f.recovery_rate_pct || 0}% — outcomes are synthetic/illustrative (CFCFRMS APIs = Tier 2).</p>`;
}

function bankAction(score) {
  if (score >= 0.85) return "Freeze suspicious linked accounts + alert branch staff";
  if (score >= 0.7) return "Enable enhanced monitoring of this ATM";
  if (score >= 0.4) return "Increase cash-in-cassette monitoring";
  return "No action required";
}

async function renderOutcomes() {
  try {
    const s = await api("/alerts/outcomes/summary");
    const el = document.getElementById("outcome-panel");
    document.getElementById("outcome-badge").textContent = s.evaluated ? `${s.evaluated} evaluated` : "";
    if (!s.evaluated) {
      el.innerHTML = `<p class="muted">No outcomes yet — alerts must age past the 24h horizon. Click "Evaluate pending" after a cycle.</p>`;
      return;
    }
    el.innerHTML = [
      ["Evaluated", s.evaluated], ["True positives", s.true_positives], ["False positives", s.false_positives],
      ["False negatives", s.false_negatives], ["Mean |error|", s.mean_abs_error], ["Outcome ECE (10 bins)", s.outcome_ece_10_bins],
    ].map(([k, v]) => `<div class="m-row"><span>${esc(k)}</span><b>${esc(String(v))}</b></div>`).join("") +
      `<p class="ev-notice">${esc(s.note)}</p>`;
  } catch { /* panel absent for non-I4C */ }
}

async function renderI4C() {
  renderMap();
  const s = state.stats;
  document.getElementById("i4c-stats").innerHTML = [
    ["🕵️", s.complaints_24h, "Complaints (24h)"], ["📅", s.complaints_7d, "Complaints (7d)"],
    ["🏧", s.high_risk_atms, "High-risk ATMs"], ["🚨", s.alerts_total, "Alerts"],
    ["✅", s.alerts_actioned, "Actioned"], ["💸", s.fraud_withdrawals_7d, "Fraud withdrawals (7d)"],
  ].map(([e, n, l]) => `<div class="stat"><div class="num">${e} ${n.toLocaleString()}</div><div class="lbl">${l}</div></div>`).join("");

  try {
    state.funnel = await api("/recovery/funnel?days=7");
    document.getElementById("i4c-funnel").innerHTML = funnelBars(state.funnel);
  } catch { document.getElementById("i4c-funnel").innerHTML = `<p class="muted">—</p>`; }

  const c7 = s.complaints_by_city_7d || {}; const c24 = s.complaints_by_city_24h || {};
  const max7 = Math.max(1, ...Object.values(c7));
  document.getElementById("city-bars").innerHTML = Object.entries(c7).map(
    ([city, n]) => `<div class="bar-row"><span><b>${esc(city)}</b></span><div class="bar-track"><div class="bar-fill" style="width:${(n / max7) * 100}%"></div></div><span class="muted">${n} (7d) · ${c24[city] || 0} (24h)</span></div>`
  ).join("");

  try {
    const m = await api("/train/status");
    if (m.metrics) {
      document.getElementById("model-metrics").innerHTML = [
        ["Model", m.metrics.model_type + " + " + (m.metrics.calibration || "—")],
        ["ROC-AUC", fmtMetric(m.metrics.roc_auc, 4)], ["Precision@20/50/100/1000", `${fmtMetric(m.metrics.precision_at_20, null)} / ${fmtMetric(m.metrics.precision_at_50, null)} / ${fmtMetric(m.metrics.precision_at_100, null)} / ${fmtMetric(m.metrics.precision_at_1000, null)}`],
        ["Baseline P@20 (volume)", fmtMetric(m.metrics.baseline_volume_precision_at_20, null)], ["Lift vs volume @100", fmtMetric(m.metrics.lift_vs_volume_at_100, null)],
        ["Lift vs proximity @100", fmtMetric(m.metrics.lift_vs_proximity_at_100, null)],
        ["Lead time (median)", `${fmtMetric(m.metrics.lead_time_median_hours, null)} h`],
        ["Threshold (≥0.7) precision", fmtMetric(m.metrics.precision_at_threshold_0p7, 2)],
      ].map(([k, v]) => `<div class="m-row"><span>${esc(k)}</span><b>${esc(String(v))}</b></div>`).join("") +
      `<p class="ev-notice">Measured on SYNTHETIC labels — see LIMITATIONS.md. Top-K certainty is carried by legitimate complaint-linked signal (counterparty_count_24h); precision decays to ${fmtMetric(m.metrics.precision_at_1000, null)} at K=1000 and threshold (≥0.7) precision is ${fmtMetric(m.metrics.precision_at_threshold_0p7, 2)}. Full detail: LIMITATIONS.md.</p>`;
    }
  } catch { document.getElementById("model-metrics").innerHTML = `<p class="muted">Train to see metrics.</p>`; }

  renderAlertTable("i4c-alert-table", state.alerts);
  await ledgerStatus();
  await renderInbox();
  await renderOutcomes();
}

async function ledgerStatus() {
  try {
    const v = await api("/ledger/verify");
    document.getElementById("ledger-badge").innerHTML = v.intact
      ? `<span class="pill ok">Ledger verified ✓ · ${v.records} blocks</span>`
      : `<span class="pill bad">LEDGER TAMPERED ✗ at block ${v.broken_at_index}</span>`;
    const lst = await api("/ledger");
    document.getElementById("ledger-preview").textContent =
      `Last block: #${lst[lst.length - 1].index} ${lst[lst.length - 1].event_type} by ${lst[lst.length - 1].actor} @ ${fmtTime(lst[lst.length - 1].created_at)}`;
  } catch { document.getElementById("ledger-badge").innerHTML = `<span class="pill info">Sign in to verify</span>`; }
}

async function renderInbox() {
  try {
    state.inbox = await api("/mock-i4c-inbox");
    document.getElementById("inbox-panel").innerHTML = state.inbox.slice(0, 15).map(
      (m) => `<div class="inbox-msg"><span class="pill info">${esc(m.channel)}</span> <span class="muted">${fmtTime(m.received_at)}</span><br/><span class="mono">${esc(JSON.stringify(m.payload).slice(0, 160))}</span></div>`
    ).join("") || `<p class="muted">No intel received yet — run an alert cycle.</p>`;
  } catch { document.getElementById("inbox-panel").innerHTML = `<p class="muted">—</p>`; }
}

/* ------------------------------ evidence panel ------------------------------ */
async function openEvidence(alertId) {
  try {
    const ev = await api(`/alerts/${alertId}/evidence`);
    const j = ev.jurisdiction || {};
    const contribs = (ev.feature_contributions || []).map(
      (f) => `<div class="feat-row"><span><b>${esc(f.feature)}</b> <span class="muted">(importance ${f.global_importance})</span></span><span>value ${f.value} → <b>${esc(f.percentile)}</b></span></div>`
    ).join("");
    const freeze = (ev.recommended_freeze_accounts || []).map(
      (a) => `<span class="pill bad">${esc(maskedAccount(a.account_token))} (${a.recent_withdrawals} txns/24h)</span>`
    ).join(" ") || `<span class="muted">No complaint-linked accounts active at this ATM in the last 24h.</span>`;
    const alert = state.alerts.find((a) => a.alert_id === alertId);
    const unc = ev.uncertainty || {};
    const graph = (ev.evidence_graph || []).map(
      (g, idx) => `<div class="ev-graph-row">
        <span class="ev-graph-idx">${idx + 1}</span>
        <span><b>${esc(g.signal)}</b><br/><span class="muted">${esc(g.value)}</span><br/>
          <span class="muted">direction: ${esc(g.direction)} · source: ${esc(g.source_type)} · ${esc(g.observed_or_synthetic)}</span></span>
        <span class="ev-graph-arrow">↓</span></div>`
    ).join("");
    const uncRows = [
      ["Confidence", unc.confidence || "n/a"],
      ["Evidence strength", unc.evidence_strength || "n/a"],
      ["Data freshness", unc.data_freshness_hours !== undefined && unc.data_freshness_hours !== null ? `${unc.data_freshness_hours}h` : "n/a"],
      ["Model version", unc.model_version || "n/a"],
      ["Prediction horizon", unc.prediction_horizon_hours ? `${unc.prediction_horizon_hours}h` : "n/a"],
      ["Synthetic evaluation", unc.synthetic_evaluation ? "YES" : "no"],
    ].map(([k, v]) => `<div class="feat-row"><span>${esc(k)}</span><b>${esc(String(v))}</b></div>`).join("");
    document.getElementById("ev-alert-id").textContent = ev.alert_id;
    document.getElementById("ev-body").innerHTML = `
      <div class="ev-block">
        <h3>Recency & Coverage</h3>
        <p class="ev-meta">Data through: <b>${fmtTime(ev.data_through)}</b> · ATMs scored: ${ev.atms_scored}/${ev.atms_total} (${ev.scoring_coverage_pct}%)</p>
        <p class="ev-rule">${esc(ev.suggested_action)} <span class="muted">(rule: ${esc(ev.fired_rule)})</span></p>
        <p class="ev-meta">Jurisdiction: ${esc(j.state || "—")}, ${esc(j.district || "—")} (fictional) · ${esc(j.police_station_area || "—")}</p>
        <p class="ev-meta">Recommended recipients: ${esc((ev.recommended_recipients || []).join(" · "))}</p>
      </div>
      <div class="ev-block"><h3>1. Complaint Activity</h3><p>${esc(ev.complaint_activity)}</p></div>
      <div class="ev-block"><h3>2. Withdrawal Activity</h3><p>${esc(ev.withdrawal_activity)}</p></div>
      <div class="ev-block"><h3>3. Context Signal + Source Disclosure</h3><p>${esc(ev.context_signal)}</p></div>
      <div class="ev-block"><h3>CFCFRMS Recovery Intel — block these linked accounts</h3><p>${freeze}</p>
        <p class="ev-notice">Fund-blocking via CFCFRMS path (mock intel, hackathon prototype).</p></div>
      <div class="ev-block"><h3>Recommended Actions (Response Playbook — graded, advisory)</h3>
        ${(ev.recommended_actions || []).map((a) => `<p class="ev-meta">${a.step}. ${esc(a.action)} — <b>${esc(a.owner)}</b></p>`).join("") || `<p class="ev-meta">No graded steps for this risk band.</p>`}
        <p class="ev-notice">Advisory only — no automated enforcement; audited human decision required (docs/RESPONSE_PLAYBOOK.md).</p></div>
      <div class="ev-block"><h3>Uncertainty & Evidence Metadata</h3>${uncRows}
        ${unc.insufficient_evidence ? `<p class="ev-notice" style="color:var(--yellow)">INSUFFICIENT EVIDENCE — HOLD ACTION: evidence below strength threshold or data stale. Review before any action.</p>` : ""}</div>
      <div class="ev-block"><h3>WHAT-IF (counterfactual simulation)</h3>
        ${ev.counterfactual_whatif && ev.counterfactual_whatif.current_risk !== null && ev.counterfactual_whatif.current_risk !== undefined
          ? `<p class="ev-meta">Current risk: <b>${(ev.counterfactual_whatif.current_risk * 100).toFixed(0)}%</b> · If complaint-surge signals were absent: <b>${(ev.counterfactual_whatif.risk_without_complaint_surge * 100).toFixed(0)}%</b> (delta ${(ev.counterfactual_whatif.delta * 100).toFixed(1)} pts)</p>
             <p class="ev-notice">${esc(ev.counterfactual_whatif.interpretation)}</p>`
          : `<p class="ev-meta">${esc((ev.counterfactual_whatif || {}).interpretation || "Unavailable.")}</p>`}</div>
      <div class="ev-block"><h3>Evidence Graph — why this ATM</h3>${graph}
        <p class="ev-notice">Each signal shows value, direction, source type and whether it is observed or synthetic. No unexplained AI reasoning.</p></div>
      <div class="ev-block"><h3>Indicative Feature Contributions</h3>${contribs}
        <p class="ev-notice">${esc(ev.explainability_note)}</p></div>
      <div class="ev-block"><h3>Per-instance SHAP (native XGBoost pred_contribs)</h3>
        ${(ev.per_instance_shap || []).map((f) => `<div class="feat-row"><span><b>${esc(f.feature)}</b></span><span>value ${f.value} → SHAP <b>${f.shap > 0 ? "+" : ""}${f.shap}</b></span></div>`).join("") || `<p class="muted">Unavailable for this model path.</p>`}
        <p class="ev-notice">Per-instance attribution for THIS alert's ATM — complements the global importance panel above.</p></div>
      <div class="ev-block">
        <h3>Notifications (Simulated — hackathon prototype)</h3>
        ${alert ? `<p class="ev-meta">SMS: ${esc(alert.sms_log)}</p><p class="ev-meta">Email: ${esc(alert.email_log)}</p><p class="ev-meta">I4C dispatch (webhook): ${esc(alert.dispatch_log)}</p>` : ""}
        <p class="ev-notice">No real SMS/email gateway is used; the API channel POSTs to the local mock inbox (real HTTP path).</p>
        <button class="btn accent small" id="ev-report-btn">📄 Generate Intelligence Report (PDF)</button>
      </div>`;
    document.getElementById("evidence-modal").classList.remove("hidden");
    document.getElementById("ev-report-btn").addEventListener("click", () => hotspotReport(alertId));
    auditBadge("ev-audit");
  } catch (err) { toast("Evidence failed: " + err.message); }
}

async function auditBadge(targetId) {
  try {
    const v = await api("/ledger/verify");
    document.getElementById(targetId).innerHTML = v.intact
      ? `<span class="pill ok">Ledger ✓ ${v.records}</span>` : `<span class="pill bad">Ledger TAMPERED</span>`;
  } catch { document.getElementById(targetId).innerHTML = ""; }
}

async function hotspotReport(alertId) {
  try {
    const res = await fetch(`/reports/hotspot/${alertId}`, {
      method: "POST", headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) throw new Error(res.status);
    const j = await res.json();
    toast(`Intelligence report ${j.report_id} generated (ledger-recorded)`);
  } catch (err) { toast("Report failed: " + err.message); }
}

/* ------------------------------ actions ------------------------------ */
async function setAlertStatus(alertId, status) {
  try {
    await api(`/alerts/${alertId}/status`, { method: "POST", body: JSON.stringify({ status }) });
    toast(`Alert ${alertId} → ${status} (ledger-recorded)`);
    loadAll();
  } catch (err) { toast("Update failed: " + err.message); }
}

async function updateRecovery(recId, status) {
  try {
    const amt = status === "held" ? { amount_held: 50000 } : { amount_recovered: 40000 };
    await api(`/recovery/${recId}/status`, { method: "POST", body: JSON.stringify({ status, ...amt }) });
    toast(`Recommendation ${recId} → ${status}`);
    renderBank();
  } catch (err) { toast("Update failed: " + err.message); }
}

async function runAlertCycle() {
  try {
    const r = await api("/alerts/run-now", { method: "POST" });
    const s = r.summary;
    toast(`Alert cycle: ${s.created} new · ${s.flagged} flagged · ${s.skipped} deduped`);
    loadAll();
  } catch (err) { toast("Alert cycle failed: " + err.message); }
}

/* ------------------------------ WebSocket live feed ------------------------------ */
function connectWS() {
  try {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/alerts?token=${encodeURIComponent(getToken())}`);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.event === "alert") {
          toast(`🚨 LIVE: ${msg.payload.atm_id} flagged ${(msg.payload.risk_score * 100).toFixed(0)}% (${msg.payload.city})`);
          loadAll();
        } else if (msg.event === "recovery" || msg.event === "recovery_status") {
          loadAll();
        }
      } catch { /* ignore */ }
    };
    ws.onclose = () => setTimeout(connectWS, 5000);
  } catch { /* ignore */ }
}

/* ------------------------------ login flow ------------------------------ */
function showLogin() { document.getElementById("login-modal").classList.remove("hidden"); }

function loginStatus(msg, kind) {
  const el = document.getElementById("login-status");
  if (el) {
    el.textContent = msg;
    el.className = "login-status " + (kind || "");
  }
}

async function doLogin() {
  const userEl = document.getElementById("login-username");
  const passEl = document.getElementById("login-password");
  if (!userEl || !passEl) {
    // stale cached markup (old dashboard version) — force a fresh reload
    location.reload();
    return;
  }
  const username = userEl.value.trim();
  const password = passEl.value;
  if (!username || !password) { loginStatus("Enter username and password.", "err"); return; }
  const btn = document.getElementById("btn-login");
  btn.disabled = true;
  btn.textContent = "Signing in…";
  loginStatus(`Contacting server as ${username}…`, "");
  try {
    const res = await fetch("/auth/login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) { loginStatus("Invalid credentials — check the demo users below.", "err"); return; }
    const j = await res.json();
    localStorage.setItem(TOKEN_KEY, j.access_token);
    state.user = j.user;
    document.getElementById("login-modal").classList.add("hidden");
    loginStatus(`Signed in as ${j.user.display_name} — loading data…`, "ok");
    connectWS();
    loadAll();
  } catch (err) {
    loginStatus("Sign-in failed: " + err.message + " (is the backend running?)", "err");
  } finally {
    btn.disabled = false;
    btn.textContent = "Sign in";
  }
}

/* ------------------------------ bindings ------------------------------ */
function bindEvents() {
  // Each binding is isolated so a single missing element (stale-cache page mix)
  // never kills the rest of the dashboard — especially the Sign-in button.
  const wire = (id, fn) => { const el = document.getElementById(id); if (el) el.addEventListener("click", fn); };
  wire("btn-login", doLogin);
  wire("btn-refresh", loadAll);
  wire("btn-cycle", runAlertCycle);
  wire("btn-switch", () => { localStorage.removeItem(TOKEN_KEY); showLogin(); });
  wire("ev-close", () => document.getElementById("evidence-modal").classList.add("hidden"));
  wire("btn-replay", () => {
    const val = document.getElementById("asof-date").value;
    state.asOf = val ? new Date(val + "T12:00:00").toISOString() : null;
    loadAll();
  });
  wire("btn-live", () => { state.asOf = null; document.getElementById("asof-date").value = ""; loadAll(); });
  wire("btn-ledger-verify", ledgerStatus);
  wire("btn-ledger-tamper", async () => {
    try { const r = await api("/ledger/tamper-demo", { method: "POST" }); toast(r.error || r.note); ledgerStatus(); } catch (err) { toast("Tamper demo: " + err.message); }
  });
  wire("btn-sit-report", async () => {
    try {
      const res = await fetch("/reports/situational", { method: "POST", headers: { Authorization: `Bearer ${getToken()}` } });
      if (!res.ok) throw new Error(res.status);
      const j = await res.json();
      const dl = await fetch(`/reports/${j.report_id}/download`, { headers: { Authorization: `Bearer ${getToken()}` } });
      const blob = await dl.blob();
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `${j.report_id}.pdf`; a.click();
      toast("Situational report generated (ledger-recorded)");
    } catch (err) { toast("Report failed: " + err.message); }
  });
  wire("btn-evaluate-outcomes", async () => {
    try {
      const r = await api("/alerts/outcomes/evaluate", { method: "POST" });
      toast(`Outcomes evaluated: ${r.evaluated} — monitoring updated`);
      renderOutcomes();
    } catch (err) { toast("Outcome evaluation failed: " + err.message); }
  });
  const loginPass = document.getElementById("login-password");
  if (loginPass) loginPass.addEventListener("keydown", (e) => { if (e.key === "Enter") doLogin(); });
  const evModal = document.getElementById("evidence-modal");
  if (evModal) evModal.addEventListener("click", (e) => { if (e.target.id === "evidence-modal") evModal.classList.add("hidden"); });
  const ddState = document.getElementById("dd-state");
  const ddCity = document.getElementById("dd-city");
  const ddBank = document.getElementById("dd-bank");
  if (ddState) ddState.addEventListener("change", (e) => { state.stateFilter = e.target.value; state.cityFilter = "All"; if (ddCity) ddCity.value = "All"; loadAll(); });
  if (ddCity) ddCity.addEventListener("change", (e) => { state.cityFilter = e.target.value; loadAll(); });
  if (ddBank) ddBank.addEventListener("change", (e) => { state.bankFilter = e.target.value; renderMap(); });
  const tHeat = document.getElementById("toggle-heat");
  const tFore = document.getElementById("toggle-forecast");
  if (tHeat) tHeat.addEventListener("change", (e) => { state.showHeat = e.target.checked; renderMap(); });
  if (tFore) tFore.addEventListener("change", (e) => { state.showForecast = e.target.checked; renderMap(); });

  // category chips (bind once)
  const cats = ["All", ...COMPLAINT_TYPES];
  const chipBox = document.getElementById("category-chips");
  if (chipBox) {
    chipBox.innerHTML = cats.map(
      (c) => `<span class="chip ${c === state.category ? "active" : ""}" data-cat="${esc(c)}">${esc(c)}</span>`
    ).join("");
    chipBox.querySelectorAll(".chip").forEach((el) => el.addEventListener("click", () => {
      state.category = el.dataset.cat;
      chipBox.querySelectorAll(".chip").forEach((x) => x.classList.toggle("active", x === el));
      renderMap();
    }));
  }
}

/* ------------------------------ boot ------------------------------ */
window.cashguardLogin = doLogin;  // inline onclick fallback (stale-cache-proof)
bindEvents();
// clear stale keys from older dashboard versions (role-modal era)
localStorage.removeItem("cashguard_role");
window.__cashguardReady = true;   // head script banner shows if this never runs
if (getToken()) { connectWS(); loadAll(); } else { showLogin(); }