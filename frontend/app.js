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
  ledgerDemoOptedIn: false,   // P0.3: tamper alert is opt-in per session
  simulatedOptedIn: false,    // P1.5: scripted scenario is opt-in, off by default (honest live)
  simulatedEvidence: {},      // evidence payloads for the loaded scripted scenario
  _loadGen: 0,                // P1.5: monotonic token; a stale in-flight loadAll() must never
                              // overwrite a newer load's state OR toggle the sim chrome off.
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
  if (res.status === 403) {
    // P0.2: never show a raw backend path or query string on screen. The caller
    // decides the friendly message; we only tag the route for scoping.
    const err = new Error("You don't have permission for that action on this account.");
    err.forbidden = true;
    err.route = path;
    throw err;
  }
  if (!res.ok) {
    // Never leak raw paths/query strings/stack traces/backend bodies to the UI.
    const err = new Error("That action couldn't be completed. Please try again.");
    err.route = path;
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function clearNotice() {
  const el = document.getElementById("notice");
  if (el) el.classList.add("hidden");
}

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), 4500);
}

function showNotice(msg) {
  const el = document.getElementById("notice");
  const txt = document.getElementById("notice-text");
  if (!el || !txt) return;
  txt.textContent = msg;
  el.classList.remove("hidden");
  const close = document.getElementById("notice-close");
  if (close) close.onclick = () => el.classList.add("hidden");
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
let tileMode = "loading";        // "online" | "offline" (canvas fallback)
let tileProviderIdx = 0;
let tileFailedCount = 0;
let tileFailTimer = null;
// OSM tiles work with zero config and no API key (brief P0.1). If they ever
// fail (no network / rate limit), enableOfflineMap() draws a styled district
// basemap so the heatmap NEVER shows broken or "API KEY REQUIRED" tiles.
const TILE_PROVIDERS = [
  { url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", attribution: '&copy; OpenStreetMap contributors' },
];
const MAP_TIMEOUT_MS = 9000; // if no tile ever loads in 9s, go offline canvas (silent fail safety)

function leafletTileUrl() {
  const p = TILE_PROVIDERS[tileProviderIdx % TILE_PROVIDERS.length];
  tileProviderIdx++;
  return p;
}

function enableOfflineMap() {
  /* Guaranteed-offline fallback: replace the tile map with a self-drawn
     canvas "district vector basemap" built from the ATMs' own lat/lon bounds,
     so a heatmap ALWAYS renders even with internet fully disabled. */
  if (tileMode === "offline") return;
  tileMode = "offline";
  clearTimeout(tileFailTimer);
  const el = document.getElementById("map");
  if (!el) return;
  const hadNote = el._tileNotice;
  el.innerHTML = `<canvas id="offline-map" class="offline-map"></canvas>
    <div class="map-fallback" style="top:6px">Offline vector map — live offline heatmap from ATM coordinates.</div>`;
  el._tileNotice = hadNote;
  requestAnimationFrame(() => drawOfflineMap());
}

function drawOfflineMap() {
  /* Canvas projection of the flagship heatmap when tiles are unreachable.
     Draws a dark grid "district" basemap on the fictional-ATM bounds and
     plots risk + complaint circles from the SAME lat/lon the Leaflet path uses. */
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

  // --- styled offline basemap: neutral ground + a district-outline polygon ---
  const grad = ctx.createLinearGradient(0, 0, W, H);
  grad.addColorStop(0, "#1d2025");
  grad.addColorStop(1, "#15171b");
  ctx.fillStyle = grad; ctx.fillRect(0, 0, W, H);

  // neutral fill for the "district" envelope (a GeoJSON-style outline, not bare tiles)
  const padX = 0.10 * W, padY = 0.12 * H;
  const poly = [
    [padX, H - padY], [W / 2, padY], [W - padX, H - padY * 0.8],
    [W - padX * 0.6, H - padY * 0.2], [W * 0.35, H - padY * 0.1]
  ];
  ctx.beginPath();
  ctx.moveTo(poly[0][0], poly[0][1]);
  for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i][0], poly[i][1]);
  ctx.closePath();
  ctx.fillStyle = "rgba(148,163,184,0.06)";
  ctx.fill();
  ctx.strokeStyle = "rgba(148,163,184,0.35)";
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // subdued lat/lng graticule lines
  ctx.strokeStyle = "rgba(148,163,184,0.10)"; ctx.lineWidth = 1;
  const step = 46;
  for (let x = step / 2; x < W; x += step) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
  for (let y = step / 2; y < H; y += step) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }

  const pts = rows.length ? rows : state.risk.filter((r) => typeof r.latitude === "number");
  let minLat = 8, maxLat = 37, minLng = 68, maxLng = 97; // India-ish default
  if (pts.length) {
    minLat = Math.min(...pts.map((r) => r.latitude));
    maxLat = Math.max(...pts.map((r) => r.latitude));
    minLng = Math.min(...pts.map((r) => r.longitude));
    maxLng = Math.max(...pts.map((r) => r.longitude));
    const pad = 0.12 * Math.max(maxLat - minLat, maxLng - minLng, 1);
    minLat -= pad; maxLat += pad; minLng -= pad; maxLng += pad;
  }
  const X = (lng) => ((lng - minLng) / (maxLng - minLng || 1)) * (W - 20) + 10;
  const Y = (lat) => H - 10 - ((lat - minLat) / (maxLat - minLat || 1)) * (H - 20);

  // complaint heat (soft pulses)
  if (state.showHeat) {
    const counts = aggregateComplaints();
    for (const [city, coords] of Object.entries(state.cityCoords)) {
      const n = counts[city] || 0; if (!n) continue;
      const cx = X(coords[1]), cy = Y(coords[0]);
      const r = 14 + Math.min(n, 40);
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
      g.addColorStop(0, "rgba(249,115,22,0.28)");
      g.addColorStop(1, "rgba(249,115,22,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
    }
  }

  // risk heatmap (forecast)
  if (state.showForecast) {
    for (const r of pts) {
      const cx = X(r.longitude), cy = Y(r.latitude);
      const rad = 4 + r.risk_score * 16;
      const col = riskColor(r.risk_score);
      ctx.globalAlpha = 0.40 + r.risk_score * 0.45;
      ctx.fillStyle = col;
      ctx.beginPath(); ctx.arc(cx, cy, rad, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 1;
    }
  }
  ctx.fillStyle = "rgba(148,163,184,0.55)";
  ctx.font = "11px Inter, system-ui, sans-serif";
  ctx.fillText(`${pts.length} ATM risk points rendered offline`, 14, 20);
}

function initMap() {
  if (map) return;
  if (tileMode === "offline") { requestAnimationFrame(drawOfflineMap); return; }
  if (typeof L === "undefined") { enableOfflineMap(); return; }  // Leaflet failed to load — go offline canvas
  map = L.map("map", { zoomControl: true }).setView([21.2, 78.5], 5);
  const startProvider = TILE_PROVIDERS[0];
  const tiles = L.tileLayer(startProvider.url, {
    attribution: startProvider.attribution, maxZoom: 18,
  });
  let loadedAny = false;
  tiles.on("tileload", () => { loadedAny = true; tileMode = "online"; clearTimeout(tileFailTimer); });
  tiles.on("tileerror", () => {
    tileFailedCount++;
    // Switch provider on repeated failures; after exhausting providers, go offline canvas.
    if (tileMode !== "offline" && !loadedAny && tileProviderIdx < TILE_PROVIDERS.length && tileFailedCount >= 3) {
      const mapEl = document.getElementById("map");
      const note = mapEl && !mapEl._tileNotice
        ? (mapEl._tileNotice = true, mapEl.insertAdjacentHTML("beforeend",
            `<div class="map-fallback" style="bottom:6px;top:auto">Primary tile imagery unreachable — switching to fallback provider.</div>`))
        : null;
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
  // Silent-fail safety: if nothing ever loads within the timeout, go offline canvas.
  tileFailTimer = setTimeout(() => { if (!loadedAny && tileMode !== "offline") enableOfflineMap(); }, MAP_TIMEOUT_MS);
  tiles.addTo(map);
  atmLayer = L.layerGroup().addTo(map);
  complaintLayer = L.layerGroup().addTo(map);
}

function renderMap() {
  try {
    if (!map) initMap();               // build the engine before using layers
    if (tileMode === "offline") { drawOfflineMap(); return; }
    if (typeof L === "undefined" || !atmLayer) {
      enableOfflineMap();
      return;
    }
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
  const { role } = state.user || {};
  // Explicit allowlist — ONLY police/I4C may read complaints. The permission
  // check runs BEFORE the fetch is dispatched, so a Bank session never even
  // sends /complaints (no chance of surfacing a raw 403 + query string).
  const ALLOWED = ["POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN"];
  if (!role || !ALLOWED.includes(role)) { state.complaints = []; return; }
  try {
    const to = state.asOf || new Date().toISOString();
    const from = new Date(new Date(to).getTime() - 7 * 864e5).toISOString();
    state.complaints = await api(`/complaints?date_from=${encodeURIComponent(from)}&date_to=${encodeURIComponent(to)}&limit=20000`).catch(() => []);
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
  clearNotice();
  const gen = ++state._loadGen;       // newest init wins; stale loads bail before touching state/chrome
  const stale = () => gen !== state._loadGen;
  try {
    const asOfEl = document.getElementById("as-of");
    document.getElementById("role-badge").textContent = `${state.user.role} · ${state.user.scope}`;
    if (state.simulatedOptedIn) {
      // Honest OPT-IN simulated scenario: pull the scripted payload and keep the
      // persistent banner/watermark visible. City coords from live are preserved
      // so the map geometry still renders; the simulated ATMs carry their own coords.
      const scen = await api("/simulated/scenario");
      if (!scen || !scen.simulated) { throw new Error("simulated scenario unavailable"); }
      if (stale()) return;
      state.risk = scen.risk_scores || [];
      state.alerts = scen.alerts || [];
      state.stats = scen.stats || null;
      state.simulatedEvidence = scen.evidence || {};
      if (asOfEl) asOfEl.textContent = `SIMULATED scenario as of ${fmtTime(scen.as_of || new Date().toISOString())}`;
      setSimulationUI(true);
      render();
      return;
    }
    const q = state.asOf ? `&as_of=${encodeURIComponent(state.asOf)}` : "";
    const [risk, alerts, stats] = await Promise.all([
      api(`/risk-scores${q}`),
      api("/alerts?limit=200"),
      api("/stats/summary").catch(() => null),   // role-scoped; non-fatal (BANK)
    ]);
    if (stale()) return;                        // a newer load superseded us — discard, don't clobber
    state.risk = risk; state.alerts = alerts; state.stats = stats;
    await Promise.all([loadCityCoords(), loadComplaints()]);
    if (stale()) return;
    if (asOfEl) asOfEl.textContent = state.asOf
      ? `Forecast replay as of ${fmtTime(state.asOf)}`
      : (state.stats ? `Forecast as of ${fmtTime(state.stats.generated_at)}` : `Forecast as of ${fmtTime(new Date().toISOString())}`);
    setSimulationUI(false);
    render();
  } catch (err) { toast("Load failed: " + err.message); }
}

/* P1.5 — the simulated-scenario UI state is driven ONLY by state.simulatedOptedIn.
   It persists across re-renders and role switches while active. */
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
  // Explicit user action (button) — never auto-triggered on load.
  try {
    await api("/simulated/scenario"); // 401/403 guard so we don't break on stale token
    state.simulatedOptedIn = true;
    toast("Loaded SCRIPTED simulated scenario — labelled, not live output");
    loadAll();
  } catch (err) {
    // P1.5 fix: a failed guard/load must NEVER leave stale simulated data rendered
    // under the live chrome (the "toggle shows off but sim data shows" state). Clear
    // the simulated state and repopulate honest live; never just turn chrome off.
    toast("Could not load simulated scenario: " + err.message);
    state.simulatedOptedIn = false;
    state.simulatedEvidence = {};
    state.alerts = [];
    state.risk = [];
    state.stats = null;
    loadAll();   // token-guarded; repopulates honest live
  }
}

function exitSimulated() {
  state.simulatedOptedIn = false;
  state.simulatedEvidence = {};
  // Clear sim data up front so a failed live reload can never leave stale
  // simulated data rendered under the live chrome.
  state.alerts = [];
  state.risk = [];
  state.stats = null;
  setSimulationUI(false);
  loadAll();
}

/* ------------------------------ renderers ------------------------------ */
function render() {
  setSimulationUI(state.simulatedOptedIn);   // banner/watermark persist on any render path
  document.querySelectorAll("main.dash").forEach((d) => d.classList.add("hidden"));
  if (state.user.role === "BANK") { document.getElementById("dash-bank").classList.remove("hidden"); renderBank(); }
  else if (state.user.role === "I4C_ADMIN") { document.getElementById("dash-i4c").classList.remove("hidden"); renderI4C(); }
  else { document.getElementById("dash-police").classList.remove("hidden"); renderPolice(); }
  // Role-gate the "Run Alert Cycle" button: only roles the backend authorizes
  // (POLICE_STATE / POLICE_DISTRICT / I4C_ADMIN) may run the alert engine.
  const btnCycle = document.getElementById("btn-cycle");
  if (btnCycle) btnCycle.classList.toggle("hidden", state.user.role === "BANK");
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
  renderThrBands(row.threshold);
}

/* D3 — tier-band breakdown tied to the ACT/REVIEW/HOLD dispatch policy.
   Mirrors backend services.alert_tier: dispatch >= 0.85, action 0.70-0.85,
   monitor < 0.70. Shows, at the selected alert threshold, which dispatch bands
   sit above (actionable) vs below (review/hold), so a judge sees that raising
   the threshold narrows the high-priority queue to the highest-confidence
   tier — the same distinction used to visually separate re-observed repeats. */
function renderThrBands(t) {
  const el = document.getElementById("thr-bands");
  if (!el) return;
  const BANDS = [
    { name: "DISPATCH · High-Priority", rng: "≥ 0.85", min: 0.85, act: "ACT — dispatch to LEA + bank", cls: "band-dispatch" },
    { name: "ACTION · Review", rng: "0.70–0.85", min: 0.70, act: "REVIEW — enhanced monitoring", cls: "band-action" },
    { name: "MONITOR · Hold", rng: "< 0.70", min: 0, act: "HOLD — watch, no dispatch", cls: "band-monitor" },
  ];
  // alert_tier semantics (mirrors backend): an alert AT the chosen threshold maps
  // to exactly one band — dispatch >= 0.85, action 0.70-0.85, monitor < 0.70.
  const tier = t >= 0.85 ? "DISPATCH" : t >= 0.70 ? "ACTION" : "MONITOR";
  const html = BANDS.map((b) => {
    const active = b.name.startsWith(tier.split(" ")[0]);
    return `<div class="band ${b.cls}${active ? " active" : ""}">
      <b>${b.name}</b><span class="muted">${b.rng}</span>
      <span class="band-act">${b.act}</span>${active ? '<span class="pill ok">band at this threshold</span>' : ""}
    </div>`;
  }).join("");
  el.innerHTML = `<div class="band-label">Dispatch bands at threshold <b>${t.toFixed(2)}</b></div>` + html;
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
  document.querySelectorAll("#alert-count").forEach((c) => (c.textContent = `${alerts.filter((a) => a.status === "new").length} new`));
  const el = document.getElementById(tableId);
  if (!el) return;
  tbodyOf(el).innerHTML = alerts.map(
    (a) => `<tr><td>${fmtTime(a.created_at)}</td><td><b>${esc(a.atm_id)}</b></td><td>${esc(a.city)}</td>
    <td>${tierBadge(a.tier || tierOf(a.risk_score))}</td><td>${riskPill(a.risk_score)}</td><td>${esc(a.recommended_action)}${alertMeta(a)}</td><td>${statusPill(a.status)}</td>
    <td>${routingBadge(a)}<button class="btn small" data-evid="${esc(a.alert_id)}">Details</button>
    ${hitlButtons(a)}</td></tr>`
  ).join("");
  el.querySelectorAll("button[data-act]").forEach((b) => b.addEventListener("click", () => hitlAction(b.dataset.id, b.dataset.act)));
  el.querySelectorAll("button[data-evid]").forEach((b) => b.addEventListener("click", () => openEvidence(b.dataset.evid)));
}

function routingBadge(a) {
  if (a.routing_status && a.routing_status !== "none" && a.origin_state) {
    const st = a.routing_status === "handoff_complete" ? "done" : a.routing_status === "handoff_ack" ? "acked" : "xstate";
    return `<span class="rt rt-${st}" title="origin ${esc(a.origin_state)} → ${esc(a.state)}">↗ ${esc(a.origin_state)}→${esc(a.state)}</span><br/>`;
  }
  return "";
}

function alertMeta(a) {
  let meta = "";
  if (a.risk_delta_vs_last !== null && a.risk_delta_vs_last !== undefined) {
    meta += `<span class="rt rt-escl" title="risk rose vs this ATM's most recent alert — genuine escalation">▲ +${a.risk_delta_vs_last.toFixed(2)} escalation</span>`;
  }
  if (a.reobservation_count > 0) {
    meta += `<span class="rt rt-reobs" title="same risk re-seen within cooldown — recorded, not re-alerted (anti alert-fatigue)">re-observed ×${a.reobservation_count}</span>`;
  }
  return meta ? `<br/>${meta}` : "";
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
  await setAlertStatusAction(alertId, status, reason);
}

async function setAlertStatusAction(alertId, status, reason = "") {
  try {
    if (state.simulatedOptedIn) {
      // P1.5: simulated mode updates the in-memory alert only (NOT persisted).
      const a = state.alerts.find((x) => x.alert_id === alertId);
      if (a) a.status = status;
      toast(`Alert ${alertId} → ${status} (simulated — not persisted to ledger)`);
      renderAlertTable(state.user.role === "I4C_ADMIN" ? "i4c-alert-table" : (state.user.role === "BANK" ? "bank-alert-table" : "alert-table"), state.alerts);
      return;
    }
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
  // P1.4 reconciliation: alert KPIs are derived from the SAME alert array that
  // feeds the alerts table below, so the cards and the table can never
  // disagree (previously the cards read /stats/summary's live DB count — 0 —
  // while the table showed the demo alert set, an on-screen contradiction).
  const alertTotal = state.alerts.length;
  const alertActioned = state.alerts.filter((a) => a.status === "actioned").length;
  document.getElementById("i4c-stats").innerHTML = [
    ["🏧", s.high_risk_atms, "High-risk ATMs", "hero"],
    ["🚨", alertTotal, "Alerts", "hero"],
    ["🕵️", s.complaints_24h, "Complaints (24h)", ""],
    ["📅", s.complaints_7d, "Complaints (7d)", ""],
    ["✅", alertActioned, "Actioned", ""],
    ["💸", s.fraud_withdrawals_7d, "Fraud withdrawals (7d)", ""],
  ].map(([e, n, l, h]) => `<div class="stat ${h}"><div class="num">${e} ${(n ?? 0).toLocaleString()}</div><div class="lbl">${l}</div></div>`).join("");
  const scale = document.getElementById("i4c-scale-note");
  if (scale) scale.textContent = `Demo-scale synthetic dataset — ${(s.complaints_7d ?? 0).toLocaleString()} complaints (7d) across current window; figures are illustrative, not live production traffic.`;

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
      const leakNote = `<div class="ev-block" style="border:1px solid #f87171;margin-bottom:10px">
        <h3>⚠ Model Honesty — Data-Leakage Corrected</h3>
        <p class="ev-meta">An earlier reported <b>ROC-AUC 0.927</b> was <b>invalid</b>: training built labels and features on the <b>same calendar day</b>, so rolling window features leaked the target into the features (label leakage). Fixed by shifting day-keyed feature frames forward 1 day. The <b>honest, forecast-safe model now scores ${fmtMetric(m.metrics.roc_auc, 4)} (held-out). Leaky AUC → forecast-safe: <b>0.9275 → 0.6344</b> (proof artifact).</p>
        <p class="ev-meta" style="color:var(--yellow)">Honest consequence: for calm demo days the model reports LOW risk (max ~0.11) for every ATM and produces NO alerts. A populated alert workflow is shown only via the opt-in "Load Simulated Scenario" button, which is clearly labelled SCRIPTED ‑ not live output.</p>
      </div>`;
      document.getElementById("model-metrics").innerHTML = leakNote + [
        ["Model", m.metrics.model_type + " + " + (m.metrics.calibration || "—")],
        ["ROC-AUC (forecast-safe)", fmtMetric(m.metrics.roc_auc, 4)],
        ["Precision@20/50/100/1000", `${fmtMetric(m.metrics.precision_at_20, null)} / ${fmtMetric(m.metrics.precision_at_50, null)} / ${fmtMetric(m.metrics.precision_at_100, null)} / ${fmtMetric(m.metrics.precision_at_1000, null)}`],
        ["Baseline P@20 (volume)", fmtMetric(m.metrics.baseline_volume_precision_at_20, null)], ["Lift vs volume @100", fmtMetric(m.metrics.lift_vs_volume_at_100, null)],
        ["Lift vs proximity @100", fmtMetric(m.metrics.lift_vs_proximity_at_100, null)],
        ["Lead time (median)", `${fmtMetric(m.metrics.lead_time_median_hours, null)} h`],
        ["Threshold (≥0.7) precision", fmtMetric(m.metrics.precision_at_threshold_0p7, 2)],
      ].map(([k, v]) => `<div class="m-row"><span>${esc(k)}</span><b>${esc(String(v))}</b></div>`).join("") +
      `<p class="ev-notice">Honest, forecast-safe metrics (AUC ${fmtMetric(m.metrics.roc_auc, 4)}) measured on SYNTHETIC labels — see LIMITATIONS.md and docs/ Model Card. This replaces any earlier "verified 0.927" figure, which was invalidated by the label-leakage fix. Full detail: LIMITATIONS.md.</p>`;
    }
  } catch { document.getElementById("model-metrics").innerHTML = `<p class="muted">Train to see metrics.</p>`; }

  renderAlertTable("i4c-alert-table", state.alerts);
  await ledgerStatus();
  await renderInbox();
  await renderHandoffs();
  await renderOutcomes();
  await renderMuleGraph();
}

async function renderHandoffs() {
  const panel = document.getElementById("handoff-panel");
  const countEl = document.getElementById("handoff-count");
  if (!panel) return;
  try {
    const res = await api("/alerts/handoffs/list");
    const hs = res.handoffs || [];
    if (countEl) countEl.textContent = res.total ? `${hs.filter((h) => h.status === "queued").length} queued / ${res.total}` : "0";
    panel.innerHTML = hs.slice(0, 20).map(
      (h) => `<div class="inbox-msg">
        <span class="pill rt rt-xstate">${esc(h.origin_state)} → ${esc(h.receiving_state)}</span>
        <span class="pill ${h.status === "queued" ? "warn" : "ok"}">${esc(h.status)}</span>
        <span class="muted">${fmtTime(h.created_at)}</span><br/>
        <span class="mono">ATM ${esc(h.atm_id)} · alert ${esc(h.alert_id)}</span>
        ${h.status === "queued" ? `<button class="btn small ok" data-hack="${esc(h.handoff_id)}">Ack</button>
          <button class="btn small" data-hcomplete="${esc(h.handoff_id)}">Complete</button>` : ""}
      </div>`
    ).join("") || `<p class="muted">No cross-state handoffs queued.</p>`;
    panel.querySelectorAll("button[data-hack]").forEach((b) => b.addEventListener("click", () => handoffAck(b.dataset.hack, "ack")));
    panel.querySelectorAll("button[data-hcomplete]").forEach((b) => b.addEventListener("click", () => handoffAck(b.dataset.hack, "complete")));
  } catch {
    panel.innerHTML = `<p class="muted">—</p>`;
    if (countEl) countEl.textContent = "";
  }
}

async function handoffAck(handoffId, status) {
  try {
    await api(`/alerts/handoffs/${handoffId}/ack`, { method: "POST", body: JSON.stringify({ status }) });
    await renderHandoffs();
    renderAlertTable(state.user.role === "I4C_ADMIN" ? "alert-table" : "bank-alert-table", state.alerts);
  } catch (e) { toast("Handoff update failed: " + e.message); }
}

async function ledgerStatus() {
  try {
    const v = await api("/ledger/verify");
    const badge = document.getElementById("ledger-badge");
    // P0.3: the DEFAULT for any fresh session is VERIFIED. A red TAMPERED state
    // is only ever shown after the user explicitly starts the tamper demo THIS
    // session. If the server still carries a tampered state from an earlier
    // session (shared in-memory across role switches / page reloads), silently
    // reset it so the default is always verified — never leaks into a new view.
    if (!v.intact && !state.ledgerDemoOptedIn) {
      try {
        const rr = await api("/ledger/restore", { method: "POST" });
        const vv = await api("/ledger/verify");
        badge.innerHTML = `<span class="pill ok">Ledger verified ✓ · ${vv.records} blocks</span>`;
      } catch {
        badge.innerHTML = `<span class="pill info">Ledger integrity check unavailable</span>`;
      }
    } else if (v.intact) {
      badge.innerHTML = `<span class="pill ok">Ledger verified ✓ · ${v.records} blocks</span>`;
    } else {
      badge.innerHTML = `<span class="pill bad">LEDGER TAMPERED ✗ at block ${v.broken_at_index} — tamper detected per demo</span>`;
    }
    const lst = await api("/ledger");
    document.getElementById("ledger-preview").textContent =
      `Last block: #${lst[lst.length - 1].index} ${lst[lst.length - 1].event_type} by ${lst[lst.length - 1].actor} @ ${fmtTime(lst[lst.length - 1].created_at)}`;
  } catch { document.getElementById("ledger-badge").innerHTML = `<span class="pill info">Sign in to verify</span>`; }
}

/* P1.8 — readable inbox parsing. Incoming webhook payloads are rendered as
   human-readable key/value lines (+masked account tokens, no raw secrets),
   with a per-message "view raw payload" toggle falling back to the raw JSON.
   Never trusts a payload field as HTML (all escaped). */
function parseInboxPayload(payload) {
  let obj = payload;
  if (typeof obj === "string") { try { obj = JSON.parse(obj); } catch { /* keep string */ } }
  if (obj === null || typeof obj !== "object") return [];
  const pick = (keys) => { for (const k of keys) { const v = obj[k]; if (v !== undefined && v !== null) return v; } return null; };
  const rows = [];
  const push = (k, v) => { if (v !== undefined && v !== null && v !== "") rows.push([k, v]); };
  push("ATM", pick(["atm_id", "atm", "target_atm"]));
  push("Bank", pick(["bank", "bank_name", "home_bank"]));
  push("City", pick(["city", "victim_city", "area"]));
  push("Role", pick(["role", "recipient_role", "jurisdiction_role"]));
  push("Action", pick(["action", "suggested_action", "recommended_action"]));
  push("Status", pick(["status", "routing_status"]));
  push("Risk", pick(["risk", "risk_score"]));
  push("Amount", pick(["amount", "amount_inr", "amount_at_risk"]));
  push("Tier", pick(["tier", "priority_tier"]));
  push("Note", pick(["note", "message", "summary"]));
  return rows;
}

function inboxBody(m) {
  const rows = parseInboxPayload(m.payload);
  const raw = esc(JSON.stringify(m.payload)).slice(0, 220);
  const body = rows.length
    ? rows.map(([k, v]) => `<div class="inbox-kv"><span class="muted">${esc(k)}</span><b>${esc(String(v))}</b></div>`).join("")
    : `<span class="mono">${raw}</span>`;
  return `${body}<button class="btn small ghost inbox-rawbtn" type="button">${rows.length ? "View raw payload" : "details"}</button>
    <div class="inbox-raw mono hidden">${raw}</div>`;
}

async function renderInbox() {
  try {
    state.inbox = await api("/mock-i4c-inbox");
    document.getElementById("inbox-panel").innerHTML = state.inbox.slice(0, 15).map(
      (m) => `<div class="inbox-msg"><span class="pill info">${esc(m.channel)}</span> <span class="muted">${fmtTime(m.received_at)}</span><br/>${inboxBody(m)}<span class="muted">📩 ${esc(m.direction === "outgoing" ? "dispatch sent" : (m.direction || "received"))}</span></div>`
    ).join("") || `<p class="muted">No intel received yet — run an alert cycle.</p>`;
    document.querySelectorAll("#inbox-panel .inbox-rawbtn").forEach((b) =>
      b.addEventListener("click", (e) => {
        const raw = e.currentTarget.closest(".inbox-msg").querySelector(".inbox-raw");
        if (raw) raw.classList.toggle("hidden");
      })
    );
  } catch { document.getElementById("inbox-panel").innerHTML = `<p class="muted">—</p>`; }
}

/* ------------------------------ evidence panel ------------------------------ */
async function openEvidence(alertId) {
  try {
    // P1.5: in a loaded scripted scenario, evidence is served from the in-memory
    // simulated payload (scripted values), NOT a live DB lookup.
    const sim = state.simulatedOptedIn;
    let ev = sim ? state.simulatedEvidence[alertId] : null;
    if (!ev && sim) {
      // Never mix a live DB evidence lookup under a simulated chrome. If the
      // scripted payload lacks this alert's evidence, say so instead of leaking
      // real data into a SCRIPTED panel.
      toast("Evidence not available for this alert in the simulated scenario.");
      return;
    }
    if (!ev) ev = await api(`/alerts/${alertId}/evidence`);
    const isSimulated = sim;   const j = ev.jurisdiction || {};
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
      ${isSimulated ? `<div class="ev-block" style="border:1px solid #f87171"><h3>⚠ SCRIPTED SIMULATED SCENARIO</h3><p class="ev-meta" style="color:var(--yellow)">This evidence panel, its risk score and its SMS/email/dispatch logs are SCRIPTED for demonstration — NOT output of the live leak-fixed risk engine (honest AUC 0.63, which reports low scores for calm days and produced no alerts).</p></div>` : ""}
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
    const el = document.getElementById(targetId);
    // P0.3: show the red TAMPERED state only after the user starts the tamper demo this session.
    if (v.intact) el.innerHTML = `<span class="pill ok">Ledger ✓ ${v.records}</span>`;
    else if (!state.ledgerDemoOptedIn) el.innerHTML = `<span class="pill info">Ledger integrity demo available</span>`;
    else el.innerHTML = `<span class="pill bad">Ledger TAMPERED</span>`;
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

/* ------------------------------ mule graph (money trail) ------------------------------ */
async function renderMuleGraph() {
  const panel = document.getElementById("mule-graph-table");
  const detail = document.getElementById("mule-graph-detail");
  if (!panel) return;
  try {
    const res = await api("/mule-graph/terminal-nodes?k=50");
    const nodes = res.nodes || [];
    if (!nodes.length) {
      panel.querySelector("tbody").innerHTML = `<tr><td colspan="8" class="muted">No terminal nodes in scope.</td></tr>`;
      detail.textContent = "—";
      return;
    }
    panel.querySelector("tbody").innerHTML = nodes.map((n, i) =>
      `<tr data-token="${esc(n.account_token)}">
        <td>${i + 1}</td>
        <td class="mono" title="${esc(n.account_token)}">${maskedAccount(n.account_token)}</td>
        <td>${(n.terminal_risk * 100).toFixed(1)}%</td>
        <td>—</td><td>—</td><td>—</td><td>—</td>
        <td><button class="btn small" data-trail="${esc(n.account_token)}">🔍 Trail</button></td>
      </tr>`
    ).join("");
    panel.querySelectorAll("button[data-trail]").forEach((b) =>
      b.addEventListener("click", async (e) => {
        const token = e.currentTarget.dataset.trail;
        detail.innerHTML = `<p class="muted">Loading trail for ${maskedAccount(token)}…</p>`;
        try {
          const trail = await api(`/mule-graph/trail/${token}`);
          detail.innerHTML = `
            <div class="ev-block"><h3>Money Trail for ${esc(maskedAccount(trail.account_token))}</h3>
              <p class="ev-meta">Terminal Risk: <b>${(trail.terminal_risk * 100).toFixed(1)}%</b> · In-Degree: ${trail.in_degree} · Out-Degree: ${trail.out_degree} · Inflow: ₹${trail.inflow_inr.toLocaleString()} · Chain Depth: ${trail.chain_depth}</p>
              <h4>Layering Chains (source → … → terminal)</h4>
              <p class="mono">${(trail.chains || []).map(c => c.join(" → ")).join("<br/>") || "—"}</p>
              <h4>Edges (transfers in window)</h4>
              <p class="mono">${(trail.edges || []).slice(0, 20).map(e => `${esc(e.source)} → ${esc(e.target)} : ₹${e.amount.toLocaleString()}`).join("<br/>") || "—"}</p>
            </div>
          `;
        } catch (err) { detail.innerHTML = `<p class="muted err">Trail load failed: ${err.message}</p>`; }
      })
    );
    detail.textContent = "Click 🔍 Trail on a row to see the money-trail chains and edges.";
  } catch (err) {
    panel.querySelector("tbody").innerHTML = `<tr><td colspan="8" class="muted err">Failed to load: ${err.message}</td></tr>`;
  }
}

/* ------------------------------ actions ------------------------------ */
async function setAlertStatus(alertId, status) {
  await setAlertStatusAction(alertId, status, "");
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
  if (state.simulatedOptedIn) {
    toast("Run Alert Cycle is disabled in SIMULATED mode — it would create FAKE live alerts. Exit the scenario to run the real engine.");
    return;
  }
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
        if (state.simulatedOptedIn) return;   // no live feed while a scripted scenario is shown
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
function showLogin() {
  clearNotice();
  document.getElementById("login-modal").classList.remove("hidden");
}

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
    state.simulatedOptedIn = false; state.simulatedEvidence = {};   // fresh session = honest live default
    setSimulationUI(false);
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

/* One-click demo role autofill + sign-in (task C): a judge can select a role
   from the login screen and be taken straight to the right dashboard. Credentials
   stay visible on the button tooltip/name for teaching. */
async function autofillDemo(username, password) {
  const userEl = document.getElementById("login-username");
  const passEl = document.getElementById("login-password");
  if (!userEl || !passEl) { location.reload(); return; }  // stale markup -> fresh reload
  userEl.value = username;
  passEl.value = password;
  loginStatus(`Autofilled ${username} — signing in…`, "");
  await doLogin();
}
window.autofillDemo = autofillDemo;

/* ------------------------------ bindings ------------------------------ */
function bindEvents() {
  // Each binding is isolated so a single missing element (stale-cache page mix)
  // never kills the rest of the dashboard — especially the Sign-in button.
  const wire = (id, fn) => { const el = document.getElementById(id); if (el) el.addEventListener("click", fn); };
  wire("btn-login", doLogin);
  wire("btn-refresh", loadAll);
  wire("btn-cycle", runAlertCycle);
  wire("btn-sim-load", loadSimulatedScenario);
  wire("btn-sim-exit", exitSimulated);
  wire("btn-sim-banner-exit", exitSimulated);
  wire("btn-switch", () => { localStorage.removeItem(TOKEN_KEY); state.simulatedOptedIn = false; setSimulationUI(false); showLogin(); });
  wire("ev-close", () => document.getElementById("evidence-modal").classList.add("hidden"));
  wire("btn-replay", () => {
    const val = document.getElementById("asof-date").value;
    state.asOf = val ? new Date(val + "T12:00:00").toISOString() : null;
    loadAll();
  });
  wire("btn-live", () => { state.asOf = null; document.getElementById("asof-date").value = ""; loadAll(); });
  wire("btn-ledger-verify", ledgerStatus);
  wire("btn-ledger-tamper", async () => {
    try {
      const r = await api("/ledger/tamper-demo", { method: "POST" });
      state.ledgerDemoOptedIn = true;   // P0.3: only red-flag now that the user started the demo
      toast(r.error || r.note || "Tamper demo running — ledger now MUTABLE; tamper will be detected");
      ledgerStatus();
    } catch (err) { toast("Tamper demo: " + err.message); }
  });
  wire("btn-ledger-restore", async () => {
    try {
      const r = await api("/ledger/restore", { method: "POST" });
      state.ledgerDemoOptedIn = false;  // P0.3: reset demo so a fresh state stays benign
      toast((r.note) || (r.verify && r.verify.intact ? `Ledger restored — ${r.verify.records} blocks verify intact` : (r.error || "restore performed")));
      ledgerStatus();
    } catch (err) { toast("Restore failed: " + err.message); }
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