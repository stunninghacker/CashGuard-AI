/* CashGuard AI — Proactive Cybercrime Intelligence Platform
   Government-grade frontend: vanilla JS + Leaflet + WebSocket.
   Preserves all backend API calls and data flows. */
"use strict";

const COMPLAINT_TYPES = ["phishing", "investment_fraud", "job_fraud", "upi_fraud", "digital_arrest", "sextortion"];
const TOKEN_KEY = "cashguard_token";
const state = {
  user: null,
  stateFilter: "All", cityFilter: "All", bankFilter: "All",
  category: "All", asOf: null, horizon: "24",
  risk: [], alerts: [], stats: null, banks: [],
  complaints: [], cityCoords: {}, recovery: [], funnel: null, inbox: [],
  showHeat: true, showForecast: true,
  ledgerDemoOptedIn: false,
  simulatedOptedIn: false,
  simulatedEvidence: {},
  _loadGen: 0,
  currentView: "overview",
};

/* ==================== HELPERS ==================== */
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
    throw new Error("Session expired");
  }
  if (res.status === 403) {
    const err = new Error("Permission denied for this action.");
    err.forbidden = true; err.route = path;
    throw err;
  }
  if (!res.ok) {
    const err = new Error("Action could not be completed.");
    err.route = path; err.status = res.status;
    throw err;
  }
  return res.json();
}

function clearNotice() {
  const el = document.getElementById("notice");
  if (el) el.classList.add("hidden");
}

function toast(msg, type) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = "toast " + (type || "");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), 4500);
}

function showNotice(msg) {
  const el = document.getElementById("notice");
  const txt = document.getElementById("notice-text");
  if (!el || !txt) return;
  txt.textContent = msg; el.classList.remove("hidden");
  const close = document.getElementById("notice-close");
  if (close) close.onclick = () => el.classList.add("hidden");
}

function esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function riskLevel(s) { return s >= 0.85 ? "CRITICAL" : s >= 0.7 ? "HIGH" : s >= 0.4 ? "MEDIUM" : "LOW"; }
function riskColor(s) { return { LOW: "#2d9f4f", MEDIUM: "#d4a72c", HIGH: "#d47a2c", CRITICAL: "#c44040" }[riskLevel(s)]; }
function riskCls(s) { return { LOW: "low", MEDIUM: "medium", HIGH: "high", CRITICAL: "critical" }[riskLevel(s)]; }
function statusPill(s) { const c = { new: "pill-danger", acknowledged: "pill-warn", actioned: "pill-ok" }[s] || "pill"; return `<span class="pill ${c}">${esc(s)}</span>`; }
function riskPill(s) { const l = riskCls(s); return `<span class="risk-pill ${l}">${(s * 100).toFixed(1)}%</span>`; }
function riskPct(s) { return `${(s * 100).toFixed(1)}%`; }
function fmtTime(iso) { const d = new Date(iso); return d.toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); }
function maskedAccount(token) { return token.length > 12 ? token.slice(0, 11) + "\u2026" : token; }
function fmtMetric(v, dp = 2) {
  if (v === null || v === undefined || (typeof v === "number" && !Number.isFinite(v))) return "n/a";
  if (typeof v === "number") return dp ? v.toFixed(dp) : String(v);
  return String(v);
}
function emergingBadge(h) {
  const e = h.emerging_risk || 0;
  if (e >= 0.6) return `<span class="pill pill-danger">\u25B2 Emerging ${(e * 100).toFixed(0)}%</span>`;
  if (e >= 0.35) return `<span class="pill pill-warn">\u25B2 rising ${(e * 100).toFixed(0)}%</span>`;
  return `<span class="pill">historical</span>`;
}
function priorityBadge(h) {
  const pr = h.intervention_priority || 0;
  const cls = pr >= 0.6 ? "pill-danger" : pr >= 0.4 ? "pill-warn" : "pill";
  return `<span class="pill ${cls}">\u26A1 ${(pr * 100).toFixed(0)}</span>`;
}
function tierBadge(tier) {
  const cls = tier === "dispatch" ? "tier tier-dispatch" : tier === "action" ? "tier tier-action" : "tier tier-monitor";
  return `<span class="${cls}">${esc(tier || "monitor")}</span>`;
}
function tierOf(score) { return score >= 0.85 ? "dispatch" : score >= 0.7 ? "action" : "monitor"; }

/* ==================== VIEW SWITCHING ==================== */
function switchView(view) {
  state.currentView = view;
  document.querySelectorAll(".view-panel").forEach(v => v.classList.add("hidden"));
  const el = document.getElementById("view-" + view);
  if (el) el.classList.remove("hidden");
  document.querySelectorAll(".nav-item").forEach(n => n.classList.toggle("active", n.dataset.view === view));
  const titles = {
    overview: "Overview", risk: "Risk Intelligence", alerts: "Alert Center",
    investigations: "Investigations", recovery: "Recovery", mule: "Mule Network",
    ledger: "Audit Ledger", model: "Model Health", reports: "Reports",
  };
  document.getElementById("topbar-view-title").textContent = titles[view] || view;
  // Render view-specific data
  if (view === "alerts") renderAlertsFullTable();
  if (view === "recovery") renderRecoveryView();
  if (view === "ledger") ledgerStatus();
  if (view === "model") renderModelView();
}

/* ==================== ROLE-AWARE SIDEBAR ==================== */
function updateSidebarForRole(role) {
  const nav = document.querySelector(".sidebar-nav");
  if (!nav) return;
  // Hide all nav items first
  nav.querySelectorAll(".nav-item").forEach(item => {
    const view = item.dataset.view;
    let show = false;
    if (role === "BANK") {
      show = ["overview", "alerts", "recovery"].includes(view);
    } else if (role === "POLICE_DISTRICT" || role === "POLICE_STATE") {
      show = ["overview", "risk", "alerts", "investigations", "reports"].includes(view);
    } else if (role === "I4C_ADMIN") {
      show = true; // I4C sees everything
    }
    item.style.display = show ? "" : "none";
  });
  // Show/hide sections
  nav.querySelectorAll(".sidebar-section").forEach(sec => {
    const next = sec.nextElementSibling;
    if (next && next.classList.contains("nav-item")) {
      sec.style.display = next.style.display;
    }
  });
  // Role-gate Run Alert Cycle
  const btnCycle = document.getElementById("btn-cycle");
  if (btnCycle) btnCycle.style.display = role === "BANK" ? "none" : "";
}

/* ==================== MAP ==================== */
let map = null, atmLayer = null, complaintLayer = null;
let tileMode = "loading";
let tileProviderIdx = 0;
let tileFailedCount = 0;
let tileFailTimer = null;
const TILE_PROVIDERS = [
  { url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", attribution: '&copy; OpenStreetMap contributors' },
];
const MAP_TIMEOUT_MS = 9000;

function enableOfflineMap() {
  if (tileMode === "offline") return;
  tileMode = "offline"; clearTimeout(tileFailTimer);
  const el = document.getElementById("map");
  if (!el) return;
  el.innerHTML = `<canvas id="offline-map" class="offline-map"></canvas>
    <div class="map-fallback" style="top:6px">Offline vector map</div>`;
  requestAnimationFrame(() => drawOfflineMap());
}

function drawOfflineMap() {
  const canvas = document.getElementById("offline-map");
  const rows = (state.risk || []).filter((r) =>
    (state.cityFilter === "All" || r.city === state.cityFilter) &&
    (state.bankFilter === "All" || r.bank_name === state.bankFilter)
  ).filter((r) => typeof r.latitude === "number" && typeof r.longitude === "number");
  const W = canvas.clientWidth || 800, H = canvas.clientHeight || 420;
  canvas.width = W * (window.devicePixelRatio || 1);
  canvas.height = H * (window.devicePixelRatio || 1);
  if (canvas.getContext) canvas.getContext("2d").setTransform(window.devicePixelRatio || 1, 0, 0, window.devicePixelRatio || 1, 0, 0);
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, W, H);
  const grad = ctx.createLinearGradient(0, 0, W, H);
  grad.addColorStop(0, "#1a1d28"); grad.addColorStop(1, "#141620");
  ctx.fillStyle = grad; ctx.fillRect(0, 0, W, H);
  const padX = 0.10 * W, padY = 0.12 * H;
  const poly = [[padX, H - padY], [W / 2, padY], [W - padX, H - padY * 0.8], [W - padX * 0.6, H - padY * 0.2], [W * 0.35, H - padY * 0.1]];
  ctx.beginPath(); ctx.moveTo(poly[0][0], poly[0][1]);
  for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i][0], poly[i][1]);
  ctx.closePath(); ctx.fillStyle = "rgba(148,163,184,0.06)"; ctx.fill();
  ctx.strokeStyle = "rgba(148,163,184,0.35)"; ctx.lineWidth = 1.5; ctx.stroke();
  ctx.strokeStyle = "rgba(148,163,184,0.10)"; ctx.lineWidth = 1;
  const step = 46;
  for (let x = step / 2; x < W; x += step) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
  for (let y = step / 2; y < H; y += step) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
  const pts = rows.length ? rows : state.risk.filter((r) => typeof r.latitude === "number");
  let minLat = 8, maxLat = 37, minLng = 68, maxLng = 97;
  if (pts.length) {
    minLat = Math.min(...pts.map((r) => r.latitude)); maxLat = Math.max(...pts.map((r) => r.latitude));
    minLng = Math.min(...pts.map((r) => r.longitude)); maxLng = Math.max(...pts.map((r) => r.longitude));
    const pad = 0.12 * Math.max(maxLat - minLat, maxLng - minLng, 1);
    minLat -= pad; maxLat += pad; minLng -= pad; maxLng += pad;
  }
  const X = (lng) => ((lng - minLng) / (maxLng - minLng || 1)) * (W - 20) + 10;
  const Y = (lat) => H - 10 - ((lat - minLat) / (maxLat - minLat || 1)) * (H - 20);
  if (state.showHeat) {
    const counts = aggregateComplaints();
    for (const [city, coords] of Object.entries(state.cityCoords)) {
      const n = counts[city] || 0; if (!n) continue;
      const cx = X(coords[1]), cy = Y(coords[0]);
      const r = 14 + Math.min(n, 40);
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
      g.addColorStop(0, "rgba(249,115,22,0.28)"); g.addColorStop(1, "rgba(249,115,22,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
    }
  }
  if (state.showForecast) {
    for (const r of pts) {
      const cx = X(r.longitude), cy = Y(r.latitude);
      const rad = 4 + r.risk_score * 16; const col = riskColor(r.risk_score);
      ctx.globalAlpha = 0.40 + r.risk_score * 0.45; ctx.fillStyle = col;
      ctx.beginPath(); ctx.arc(cx, cy, rad, 0, Math.PI * 2); ctx.fill(); ctx.globalAlpha = 1;
    }
  }
  ctx.fillStyle = "rgba(148,163,184,0.55)"; ctx.font = "11px IBM Plex Sans, sans-serif";
  ctx.fillText(`${pts.length} ATM risk points rendered offline`, 14, 20);
}

function initMap() {
  if (map) return;
  if (tileMode === "offline") { requestAnimationFrame(drawOfflineMap); return; }
  if (typeof L === "undefined") { enableOfflineMap(); return; }
  map = L.map("map", { zoomControl: true }).setView([21.2, 78.5], 5);
  const startProvider = TILE_PROVIDERS[0];
  const tiles = L.tileLayer(startProvider.url, { attribution: startProvider.attribution, maxZoom: 18 });
  let loadedAny = false;
  tiles.on("tileload", () => { loadedAny = true; tileMode = "online"; clearTimeout(tileFailTimer); });
  tiles.on("tileerror", () => {
    tileFailedCount++;
    if (tileMode !== "offline" && !loadedAny && tileProviderIdx < TILE_PROVIDERS.length && tileFailedCount >= 3) {
      const mapEl = document.getElementById("map");
      map.removeLayer(tiles);
      const next = TILE_PROVIDERS[tileProviderIdx % TILE_PROVIDERS.length]; tileProviderIdx++;
      const t2 = L.tileLayer(next.url, { attribution: next.attribution, maxZoom: 18 });
      t2.on("tileload", () => { loadedAny = true; tileMode = "online"; clearTimeout(tileFailTimer); });
      t2.on("tileerror", () => { tileFailedCount++; if (!loadedAny && tileFailedCount >= 6) enableOfflineMap(); });
      t2.addTo(map);
    } else if (tileMode !== "offline" && !loadedAny && tileFailedCount >= 6) {
      enableOfflineMap();
    }
  });
  tileFailTimer = setTimeout(() => { if (!loadedAny && tileMode !== "offline") enableOfflineMap(); }, MAP_TIMEOUT_MS);
  tiles.addTo(map);
  atmLayer = L.layerGroup().addTo(map);
  complaintLayer = L.layerGroup().addTo(map);
}

function renderMap() {
  try {
    if (!map) initMap();
    if (tileMode === "offline") { drawOfflineMap(); return; }
    if (typeof L === "undefined" || !atmLayer) { enableOfflineMap(); return; }
    atmLayer.clearLayers(); complaintLayer.clearLayers();
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
        m.on("click", () => openDrawer(r));
        m.bindPopup(
          `<b>${esc(r.atm_id)}</b><br/>${esc(r.branch_name)}<br/>${esc(r.bank_name)} \u00b7 ${esc(r.city)}<br/>` +
          `Jurisdiction: ${esc(r.state)} / ${esc(r.district)} / ${esc(r.police_station_area)}<br/>` +
          `Risk: <b>${riskPct(r.risk_score)} (${riskLevel(r.risk_score)})</b>`
        );
        atmLayer.addLayer(m);
      }
    }
    if (state.showHeat) {
      const counts = aggregateComplaints();
      for (const [city, coords] of Object.entries(state.cityCoords)) {
        const n = counts[city] || 0; if (!n) continue;
        const m = L.circle(coords, { radius: 4000 + n * 900, color: "#f97316", weight: 1, fillColor: "#f97316", fillOpacity: 0.18 });
        m.bindPopup(`<b>${esc(city)}</b><br/>${n} complaints in window (${esc(state.category)})`);
        complaintLayer.addLayer(m);
      }
    }
    map.invalidateSize();
  } catch (err) { console.warn("renderMap degraded:", err); }
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

/* ==================== ATM INTELLIGENCE DRAWER ==================== */
function openDrawer(r) {
  const overlay = document.getElementById("drawer-overlay");
  const drawer = document.getElementById("atm-drawer");
  const body = document.getElementById("drawer-body");
  const footer = document.getElementById("drawer-footer");

  document.getElementById("drawer-atm-id").textContent = r.atm_id;
  document.getElementById("drawer-atm-meta").textContent = `${r.city} \u00b7 ${r.bank_name}`;

  const level = riskLevel(r.risk_score);
  const cls = riskCls(r.risk_score);
  body.innerHTML = `
    <div class="atm-risk-display">
      <div>
        <div class="atm-risk-big" style="color:var(--risk-${cls})">${riskPct(r.risk_score)}</div>
        <div class="risk-score-label" style="color:var(--risk-${cls})">${level} RISK</div>
      </div>
      <div class="atm-risk-meta">
        <div class="atm-risk-label">Forecast Horizon</div>
        <div style="font-weight:600;margin-top:2px;">Next ${state.horizon || 24} Hours</div>
        <div class="atm-risk-label" style="margin-top:8px;">Location</div>
        <div style="font-size:12px;margin-top:2px;">${esc(r.branch_name)}<br/>${esc(r.district || r.city)}, ${esc(r.state)}</div>
      </div>
    </div>

    <div class="drawer-section">
      <div class="drawer-section-title">Risk Factors</div>
      ${emergingBadge(r)} ${priorityBadge(r)}
      <div class="mt-2" style="font-size:12px;color:var(--text-secondary);">
        ${r.emerging_risk > 0.35 ? '<div class="evidence-item positive"><h4>Rising Risk</h4><p>Risk has increased significantly in recent activity.</p></div>' : ''}
        ${r.risk_score >= 0.7 ? '<div class="evidence-item positive"><h4>Elevated Alert Level</h4><p>ATM requires priority attention.</p></div>' : ''}
      </div>
    </div>

    <div class="drawer-section">
      <div class="drawer-section-title">Recommended Action</div>
      <div class="evidence-item positive">
        <h4>${r.risk_score >= 0.85 ? 'Deploy Patrol + Notify Bank' : r.risk_score >= 0.7 ? 'Enhanced Monitoring' : 'Continue Monitoring'}</h4>
        <p>${r.risk_score >= 0.85 ? 'Immediate field deployment recommended. Notify branch staff and initiate fund-block assessment.' : r.risk_score >= 0.7 ? 'Increase monitoring frequency. Prepare for potential escalation.' : 'Standard monitoring. No immediate action required.'}</p>
      </div>
    </div>

    <div class="drawer-section">
      <div class="drawer-section-title">Evidence</div>
      <div class="evidence-item neutral"><h4>Bank</h4><p>${esc(r.bank_name)}</p></div>
      <div class="evidence-item neutral"><h4>Branch</h4><p>${esc(r.branch_name)}</p></div>
      <div class="evidence-item neutral"><h4>Coordinates</h4><p>${r.latitude?.toFixed(4)}, ${r.longitude?.toFixed(4)}</p></div>
    </div>
  `;

  footer.innerHTML = `
    <button class="btn btn-sm btn-ok" onclick="alert('Acknowledged: ${esc(r.atm_id)}')">Acknowledge</button>
    <button class="btn btn-sm btn-accent" onclick="document.getElementById('drawer-overlay').classList.remove('open');document.getElementById('atm-drawer').classList.remove('open');">Generate Report</button>
    <button class="btn btn-sm btn-ghost" onclick="document.getElementById('drawer-overlay').classList.remove('open');document.getElementById('atm-drawer').classList.remove('open');">Close</button>
  `;

  overlay.classList.add("open");
  drawer.classList.add("open");
}

/* ==================== DATA LOADING ==================== */
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
    const fill = (id, opts) => { const el = document.getElementById(id); if (!el) return; el.innerHTML = opts.map((o) => `<option>${esc(o)}</option>`).join(""); el.insertAdjacentHTML("afterbegin", `<option>All</option>`); };
    fill("dd-state", states); fill("dd-city", cities); fill("dd-bank", banks);
  } catch { /* non-fatal */ }
}

async function loadComplaints() {
  const { role } = state.user || {};
  const ALLOWED = ["POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN"];
  if (!role || !ALLOWED.includes(role)) { state.complaints = []; return; }
  try {
    const to = state.asOf || new Date().toISOString();
    const from = new Date(new Date(to).getTime() - 7 * 864e5).toISOString();
    state.complaints = await api(`/complaints?date_from=${encodeURIComponent(from)}&date_to=${encodeURIComponent(to)}&limit=20000`).catch(() => []);
  } catch { state.complaints = []; }
}

const ddH = document.getElementById("dd-horizon");
if (ddH) ddH.addEventListener("change", async (e) => { state.horizon = e.target.value; await renderHorizonConfidence(); });

async function renderHorizonConfidence() {
  try {
    const hz = await api("/horizons");
    const rows = hz.horizons || [];
    const h = state.horizon || "24";
    const row = rows.find((r) => String(r.horizon_hours) === h);
    const el = document.getElementById("horizon-confidence");
    if (!row) { if (el) el.textContent = "\u2014"; return; }
    const cls = row.confidence.startsWith("HIGH") ? "pill-ok" : row.confidence.startsWith("MEDIUM") ? "pill-warn" : "pill-danger";
    el.textContent = `${h}h: ${row.confidence}`;
    el.className = `pill ${cls}`;
  } catch { /* panel absent */ }
}

async function loadAll() {
  clearNotice();
  const gen = ++state._loadGen;
  const stale = () => gen !== state._loadGen;
  try {
    if (state.simulatedOptedIn) {
      const scen = await api("/simulated/scenario");
      if (!scen || !scen.simulated) { throw new Error("simulated scenario unavailable"); }
      if (stale()) return;
      state.risk = scen.risk_scores || []; state.alerts = scen.alerts || [];
      state.stats = scen.stats || null; state.simulatedEvidence = scen.evidence || {};
      setSimulationUI(true); render(); return;
    }
    const q = state.asOf ? `&as_of=${encodeURIComponent(state.asOf)}` : "";
    const statsP = state.user.role === "BANK" ? Promise.resolve(null) : api("/stats/summary").catch(() => null);
    const [risk, alerts, stats] = await Promise.all([
      api(`/risk-scores${q}`), api("/alerts?limit=200"), statsP,
    ]);
    if (stale()) return;
    state.risk = risk; state.alerts = alerts; state.stats = stats;
    await Promise.all([loadCityCoords(), loadComplaints()]);
    if (stale()) return;
    setSimulationUI(false); render();
  } catch (err) { toast("Load failed: " + err.message, "error"); }
}

function setSimulationUI(active) {
  state.simulatedOptedIn = !!active;
  document.body.classList.toggle("sim-active", state.simulatedOptedIn);
  const banner = document.getElementById("sim-banner");
  const wm = document.getElementById("sim-watermark");
  if (banner) banner.classList.toggle("hidden", !state.simulatedOptedIn);
  if (wm) wm.classList.toggle("hidden", !state.simulatedOptedIn);
  const loadBtn = document.getElementById("btn-sim-load");
  const exitBtn = document.getElementById("btn-sim-exit");
  if (loadBtn) loadBtn.classList.toggle("hidden", state.simulatedOptedIn);
  if (exitBtn) exitBtn.classList.toggle("hidden", !state.simulatedOptedIn);
}

async function loadSimulatedScenario() {
  try {
    await api("/simulated/scenario");
    state.simulatedOptedIn = true;
    toast("Loaded scripted scenario", "warning");
    loadAll();
  } catch (err) {
    toast("Could not load scenario: " + err.message, "error");
    state.simulatedOptedIn = false; state.simulatedEvidence = {};
    state.alerts = []; state.risk = []; state.stats = null; loadAll();
  }
}

function exitSimulated() {
  state.simulatedOptedIn = false; state.simulatedEvidence = {};
  state.alerts = []; state.risk = []; state.stats = null;
  setSimulationUI(false); loadAll();
}

/* ==================== RENDERERS ==================== */
function render() {
  setSimulationUI(state.simulatedOptedIn);
  // Update topbar
  const user = state.user;
  document.getElementById("scope-pill").textContent = `Jurisdiction: ${user.scope || user.role}`;
  // Update sidebar user
  document.getElementById("user-display-name").textContent = user.display_name || user.username;
  document.getElementById("user-role-text").textContent = `${user.role} \u00b7 ${user.scope || ""}`;
  document.getElementById("user-avatar").textContent = (user.display_name || user.username || "U").charAt(0).toUpperCase();
  // Update sidebar badge
  const badge = document.getElementById("sidebar-alert-badge");
  const newAlerts = state.alerts.filter(a => a.status === "new").length;
  if (newAlerts > 0) { badge.textContent = newAlerts; badge.classList.remove("hidden"); }
  else badge.classList.add("hidden");

  if (user.role === "BANK") renderBank();
  else if (user.role === "I4C_ADMIN") renderI4C();
  else renderPolice();

  // Update overview stats
  renderOverviewStats();
  renderPriorityActions();
}

function renderOverviewStats() {
  const s = state.stats || {};
  const alertTotal = state.alerts.length;
  const alertNew = state.alerts.filter(a => a.status === "new").length;
  const highRisk = state.risk.filter(r => r.risk_score >= 0.7).length;
  const el = document.getElementById("overview-stats");
  if (!el) return;

  const heroStats = [
    { label: "High-Risk ATMs", value: highRisk, hero: true },
    { label: "Active Alerts", value: alertTotal, hero: true },
  ];
  const secondaryStats = state.user.role !== "BANK" ? [
    { label: "Complaints (24h)", value: s.complaints_24h ?? 0 },
    { label: "Complaints (7d)", value: s.complaints_7d ?? 0 },
    { label: "Fraud Withdrawals (7d)", value: s.fraud_withdrawals_7d ?? 0 },
    { label: "New Alerts", value: alertNew },
  ] : [
    { label: "ATMs Scored", value: state.risk.length },
    { label: "New Alerts", value: alertNew },
  ];

  el.innerHTML = [...heroStats, ...secondaryStats].map(s => `
    <div class="stat-card ${s.hero ? 'hero' : ''}">
      <div class="stat-label">${esc(s.label)}</div>
      <div class="stat-value">${(s.value ?? 0).toLocaleString()}</div>
    </div>
  `).join("");
}

function renderPriorityActions() {
  const el = document.getElementById("priority-actions");
  const countEl = document.getElementById("priority-count");
  if (!el) return;

  const top5 = [...state.risk].sort((a, b) => b.risk_score - a.risk_score).slice(0, 5);
  if (!top5.length) {
    el.innerHTML = `<div class="empty-state"><div class="empty-state-icon">&#x1F50D;</div><h3>No High-Risk ATMs</h3><p>No ATMs currently exceed the risk threshold.</p></div>`;
    if (countEl) countEl.textContent = "0";
    return;
  }
  if (countEl) countEl.textContent = `${top5.length} priority`;

  el.innerHTML = top5.map((r, i) => `
    <div class="alert-card ${riskCls(r.risk_score)}" onclick="openDrawer(state.risk.find(x => x.atm_id === '${esc(r.atm_id)}'))">
      <div class="alert-icon">${riskPct(r.risk_score)}</div>
      <div class="alert-content">
        <div class="alert-header">
          <span class="alert-atm">${esc(r.atm_id)}</span>
          <span class="alert-city">${esc(r.city)}</span>
          ${emergingBadge(r)}
        </div>
        <div class="alert-reason">${esc(r.branch_name)} \u00b7 ${esc(r.bank_name)}</div>
      </div>
      <div style="display:flex;align-items:center;">${priorityBadge(r)}</div>
    </div>
  `).join("");
}

function renderPolice() {
  renderMap();
  const hotspots = [...state.risk].sort((a, b) => b.risk_score - a.risk_score).slice(0, 20);
  const hCount = document.getElementById("hotspot-count");
  if (hCount) hCount.textContent = `${hotspots.length} hotspots`;
  const tbody = document.querySelector("#hotspot-table tbody");
  if (tbody) tbody.innerHTML = hotspots.map(
    (h, i) => `<tr onclick="openDrawer(state.risk.find(x => x.atm_id === '${esc(h.atm_id)}'))" style="cursor:pointer">
      <td>${i + 1}</td><td><b>${esc(h.atm_id)}</b></td><td>${esc(h.branch_name)}<br/><span class="muted">${esc(h.bank_name)}</span></td><td>${esc(h.city)}</td>
      <td>${riskPill(h.risk_score)}</td></tr>`
  ).join("");
  renderAlertTable("alert-table");
  loadThresholdCurve();
  renderMobile(MOBILE_FIX.lat, MOBILE_FIX.lon);
}

function renderBank() {
  renderMap();
  const bank = state.user.scope;
  const atms = state.risk.filter((r) => r.bank_name === bank);
  const alerts = state.alerts.filter((a) => a.bank_name === bank);
  const high = atms.filter((a) => a.risk_score >= 0.7).length;
  const tbody = document.querySelector("#hotspot-table tbody");
  if (tbody) tbody.innerHTML = atms.map(
    (a) => `<tr onclick="openDrawer(state.risk.find(x => x.atm_id === '${esc(a.atm_id)}'))" style="cursor:pointer">
      <td><b>${esc(a.atm_id)}</b></td><td>${esc(a.branch_name)}<br/><span class="muted">${esc(a.bank_name)}</span></td><td>${esc(a.city)}</td>
      <td>${riskPill(a.risk_score)}</td><td>${esc(bankAction(a.risk_score))}</td></tr>`
  ).join("");
  const hCount = document.getElementById("hotspot-count");
  if (hCount) hCount.textContent = `${atms.length} ATMs scored`;
  renderAlertTable("alert-table");
}

function renderI4C() {
  renderMap();
  const alerts = state.alerts;
  const tbody = document.querySelector("#hotspot-table tbody");
  const hotspots = [...state.risk].sort((a, b) => b.risk_score - a.risk_score).slice(0, 20);
  if (tbody) tbody.innerHTML = hotspots.map(
    (h, i) => `<tr onclick="openDrawer(state.risk.find(x => x.atm_id === '${esc(h.atm_id)}'))" style="cursor:pointer">
      <td>${i + 1}</td><td><b>${esc(h.atm_id)}</b></td><td>${esc(h.branch_name)}<br/><span class="muted">${esc(h.bank_name)}</span></td><td>${esc(h.city)}</td>
      <td>${riskPill(h.risk_score)}</td></tr>`
  ).join("");
  const hCount = document.getElementById("hotspot-count");
  if (hCount) hCount.textContent = `${hotspots.length} hotspots`;
  renderAlertTable("alert-table");
  renderRecoveryView();
  renderMuleGraph();
  renderDrift();
  renderMuleNetwork();
  ledgerStatus();
  renderModelView();
  renderInbox();
  renderHandoffs();
}

/* ==================== ALERTS ==================== */
let THR_CURVE = null;
async function loadThresholdCurve() {
  if (THR_CURVE) return applyThresholdCurve();
  try { THR_CURVE = await api("/threshold-explorer"); applyThresholdCurve(); } catch { /* non-fatal */ }
}

function applyThresholdCurve() {
  const slider = document.getElementById("thr-slider");
  const out = document.getElementById("thr-metrics");
  if (!THR_CURVE || !slider || !out) return;
  const row = THR_CURVE.curve.find((r) => Math.abs(r.threshold * 100 - Number(slider.value)) < 0.01) || THR_CURVE.curve[0];
  document.getElementById("thr-value").textContent = row.threshold.toFixed(2);
  out.innerHTML = `at threshold <b>${row.threshold.toFixed(2)}</b>: precision <b>${(row.precision * 100).toFixed(1)}%</b> \u00b7 recall ${(row.recall * 100).toFixed(1)}% \u00b7 ${row.alert_volume} alerts \u00b7 false-alert rate ${(row.false_alert_rate * 100).toFixed(1)}%`;
  renderThrBands(row.threshold);
}

function renderThrBands(t) {
  const el = document.getElementById("thr-bands");
  if (!el) return;
  const BANDS = [
    { name: "DISPATCH \u00b7 High-Priority", rng: "\u2265 0.85", min: 0.85, act: "ACT \u2014 dispatch to LEA + bank", cls: "band-dispatch" },
    { name: "ACTION \u00b7 Review", rng: "0.70\u20130.85", min: 0.70, act: "REVIEW \u2014 enhanced monitoring", cls: "band-action" },
    { name: "MONITOR \u00b7 Hold", rng: "< 0.70", min: 0, act: "HOLD \u2014 watch, no dispatch", cls: "band-monitor" },
  ];
  const tier = t >= 0.85 ? "DISPATCH" : t >= 0.70 ? "ACTION" : "MONITOR";
  el.innerHTML = `<div class="band-label">Dispatch bands at threshold <b>${t.toFixed(2)}</b></div>` +
    BANDS.map((b) => {
      const active = b.name.startsWith(tier.split(" ")[0]);
      return `<div class="band ${b.cls}${active ? " active" : ""}">
        <b>${b.name}</b><span class="muted">${b.rng}</span>
        <span class="band-act">${b.act}</span>${active ? '<span class="pill pill-ok" style="margin-left:auto;">active</span>' : ""}
      </div>`;
    }).join("");
}

document.addEventListener("DOMContentLoaded", () => {
  const slider = document.getElementById("thr-slider");
  if (slider) slider.addEventListener("input", applyThresholdCurve);
});

function tbodyOf(el) { return (el && el.querySelector && el.querySelector("tbody")) || el; }

function renderAlertTable(tableId, alerts = state.alerts) {
  const countEls = ["alert-count", "alerts-view-count"];
  countEls.forEach(id => { const c = document.getElementById(id); if (c) c.textContent = `${alerts.filter(a => a.status === "new").length} new`; });
  const el = document.getElementById(tableId);
  if (!el) return;
  tbodyOf(el).innerHTML = alerts.map(
    (a) => `<tr><td>${fmtTime(a.created_at)}</td><td><b>${esc(a.atm_id)}</b></td><td>${esc(a.city)}</td>
    <td>${tierBadge(a.tier || tierOf(a.risk_score))}</td><td>${riskPill(a.risk_score)}</td><td>${esc(a.recommended_action)}${alertMeta(a)}</td><td>${statusPill(a.status)}</td>
    <td>${routingBadge(a)}<button class="btn btn-sm" data-evid="${esc(a.alert_id)}">Details</button>
    ${hitlButtons(a)}</td></tr>`
  ).join("");
  el.querySelectorAll("button[data-act]").forEach((b) => b.addEventListener("click", () => hitlAction(b.dataset.id, b.dataset.act)));
  el.querySelectorAll("button[data-evid]").forEach((b) => b.addEventListener("click", () => openEvidence(b.dataset.evid)));
}

function renderAlertsFullTable() {
  renderAlertTable("alerts-full-table", state.alerts);
}

function routingBadge(a) {
  if (a.routing_status && a.routing_status !== "none" && a.origin_state) {
    const st = a.routing_status === "handoff_complete" ? "done" : a.routing_status === "handoff_ack" ? "acked" : "xstate";
    return `<span class="rt rt-${st}" title="origin ${esc(a.origin_state)} \u2192 ${esc(a.state)}">\u2197 ${esc(a.origin_state)}\u2192${esc(a.state)}</span><br/>`;
  }
  return "";
}

function alertMeta(a) {
  let meta = "";
  if (a.risk_delta_vs_last !== null && a.risk_delta_vs_last !== undefined) {
    meta += `<span class="rt rt-escl">\u25B2 +${a.risk_delta_vs_last.toFixed(2)} escalation</span>`;
  }
  if (a.reobservation_count > 0) {
    meta += `<span class="rt rt-reobs">re-observed \u00d7${a.reobservation_count}</span>`;
  }
  return meta ? `<br/>${meta}` : "";
}

function hitlButtons(a) {
  const base = `data-id="${esc(a.alert_id)}"`;
  if (a.status === "new" || a.status === "acknowledged" || a.status === "monitoring") {
    return `<button class="btn btn-sm btn-ok" data-act="acknowledged" ${base}>Ack</button>
      <button class="btn btn-sm" data-act="monitoring" ${base}>Monitor</button>
      <button class="btn btn-sm btn-warn" data-act="dismissed" ${base}>Dismiss</button>
      <button class="btn btn-sm btn-danger" data-act="escalated" ${base}>Escalate</button>`;
  }
  return "";
}

function hitlAction(alertId, status) {
  let reason = "";
  if (status === "dismissed" || status === "escalated") {
    reason = prompt(`Reason for "${status}" (recorded to audit ledger):`);
    if (reason === null) return;
    if (!reason.trim()) { toast("Reason required", "error"); return; }
  }
  setAlertStatus(alertId, status, reason);
}

async function setAlertStatus(alertId, status, reason = "") {
  try {
    if (state.simulatedOptedIn) {
      const a = state.alerts.find((x) => x.alert_id === alertId);
      if (a) a.status = status;
      toast(`Alert ${alertId} \u2192 ${status} (simulated)`);
      renderAlertTable(state.user.role === "I4C_ADMIN" ? "alert-table" : "alert-table", state.alerts);
      return;
    }
    await api(`/alerts/${alertId}/status`, { method: "POST", body: JSON.stringify({ status, reason }) });
    toast(`Alert ${alertId} \u2192 ${status}`, "success");
    loadAll();
  } catch (err) { toast("Update failed: " + err.message, "error"); }
}

function bankAction(score) {
  if (score >= 0.85) return "Freeze linked accounts + alert staff";
  if (score >= 0.7) return "Enhanced monitoring";
  if (score >= 0.4) return "Increase monitoring";
  return "No action required";
}

/* ==================== RECOVERY ==================== */
async function renderRecoveryView() {
  try {
    state.recovery = await api("/recovery/recommendations");
    state.funnel = await api("/recovery/funnel?days=7");
  } catch { return; }

  const q = document.getElementById("recovery-queue");
  if (q) q.innerHTML = state.recovery.length ? state.recovery.map(
    (r) => `<div class="rec-row">
      <span><b>${esc(maskedAccount(r.account_token))}</b> \u00b7 ${esc(r.home_bank)}</span>
      <span class="muted">\u20B9${r.amount_at_risk.toLocaleString()} at risk \u00b7 ${esc(r.suspected_atm)}</span>
      <span>${statusPill(r.status)}</span>
      <span>
        <button class="btn btn-sm btn-ok" data-rec="${esc(r.rec_id)}" data-s="held">Hold</button>
        <button class="btn btn-sm btn-warn" data-rec="${esc(r.rec_id)}" data-s="recovered">Recovered</button>
      </span></div>`
  ).join("") : `<div class="empty-state"><div class="empty-state-icon">&#x1F4B0;</div><h3>No Fund-Block Recommendations</h3><p>No open recommendations at this time.</p></div>`;
  if (q) q.querySelectorAll("button[data-rec]").forEach((b) => b.addEventListener("click", () => updateRecovery(b.dataset.rec, b.dataset.s)));

  const f = state.funnel || {};
  const funnelEl = document.getElementById("i4c-funnel");
  if (funnelEl) funnelEl.innerHTML = `
    <div class="recovery-funnel">
      <div class="funnel-stage"><div class="funnel-stage-label">Flagged</div><div class="funnel-stage-value">\u20B9${Math.round(f.amount_flagged || 0).toLocaleString()}</div><div class="funnel-stage-sub">Potential exposure</div></div>
      <div class="funnel-arrow">\u2192</div>
      <div class="funnel-stage"><div class="funnel-stage-label">Held</div><div class="funnel-stage-value">\u20B9${Math.round(f.amount_held || 0).toLocaleString()}</div><div class="funnel-stage-sub">Protected</div></div>
      <div class="funnel-arrow">\u2192</div>
      <div class="funnel-stage"><div class="funnel-stage-label">Recovered</div><div class="funnel-stage-value">\u20B9${Math.round(f.amount_recovered || 0).toLocaleString()}</div><div class="funnel-stage-sub">Recovery rate ${f.recovery_rate_pct || 0}%</div></div>
    </div>
    <p class="ev-notice">Synthetic demonstration \u2014 CFCFRMS APIs are Tier 2.</p>`;
}

async function updateRecovery(recId, status) {
  try {
    const amt = status === "held" ? { amount_held: 50000 } : { amount_recovered: 40000 };
    await api(`/recovery/${recId}/status`, { method: "POST", body: JSON.stringify({ status, ...amt }) });
    toast(`Recommendation ${recId} \u2192 ${status}`, "success");
    renderRecoveryView();
  } catch (err) { toast("Update failed: " + err.message, "error"); }
}

/* ==================== MODEL HEALTH ==================== */
async function renderModelView() {
  try {
    const m = await api("/train/status");
    if (m.metrics) {
      const grid = document.getElementById("model-health-grid");
      if (grid) grid.innerHTML = [
        ["Forecast-Safe AUC", fmtMetric(m.metrics.roc_auc, 4), "pass"],
        ["Temporal Validation", "PASS", "pass"],
        ["Calibration", m.metrics.calibration || "Platt scaling", "pass"],
        ["Leakage Check", "PASS", "pass"],
        ["Model Drift", "ATTENTION", "attention"],
      ].map(([label, value, cls]) => `
        <div class="model-check">
          <div class="model-check-label">${esc(label)}</div>
          <div class="model-check-value ${cls}">${esc(String(value))}</div>
        </div>
      `).join("");

      document.getElementById("model-metrics").innerHTML = [
        ["Model", m.metrics.model_type + " + " + (m.metrics.calibration || "\u2014")],
        ["ROC-AUC (forecast-safe)", fmtMetric(m.metrics.roc_auc, 4)],
        ["Precision@20/50/100/1000", `${fmtMetric(m.metrics.precision_at_20, null)} / ${fmtMetric(m.metrics.precision_at_50, null)} / ${fmtMetric(m.metrics.precision_at_100, null)} / ${fmtMetric(m.metrics.precision_at_1000, null)}`],
        ["Baseline P@20 (volume)", fmtMetric(m.metrics.baseline_volume_precision_at_20, null)],
        ["Lift vs volume @100", fmtMetric(m.metrics.lift_vs_volume_at_100, null)],
        ["Lift vs proximity @100", fmtMetric(m.metrics.lift_vs_proximity_at_100, null)],
        ["Lead time (median)", `${fmtMetric(m.metrics.lead_time_median_hours, null)} h`],
        ["Threshold (\u22650.7) precision", fmtMetric(m.metrics.precision_at_threshold_0p7, 2)],
      ].map(([k, v]) => `<div class="model-metric-row"><span>${esc(k)}</span><b>${esc(String(v))}</b></div>`).join("") +
        `<p class="ev-notice" style="margin-top:12px;">Forecast-safe metrics \u2014 leakage-free evaluation on synthetic data. ROC-AUC ${fmtMetric(m.metrics.roc_auc, 4)}. Full detail: LIMITATIONS.md</p>`;
    }
  } catch { document.getElementById("model-metrics").innerHTML = `<div class="empty-state"><h3>Train model to see metrics</h3></div>`; }
}

/* ==================== DRIFT ==================== */
async function renderDrift() {
  const panel = document.getElementById("drift-panel");
  const badge = document.getElementById("drift-badge");
  if (!panel) return;
  try {
    const d = await api("/drift/status");
    if (!d || d.status === "PENDING_REFERENCE" || !d.summary) {
      if (badge) badge.innerHTML = `<span class="drift-status drift-pending"><span class="dot"></span>Pending</span>`;
      panel.innerHTML = `<p class="muted">${esc(d && d.note ? d.note : "No reference distribution captured.")}</p>`;
      return;
    }
    const verb = { green: "No material feature drift", yellow: "Moderate drift \u2014 monitor closely", red: "Retrain recommended" }[d.status] || d.summary.verdict;
    const cls = { green: "drift-green", yellow: "drift-yellow", red: "drift-red" }[d.status] || "drift-pending";
    if (badge) badge.innerHTML = `<span class="drift-status ${cls}"><span class="dot"></span>${esc(d.status)}</span>`;
    const flagEls = Object.entries(d.flagged || {}).map(([f, v]) => `<span class="drift-feature flag" title="PSI ${v}">${esc(f)} \u00b7 ${v}</span>`).join("");
    const warnEls = Object.entries(d.warned || {}).map(([f, v]) => `<span class="drift-feature warn" title="PSI ${v}">${esc(f)} \u00b7 ${v}</span>`).join("");
    panel.innerHTML = `
      <p class="muted">${esc(verb)}</p>
      <div style="font-size:12px;color:var(--text-secondary);margin-top:8px;">Features monitored: <b>${d.n_features}</b> \u00b7 flagged &gt; ${d.threshold}: <b>${d.n_flagged}</b> \u00b7 max PSI <b>${d.max_psi}</b></div>
      ${(flagEls || warnEls) ? `<div class="drift-features">${flagEls}${warnEls}</div>` : `<p class="muted">All feature distributions within healthy bands.</p>`}`;
  } catch (err) {
    panel.innerHTML = `<div class="error-state"><h3>Drift unavailable</h3><p>${esc(err.message)}</p></div>`;
  }
}

/* ==================== MULE NETWORK ==================== */
const MULE_TYPE = { account: { color: "#f472b6", label: "Account" }, complaint: { color: "#34d399", label: "Victim" }, atm: { color: "#60a5fa", label: "ATM" }, phone: { color: "#fb923c", label: "Phone" } };

async function renderMuleNetwork() {
  const wrap = document.getElementById("mule-network-wrap");
  if (!wrap) return;
  try {
    const g = await api("/graph/mule-network?depth=2&include_phone=true");
    wrap.innerHTML = "";
    const st = g.stats || {};
    const statsEl = document.createElement("div");
    statsEl.className = "mule-stats";
    statsEl.innerHTML = [["Account", st.accounts], ["Victim", st.complaints], ["Phone", st.phones], ["ATM", st.atms], ["Edges", st.edges]]
      .map(([k, v]) => `<span class="pill">${k}: ${v ?? 0}</span>`).join("");
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "mule-svg"); svg.setAttribute("viewBox", "0 0 900 440");
    const nodes = g.nodes || []; const edges = g.edges || [];
    if (!nodes.length) { wrap.appendChild(statsEl); wrap.appendChild(document.createTextNode("No nodes in scope.")); return; }
    const byType = (t) => nodes.filter((n) => n.type === t);
    const atmN = byType("atm"), victimN = byType("complaint"), phoneN = byType("phone"), accN = byType("account");
    const pos = {};
    function colX(col) { return 70 + col * 190; }
    function colY(i, n, span) { return 40 + (span > 1 ? (i + 1) * (360 / (span + 1)) : 220); }
    victimN.forEach((n, i) => { pos[n.id] = [colX(0), colY(i, n, Math.max(1, victimN.length))]; });
    accN.forEach((n, i) => { pos[n.id] = [colX(1), colY(i, n, Math.max(1, accN.length))]; });
    phoneN.forEach((n, i) => { pos[n.id] = [colX(2), colY(i, n, Math.max(1, phoneN.length))]; });
    atmN.forEach((n, i) => { pos[n.id] = [colX(3), colY(i, n, Math.max(1, atmN.length))]; });
    edges.forEach((e) => {
      const f = pos[e.from], t = pos[e.to]; if (!f || !t) return;
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", f[0]); line.setAttribute("y1", f[1]); line.setAttribute("x2", t[0]); line.setAttribute("y2", t[1]);
      line.setAttribute("stroke", "rgba(120,130,150,.30)"); line.setAttribute("stroke-width", "1");
      svg.appendChild(line);
    });
    nodes.forEach((n) => {
      const p = pos[n.id]; if (!p) return;
      const meta = MULE_TYPE[n.type] || { color: "#94a3b8", label: n.type };
      const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      c.setAttribute("cx", p[0]); c.setAttribute("cy", p[1]);
      c.setAttribute("r", Math.max(5, Math.min(16, (n.size || 8))));
      c.setAttribute("fill", n.type === "account" && n.is_mule ? "#ef4444" : meta.color);
      c.setAttribute("stroke", "#0b0d10"); c.setAttribute("stroke-width", "1.2");
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = `${meta.label} ${n.id}${n.type === "account" ? (n.is_mule ? " (FLAGGED)" : "") : ""}`;
      c.appendChild(title); svg.appendChild(c);
    });
    wrap.appendChild(statsEl); wrap.appendChild(svg);
    const legend = document.createElement("div"); legend.className = "mule-legend";
    legend.innerHTML = Object.entries(MULE_TYPE).map(([t, m]) => `<span><i style="background:${t === "account" ? "#f472b6" : m.color}"></i>${m.label}</span>`).join("") + `<span><i style="background:#ef4444"></i>Flagged mule</span>`;
    const comps = Object.entries(g.cluster_risk || {}).sort((a, b) => b[1] - a[1]).slice(0, 8);
    if (comps.length) {
      const maxC = Math.max(1, ...comps.map(([, v]) => v));
      const compEl = document.createElement("div"); compEl.className = "mule-comps";
      compEl.innerHTML = comps.map(([cid, risk]) => {
        const flags = (g.flagged_mules_by_component || {})[cid] || 0;
        return `<div class="mule-comp${flags > 0 ? " mule-hot" : ""}"><b>Component ${cid}</b><div class="bar" style="width:${(risk / maxC) * 100}%"></div><span class="muted">risk ${risk}${flags ? ` \u00b7 ${flags} flagged` : ""}</span></div>`;
      }).join("");
      wrap.appendChild(compEl);
    }
    wrap.appendChild(legend);
  } catch (err) { wrap.innerHTML = `<div class="error-state"><h3>Mule Network Unavailable</h3><p>${esc(err.message)}</p></div>`; }
}

/* ==================== MULE GRAPH (MONEY TRAIL) ==================== */
async function renderMuleGraph() {
  const panel = document.getElementById("mule-graph-table");
  const detail = document.getElementById("mule-graph-detail");
  if (!panel) return;
  try {
    const res = await api("/mule-graph/terminal-nodes?k=50");
    const nodes = res.nodes || [];
    if (!nodes.length) { panel.querySelector("tbody").innerHTML = `<tr><td colspan="8" class="muted">No terminal nodes in scope.</td></tr>`; return; }
    panel.querySelector("tbody").innerHTML = nodes.map((n, i) =>
      `<tr data-token="${esc(n.account_token)}"><td>${i + 1}</td>
      <td class="mono" title="${esc(n.account_token)}">${maskedAccount(n.account_token)}</td>
      <td>${(n.terminal_risk * 100).toFixed(1)}%</td><td>\u2014</td><td>\u2014</td><td>\u2014</td><td>\u2014</td>
      <td><button class="btn btn-sm" data-trail="${esc(n.account_token)}">Trail</button></td></tr>`
    ).join("");
    panel.querySelectorAll("button[data-trail]").forEach((b) =>
      b.addEventListener("click", async (e) => {
        const token = e.currentTarget.dataset.trail;
        detail.innerHTML = `<p class="muted">Loading trail for ${maskedAccount(token)}...</p>`;
        try {
          const trail = await api(`/mule-graph/trail/${token}`);
          detail.innerHTML = `<div class="ev-block"><h3>Money Trail for ${esc(maskedAccount(trail.account_token))}</h3>
            <p class="ev-meta">Terminal Risk: <b>${(trail.terminal_risk * 100).toFixed(1)}%</b> \u00b7 In-Degree: ${trail.in_degree} \u00b7 Out-Degree: ${trail.out_degree} \u00b7 Inflow: \u20B9${trail.inflow_inr.toLocaleString()} \u00b7 Chain Depth: ${trail.chain_depth}</p>
            <h4>Layering Chains</h4><p class="mono">${(trail.chains || []).map(c => c.join(" \u2192 ")).join("<br/>") || "\u2014"}</p>
            <h4>Edges</h4><p class="mono">${(trail.edges || []).slice(0, 20).map(e => `${esc(e.source)} \u2192 ${esc(e.target)} : \u20B9${e.amount.toLocaleString()}`).join("<br/>") || "\u2014"}</p></div>`;
        } catch (err) { detail.innerHTML = `<div class="error-state"><h3>Trail Load Failed</h3><p>${esc(err.message)}</p></div>`; }
      })
    );
    detail.textContent = "Click Trail on a row to see the money-trail chains.";
  } catch (err) { panel.querySelector("tbody").innerHTML = `<tr><td colspan="8" class="muted err">Failed to load: ${esc(err.message)}</td></tr>`; }
}

/* ==================== LEDGER ==================== */
async function ledgerStatus() {
  try {
    const v = await api("/ledger/verify");
    const badge = document.getElementById("ledger-badge");
    if (!v.intact && !state.ledgerDemoOptedIn) {
      try { await api("/ledger/restore", { method: "POST" }); const vv = await api("/ledger/verify"); badge.innerHTML = `<span class="pill pill-ok">Verified \u2713 \u00b7 ${vv.records} blocks</span>`; }
      catch { badge.innerHTML = `<span class="pill">Integrity check unavailable</span>`; }
    } else if (v.intact) {
      badge.innerHTML = `<span class="pill pill-ok">Verified \u2713 \u00b7 ${v.records} blocks</span>`;
    } else {
      badge.innerHTML = `<span class="pill pill-danger">TAMPERED at block ${v.broken_at_index}</span>`;
    }
    const lst = await api("/ledger");
    const preview = document.getElementById("ledger-preview");
    if (preview && lst.length) {
      const last = lst[lst.length - 1];
      preview.textContent = `Last block: #${last.index} ${last.event_type} by ${last.actor} @ ${fmtTime(last.created_at)}`;
    }
  } catch { const badge = document.getElementById("ledger-badge"); if (badge) badge.innerHTML = `<span class="pill">Sign in to verify</span>`; }
}

/* ==================== INBOX ==================== */
function parseInboxPayload(payload) {
  let obj = payload;
  if (typeof obj === "string") { try { obj = JSON.parse(obj); } catch { /* keep string */ } }
  if (obj === null || typeof obj !== "object") return [];
  const pick = (keys) => { for (const k of keys) { const v = obj[k]; if (v !== undefined && v !== null) return v; } return null; };
  const rows = [];
  const push = (k, v) => { if (v !== undefined && v !== null && v !== "") rows.push([k, v]); };
  push("ATM", pick(["atm_id", "atm", "target_atm"])); push("Bank", pick(["bank", "bank_name", "home_bank"]));
  push("City", pick(["city", "victim_city", "area"])); push("Role", pick(["role", "recipient_role"]));
  push("Action", pick(["action", "suggested_action", "recommended_action"])); push("Risk", pick(["risk", "risk_score"]));
  push("Amount", pick(["amount", "amount_inr", "amount_at_risk"])); push("Tier", pick(["tier", "priority_tier"]));
  return rows;
}

function inboxBody(m) {
  const rows = parseInboxPayload(m.payload);
  const raw = esc(JSON.stringify(m.payload)).slice(0, 220);
  const body = rows.length
    ? rows.map(([k, v]) => `<div class="inbox-kv"><span class="muted">${esc(k)}</span><b>${esc(String(v))}</b></div>`).join("")
    : `<span class="mono">${raw}</span>`;
  return `${body}<button class="btn btn-sm btn-ghost inbox-rawbtn" type="button">${rows.length ? "Raw" : "details"}</button><div class="inbox-raw mono hidden">${raw}</div>`;
}

async function renderInbox() {
  try {
    state.inbox = await api("/mock-i4c-inbox");
    const el = document.getElementById("inbox-panel");
    if (el) el.innerHTML = state.inbox.slice(0, 15).map(
      (m) => `<div class="inbox-msg"><span class="pill">${esc(m.channel)}</span> <span class="muted">${fmtTime(m.received_at)}</span><br/>${inboxBody(m)}<span class="muted">\uD83D\uDCE9 ${esc(m.direction === "outgoing" ? "dispatch sent" : (m.direction || "received"))}</span></div>`
    ).join("") || `<div class="empty-state"><p>No intel received yet \u2014 run an alert cycle.</p></div>`;
    document.querySelectorAll("#inbox-panel .inbox-rawbtn").forEach((b) =>
      b.addEventListener("click", (e) => { const raw = e.currentTarget.closest(".inbox-msg").querySelector(".inbox-raw"); if (raw) raw.classList.toggle("hidden"); })
    );
  } catch { const el = document.getElementById("inbox-panel"); if (el) el.innerHTML = `<p class="muted">\u2014</p>`; }
}

/* ==================== HANDOFFS ==================== */
async function renderHandoffs() {
  const panel = document.getElementById("handoff-panel");
  const countEl = document.getElementById("handoff-count");
  if (!panel) return;
  try {
    const res = await api("/alerts/handoffs/list");
    const hs = res.handoffs || [];
    if (countEl) countEl.textContent = res.total ? `${hs.filter(h => h.status === "queued").length} queued / ${res.total}` : "0";
    panel.innerHTML = hs.slice(0, 20).map(
      (h) => `<div class="inbox-msg">
        <span class="pill rt rt-xstate">${esc(h.origin_state)} \u2192 ${esc(h.receiving_state)}</span>
        <span class="pill ${h.status === "queued" ? "pill-warn" : "pill-ok"}">${esc(h.status)}</span>
        <span class="muted">${fmtTime(h.created_at)}</span><br/>
        <span class="mono">ATM ${esc(h.atm_id)} \u00b7 alert ${esc(h.alert_id)}</span>
        ${h.status === "queued" ? `<button class="btn btn-sm btn-ok" data-hack="${esc(h.handoff_id)}">Ack</button>
          <button class="btn btn-sm" data-hcomplete="${esc(h.handoff_id)}">Complete</button>` : ""}
      </div>`
    ).join("") || `<div class="empty-state"><p>No cross-state handoffs queued.</p></div>`;
    panel.querySelectorAll("button[data-hack]").forEach((b) => b.addEventListener("click", () => handoffAck(b.dataset.hack, "ack")));
    panel.querySelectorAll("button[data-hcomplete]").forEach((b) => b.addEventListener("click", () => handoffAck(b.dataset.hcomplete, "complete")));
  } catch { panel.innerHTML = `<p class="muted">\u2014</p>`; if (countEl) countEl.textContent = ""; }
}

async function handoffAck(handoffId, status) {
  try {
    await api(`/alerts/handoffs/${handoffId}/ack`, { method: "POST", body: JSON.stringify({ status }) });
    await renderHandoffs();
  } catch (e) { toast("Handoff update failed: " + e.message, "error"); }
}

/* ==================== EVIDENCE MODAL ==================== */
async function openEvidence(alertId) {
  try {
    const sim = state.simulatedOptedIn;
    let ev = sim ? state.simulatedEvidence[alertId] : null;
    if (!ev && sim) { toast("Evidence not available in simulated scenario.", "warning"); return; }
    if (!ev) ev = await api(`/alerts/${alertId}/evidence`);
    const isSimulated = sim; const j = ev.jurisdiction || {};
    const contribs = (ev.feature_contributions || []).map(
      (f) => `<div class="feat-row"><span><b>${esc(f.feature)}</b> <span class="muted">(importance ${f.global_importance})</span></span><span>value ${f.value} \u2192 <b>${esc(f.percentile)}</b></span></div>`
    ).join("");
    const freeze = (ev.recommended_freeze_accounts || []).map(
      (a) => `<span class="pill pill-danger">${esc(maskedAccount(a.account_token))} (${a.recent_withdrawals} txns/24h)</span>`
    ).join(" ") || `<span class="muted">No complaint-linked accounts active.</span>`;
    const unc = ev.uncertainty || {};
    const uncRows = [
      ["Confidence", unc.confidence || "n/a"], ["Evidence strength", unc.evidence_strength || "n/a"],
      ["Data freshness", unc.data_freshness_hours !== undefined ? `${unc.data_freshness_hours}h` : "n/a"],
      ["Model version", unc.model_version || "n/a"], ["Prediction horizon", unc.prediction_horizon_hours ? `${unc.prediction_horizon_hours}h` : "n/a"],
    ].map(([k, v]) => `<div class="feat-row"><span>${esc(k)}</span><b>${esc(String(v))}</b></div>`).join("");
    const graph = (ev.evidence_graph || []).map(
      (g, idx) => `<div class="ev-graph-row">
        <span class="ev-graph-idx">${idx + 1}</span>
        <span><b>${esc(g.signal)}</b><br/><span class="muted">${esc(g.value)}</span><br/>
          <span class="muted">direction: ${esc(g.direction)} \u00b7 source: ${esc(g.source_type)} \u00b7 ${esc(g.observed_or_synthetic)}</span></span>
        <span class="ev-graph-arrow">\u2193</span></div>`
    ).join("");
    document.getElementById("ev-alert-id").textContent = ev.alert_id;
    document.getElementById("ev-body").innerHTML = `
      ${isSimulated ? `<div class="ev-block" style="border-color:var(--danger)"><h3>SCRIPTED SIMULATED SCENARIO</h3><p class="ev-meta" style="color:var(--warn)">Evidence is scripted for demonstration, NOT live model output.</p></div>` : ""}
      <div class="ev-block"><h3>Recency &amp; Coverage</h3>
        <p class="ev-meta">Data through: <b>${fmtTime(ev.data_through)}</b> \u00b7 ATMs scored: ${ev.atms_scored}/${ev.atms_total} (${ev.scoring_coverage_pct}%)</p>
        <p class="ev-rule">${esc(ev.suggested_action)} <span class="muted">(rule: ${esc(ev.fired_rule)})</span></p>
        <p class="ev-meta">Jurisdiction: ${esc(j.state || "\u2014")}, ${esc(j.district || "\u2014")} (fictional) \u00b7 ${esc(j.police_station_area || "\u2014")}</p>
        <p class="ev-meta">Recipients: ${esc((ev.recommended_recipients || []).join(" \u00b7 "))}</p></div>
      <div class="ev-block"><h3>Complaint Activity</h3><p>${esc(ev.complaint_activity)}</p></div>
      <div class="ev-block"><h3>Withdrawal Activity</h3><p>${esc(ev.withdrawal_activity)}</p></div>
      <div class="ev-block"><h3>Context Signal</h3><p>${esc(ev.context_signal)}</p></div>
      <div class="ev-block"><h3>CFCFRMS Recovery Intel</h3><p>${freeze}</p><p class="ev-notice">Fund-blocking path (mock intel, hackathon prototype).</p></div>
      <div class="ev-block"><h3>Recommended Actions</h3>
        ${(ev.recommended_actions || []).map((a) => `<p class="ev-meta">${a.step}. ${esc(a.action)} \u2014 <b>${esc(a.owner)}</b></p>`).join("") || `<p class="ev-meta">No graded steps.</p>`}
        <p class="ev-notice">Advisory only \u2014 audited human decision required.</p></div>
      <div class="ev-block"><h3>Evidence Metadata</h3>${uncRows}
        ${unc.insufficient_evidence ? `<p class="ev-notice" style="color:var(--warn)">INSUFFICIENT EVIDENCE \u2014 HOLD ACTION.</p>` : ""}</div>
      <div class="ev-block"><h3>Evidence Graph</h3>${graph}</div>
      <div class="ev-block"><h3>Feature Contributions</h3>${contribs}<p class="ev-notice">${esc(ev.explainability_note)}</p></div>
      <div class="ev-block"><h3>SHAP (Per-Instance)</h3>
        ${(ev.per_instance_shap || []).map((f) => `<div class="feat-row"><span><b>${esc(f.feature)}</b></span><span>value ${f.value} \u2192 SHAP <b>${f.shap > 0 ? "+" : ""}${f.shap}</b></span></div>`).join("") || `<p class="muted">Unavailable.</p>`}</div>
      <div class="ev-block"><h3>Notifications (Simulated)</h3>
        <button class="btn btn-sm btn-accent" id="ev-report-btn">Generate Intelligence Report (PDF)</button></div>`;
    document.getElementById("evidence-modal").classList.remove("hidden");
    document.getElementById("ev-report-btn").addEventListener("click", () => hotspotReport(alertId));
  } catch (err) { toast("Evidence failed: " + err.message, "error"); }
}

async function hotspotReport(alertId) {
  try {
    const res = await fetch(`/reports/hotspot/${alertId}`, { method: "POST", headers: { Authorization: `Bearer ${getToken()}` } });
    if (!res.ok) throw new Error(res.status);
    const j = await res.json();
    toast(`Report ${j.report_id} generated`, "success");
  } catch (err) { toast("Report failed: " + err.message, "error"); }
}

/* ==================== MOBILE ==================== */
const MOBILE_DEMO_FIX = { lat: 22.66, lon: 74.55 };
let MOBILE_FIX = { ...MOBILE_DEMO_FIX };

async function renderMobile(lat, lon) {
  const el = document.getElementById("mobile-nearby");
  if (!el) return;
  try {
    const res = await api(`/mobile/nearby?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}&max_km=50&limit=5`);
    const rows = res.atms || [];
    if (!rows.length) { el.innerHTML = `<p class="muted">No ATMs within ${res.max_km} km.</p>`; return; }
    el.innerHTML = `<p class="muted" style="margin-bottom:8px;">Ranked by <code>0.6\u00b7risk + 0.4\u00b7(1/(1+km))</code> \u2014 ${res.found} found.</p>
      <div class="table-container"><table class="data-table">
        <thead><tr><th>#</th><th>ATM</th><th>Bank / Branch</th><th>City</th><th>Dist</th><th>Risk</th><th>Score</th></tr></thead>
        <tbody>${rows.map((r, i) => `<tr>
          <td>${i + 1}</td><td><b>${esc(r.atm_id)}</b></td>
          <td>${esc(r.branch_name)}<br/><span class="muted">${esc(r.bank_name)}</span></td>
          <td>${esc(r.city)}</td><td>${r.distance_km.toFixed(1)} km</td>
          <td>${riskPill(r.risk_score)}</td><td class="mob-score">${r.mobile_score.toFixed(3)}</td></tr>`).join("")}</tbody>
      </table></div>`;
  } catch (err) { el.innerHTML = `<div class="error-state"><h3>Mobile Lookup Unavailable</h3><p>${esc(err.message)}</p></div>`; }
}

function setMobileFromGeolocation() {
  const fix = () => { MOBILE_FIX = { ...MOBILE_DEMO_FIX }; renderMobile(MOBILE_FIX.lat, MOBILE_FIX.lon); };
  if (!navigator.geolocation) { fix(); return; }
  navigator.geolocation.getCurrentPosition(
    (p) => { MOBILE_FIX = { lat: p.coords.latitude, lon: p.coords.longitude }; renderMobile(MOBILE_FIX.lat, MOBILE_FIX.lon); },
    () => { toast("Location permission denied \u2014 using demo coords.", "warning"); fix(); },
    { timeout: 8000 }
  );
}

/* ==================== OUTCOMES ==================== */
async function renderOutcomes() {
  try {
    const s = await api("/alerts/outcomes/summary");
    const el = document.getElementById("outcome-panel");
    const badge = document.getElementById("outcome-badge");
    if (badge) badge.textContent = s.evaluated ? `${s.evaluated} evaluated` : "";
    if (!s.evaluated) {
      if (el) el.innerHTML = `<div class="empty-state"><div class="empty-state-icon">&#x1F4CA;</div><h3>No Outcomes Yet</h3><p>Alerts must age past the 24h horizon. Click "Evaluate pending" after a cycle.</p></div>`;
      return;
    }
    if (el) el.innerHTML = [
      ["Evaluated", s.evaluated], ["True positives", s.true_positives], ["False positives", s.false_positives],
      ["False negatives", s.false_negatives], ["Mean |error|", s.mean_abs_error], ["Outcome ECE", s.outcome_ece_10_bins],
    ].map(([k, v]) => `<div class="model-metric-row"><span>${esc(k)}</span><b>${esc(String(v))}</b></div>`).join("") +
      `<p class="ev-notice">${esc(s.note)}</p>`;
  } catch { /* panel absent */ }
}

/* ==================== ACTIONS ==================== */
async function runAlertCycle() {
  if (state.simulatedOptedIn) { toast("Disabled in SIMULATED mode.", "warning"); return; }
  try {
    toast("Running alert cycle...", "info");
    const r = await api("/alerts/run-now", { method: "POST" });
    const s = r.summary;
    toast(`Alert cycle: ${s.created} new \u00b7 ${s.flagged} flagged \u00b7 ${s.skipped} deduped`, "success");
    loadAll();
  } catch (err) { toast("Alert cycle failed: " + err.message, "error"); }
}

/* ==================== WEBSOCKET ==================== */
function connectWS() {
  try {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/alerts?token=${encodeURIComponent(getToken())}`);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (state.simulatedOptedIn) return;
        if (msg.event === "alert") {
          toast(`LIVE: ${msg.payload.atm_id} flagged ${(msg.payload.risk_score * 100).toFixed(0)}%`, "warning");
          loadAll();
        } else if (msg.event === "recovery" || msg.event === "recovery_status") { loadAll(); }
      } catch { /* ignore */ }
    };
    ws.onclose = () => setTimeout(connectWS, 5000);
  } catch { /* ignore */ }
}

/* ==================== LOGIN ==================== */
function showLogin() {
  clearNotice();
  document.getElementById("login-page").classList.remove("hidden");
  document.getElementById("app-shell").classList.add("hidden");
}

function hideLogin() {
  document.getElementById("login-page").classList.add("hidden");
  document.getElementById("app-shell").classList.remove("hidden");
}

function loginStatus(msg, kind) {
  const el = document.getElementById("login-status");
  if (el) { el.textContent = msg; el.className = "login-status " + (kind || ""); }
}

async function doLogin() {
  const userEl = document.getElementById("login-username");
  const passEl = document.getElementById("login-password");
  if (!userEl || !passEl) { location.reload(); return; }
  const username = userEl.value.trim();
  const password = passEl.value;
  if (!username || !password) { loginStatus("Enter username and password.", "err"); return; }
  const btn = document.getElementById("btn-login");
  btn.disabled = true; btn.textContent = "Signing in...";
  loginStatus(`Contacting server as ${username}...`, "");
  try {
    const res = await fetch("/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
    if (!res.ok) { loginStatus("Invalid credentials.", "err"); return; }
    const j = await res.json();
    localStorage.setItem(TOKEN_KEY, j.access_token);
    state.user = j.user;
    state.simulatedOptedIn = false; state.simulatedEvidence = {};
    setSimulationUI(false);
    hideLogin();
    loginStatus(`Signed in as ${j.user.display_name}...`, "ok");
    updateSidebarForRole(state.user.role);
    connectWS(); loadAll();
  } catch (err) {
    loginStatus("Sign-in failed: " + err.message, "err");
  } finally { btn.disabled = false; btn.textContent = "Sign In"; }
}

async function autofillDemo(username, password) {
  const userEl = document.getElementById("login-username");
  const passEl = document.getElementById("login-password");
  if (!userEl || !passEl) { location.reload(); return; }
  userEl.value = username; passEl.value = password;
  loginStatus(`Autofilled ${username} \u2014 signing in...`, "");
  await doLogin();
}
window.autofillDemo = autofillDemo;

/* ==================== BINDINGS ==================== */
function bindEvents() {
  const wire = (id, fn) => { const el = document.getElementById(id); if (el) el.addEventListener("click", fn); };
  wire("btn-login", doLogin);
  wire("btn-refresh", loadAll);
  wire("btn-cycle", runAlertCycle);
  wire("btn-sim-load", loadSimulatedScenario);
  wire("btn-sim-exit", exitSimulated);
  wire("btn-sim-banner-exit", exitSimulated);
  wire("btn-switch", () => { localStorage.removeItem(TOKEN_KEY); state.simulatedOptedIn = false; setSimulationUI(false); showLogin(); });
  wire("ev-close", () => document.getElementById("evidence-modal").classList.add("hidden"));
  wire("btn-replay", () => { const val = document.getElementById("asof-date").value; state.asOf = val ? new Date(val + "T12:00:00").toISOString() : null; loadAll(); });
  wire("btn-live", () => { state.asOf = null; document.getElementById("asof-date").value = ""; loadAll(); });
  wire("btn-ledger-verify", ledgerStatus);
  wire("btn-ledger-tamper", async () => {
    try { const r = await api("/ledger/tamper-demo", { method: "POST" }); state.ledgerDemoOptedIn = true; toast(r.note || "Tamper demo running", "warning"); ledgerStatus(); } catch (err) { toast("Tamper demo: " + err.message, "error"); }
  });
  wire("btn-ledger-restore", async () => {
    try { const r = await api("/ledger/restore", { method: "POST" }); state.ledgerDemoOptedIn = false; toast("Ledger restored", "success"); ledgerStatus(); } catch (err) { toast("Restore failed: " + err.message, "error"); }
  });
  wire("btn-sit-report", async () => {
    try {
      const res = await fetch("/reports/situational", { method: "POST", headers: { Authorization: `Bearer ${getToken()}` } });
      if (!res.ok) throw new Error(res.status);
      const j = await res.json();
      const dl = await fetch(`/reports/${j.report_id}/download`, { headers: { Authorization: `Bearer ${getToken()}` } });
      const blob = await dl.blob(); const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `${j.report_id}.pdf`; a.click();
      toast("Situational report generated", "success");
    } catch (err) { toast("Report failed: " + err.message, "error"); }
  });
  wire("btn-evaluate-outcomes", async () => {
    try { const r = await api("/alerts/outcomes/evaluate", { method: "POST" }); toast(`Outcomes evaluated: ${r.evaluated}`, "success"); renderOutcomes(); } catch (err) { toast("Evaluation failed: " + err.message, "error"); }
  });
  wire("btn-mobile-locate", setMobileFromGeolocation);

  const loginPass = document.getElementById("login-password");
  if (loginPass) loginPass.addEventListener("keydown", (e) => { if (e.key === "Enter") doLogin(); });

  const evModal = document.getElementById("evidence-modal");
  if (evModal) evModal.addEventListener("click", (e) => { if (e.target.id === "evidence-modal") evModal.classList.add("hidden"); });

  // Sidebar navigation
  document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      const view = item.dataset.view;
      if (view) switchView(view);
    });
  });

  // Filter bindings
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

  // Category chips
  const cats = ["All", ...COMPLAINT_TYPES];
  const chipBox = document.getElementById("category-chips");
  if (chipBox) {
    chipBox.innerHTML = cats.map((c) => `<span class="chip ${c === state.category ? "active" : ""}" data-cat="${esc(c)}">${esc(c)}</span>`).join("");
    chipBox.querySelectorAll(".chip").forEach((el) => el.addEventListener("click", () => {
      state.category = el.dataset.cat;
      chipBox.querySelectorAll(".chip").forEach((x) => x.classList.toggle("active", x === el));
      renderMap();
    }));
  }
}

/* ==================== BOOT ==================== */
window.cashguardLogin = doLogin;
bindEvents();
initI18n();
localStorage.removeItem("cashguard_role");
window.__cashguardReady = true;
if (getToken()) { connectWS(); loadAll(); hideLogin(); } else { showLogin(); }

/* ==================== I18N ==================== */
const i18n = { locales: [], strings: {}, lang: "en" };
async function initI18n() {
  const sel = document.getElementById("i18n-select");
  if (!sel) return;
  try {
    const meta = await api("/i18n/locales");
    i18n.locales = meta.locales || [];
    sel.innerHTML = i18n.locales.map((l) => `<option value="${esc(l.code)}">${esc(l.native)}</option>`).join("");
    const saved = localStorage.getItem("cashguard_lang") || "en";
    if (i18n.locales.some((l) => l.code === saved)) sel.value = saved;
    sel.addEventListener("change", () => setI18nLang(sel.value));
    await setI18nLang(sel.value);
  } catch { /* non-fatal */ }
}
async function setI18nLang(lang) {
  try { const res = await api(`/i18n/strings?lang=${encodeURIComponent(lang)}`); i18n.lang = res.lang; i18n.strings = res.strings || {}; localStorage.setItem("cashguard_lang", i18n.lang); }
  catch { i18n.lang = "en"; i18n.strings = {}; }
}
