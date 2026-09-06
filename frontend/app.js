/* CashGuard AI — Government-Grade Cybercrime Intelligence Command Platform
   Smart India Hackathon 2026 · SIH26184 · MHA / I4C
   Complete frontend rewrite — vanilla JS, no frameworks, no build tools. */
"use strict";

/* ==================== CONSTANTS ==================== */
const TOKEN_KEY = "cashguard_token";
const COMPLAINT_TYPES = ["phishing", "investment_fraud", "job_fraud", "upi_fraud", "digital_arrest", "sextortion"];
const RISK_COLORS = { LOW: "#22C55E", MEDIUM: "#F59E0B", HIGH: "#F97316", CRITICAL: "#EF4444" };
const TIER_COLORS = { DISPATCH: "#EF4444", ACTION: "#F97316", MONITOR: "#22C55E" };
const MULE_TYPE_COLORS = { account: "#EF4444", victim: "#22C55E", phone: "#F59E0B", atm: "#3B82F6" };
const INDIA_CENTER = [20.5, 78.9];
const INDIA_ZOOM = 5;

/* ==================== SVG ICONS ==================== */
const ICONS = {
  shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/></svg>',
  map: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 7l6-3 6 3 6-3v13l-6 3-6-3-6 3z"/><path d="M9 4v13"/><path d="M15 7v13"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
  dollar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>',
  network: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="5" r="3"/><circle cx="5" cy="19" r="3"/><circle cx="19" cy="19" r="3"/><line x1="12" y1="8" x2="5" y2="16"/><line x1="12" y1="8" x2="19" y2="16"/></svg>',
  ledger: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
  heartbeat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>',
  file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><polyline points="20 6 9 17 4 12"/></svg>',
  chevronR: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><polyline points="9 18 15 12 9 6"/></svg>',
  chevronL: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><polyline points="15 18 9 12 15 6"/></svg>',
  menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>',
  target: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
  download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
  eye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
  logOut: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>',
  user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
  globe: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
  layers: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>',
};

function icon(name, cls) {
  return `<span class="icon${cls ? ' ' + cls : ''}" aria-hidden="true">${ICONS[name] || ''}</span>`;
}

/* ==================== STATE ==================== */
const state = {
  user: null,
  stateFilter: "All",
  cityFilter: "All",
  bankFilter: "All",
  category: "All",
  asOf: null,
  horizon: "24",
  risk: [],
  alerts: [],
  stats: null,
  banks: [],
  complaints: [],
  cityCoords: {},
  recovery: [],
  funnel: null,
  inbox: [],
  handoffs: [],
  showHeat: true,
  showForecast: true,
  simulatedOptedIn: false,
  simulatedEvidence: {},
  _loadGen: 0,
  currentView: "overview",
  _viewsRendered: {},
  _sortedRisk: null,
  _abortController: null,
  sidebarCollapsed: false,
};

/* ==================== HELPERS ==================== */
function getToken() { return localStorage.getItem(TOKEN_KEY); }

function debounce(fn, ms) {
  let t;
  return function (...args) { clearTimeout(t); t = setTimeout(() => fn.apply(this, args), ms); };
}

function esc(s) { return s == null ? "" : String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

function riskLevel(s) {
  if (s >= 0.85) return "CRITICAL";
  if (s >= 0.7) return "HIGH";
  if (s >= 0.4) return "MEDIUM";
  return "LOW";
}
function riskColor(s) { return RISK_COLORS[riskLevel(s)]; }
function riskCls(s) { return "risk-" + riskLevel(s).toLowerCase(); }
function riskPct(s) { return (s * 100).toFixed(1) + "%"; }

function riskPill(s) {
  const lv = riskLevel(s);
  return `<span class="risk-pill risk-${lv.toLowerCase()}">${lv} ${riskPct(s)}</span>`;
}

function tierBadge(tier) {
  if (!tier) return "";
  const t = tier.toUpperCase();
  return `<span class="tier-badge tier-${t.toLowerCase()}">${t}</span>`;
}

function statusPill(s) {
  const cls = s === "new" ? "status-new" : s === "actioned" ? "status-actioned" : "status-default";
  return `<span class="status-pill ${cls}">${esc(s)}</span>`;
}

function fmtTime(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }); }
  catch { return esc(iso); }
}

function maskedAccount(token) {
  if (!token) return "—";
  return token.length > 12 ? token.slice(0, 8) + "····" + token.slice(-4) : token;
}

function fmtMetric(v, dp) {
  if (v == null || isNaN(v)) return "—";
  return typeof v === "number" ? v.toFixed(dp || 0) : String(v);
}

function getSortedRisk() {
  if (state._sortedRisk) return state._sortedRisk;
  state._sortedRisk = [...(state.risk || [])].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));
  return state._sortedRisk;
}

function invalidateRiskCache() { state._sortedRisk = null; }

/* ==================== API ==================== */
async function api(path, opts = {}) {
  const token = getToken();
  const headers = { ...(opts.headers || {}) };
  if (token) headers["Authorization"] = "Bearer " + token;
  if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  if (state._abortController && opts.method === "GET") {
    opts.signal = state._abortController.signal;
  }
  const resp = await fetch(path, { ...opts, headers });
  if (resp.status === 401) { showLogin(); throw new Error("Session expired"); }
  if (resp.status === 403) { toast("Access denied for your role", "error"); throw new Error("Forbidden"); }
  if (!resp.ok) { const t = await resp.text().catch(() => ""); throw new Error(`Request failed (${resp.status})`); }
  const ct = resp.headers.get("content-type") || "";
  if (ct.includes("application/json")) return resp.json();
  return resp;
}

/* ==================== TOAST / NOTICE ==================== */
function toast(msg, type) {
  const el = document.getElementById("toast");
  if (!el) return;
  if (el._t) clearTimeout(el._t);
  el.textContent = msg;
  el.className = "toast " + (type || "");
  el._t = setTimeout(() => el.classList.add("hidden"), 4500);
}

function clearNotice() {
  const el = document.getElementById("notice");
  if (el) el.classList.add("hidden");
}

function showNotice(msg) {
  const el = document.getElementById("notice");
  const txt = document.getElementById("notice-text");
  if (el && txt) { txt.textContent = msg; el.classList.remove("hidden"); }
}

/* ==================== MAP CONTROLLER ==================== */
class MapController {
  constructor(containerId, opts = {}) {
    this.containerId = containerId;
    this.opts = Object.assign({ center: INDIA_CENTER, zoom: INDIA_ZOOM, maxZoom: 18 }, opts);
    this.map = null;
    this.atmLayer = null;
    this.heatLayer = null;
    this.tileLayer = null;
    this.offline = false;
    this._markerMap = new Map();
    this._resizeObs = null;
    this._failCount = 0;
    this._loaded = false;
  }

  init() {
    if (this.map) return this;
    if (typeof L === "undefined") {
      this._renderFallback();
      return this;
    }
    const el = document.getElementById(this.containerId);
    if (!el || el.clientHeight < 10) return this;

    try {
      this.map = L.map(this.containerId, {
        center: this.opts.center,
        zoom: this.opts.zoom,
        zoomControl: false,
        attributionControl: true,
      });
      L.control.zoom({ position: "topright" }).addTo(this.map);

      this.tileLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: this.opts.maxZoom,
        errorTileUrl: "",
      });

      this.tileLayer.on("tileload", () => { this._loaded = true; this._failCount = 0; });
      this.tileLayer.on("tileerror", () => {
        this._failCount++;
        if (!this._loaded && this._failCount >= 6) this._enableOffline();
      });

      this.tileLayer.addTo(this.map);
      this.atmLayer = L.layerGroup().addTo(this.map);

      setTimeout(() => {
        if (!this._loaded) this._enableOffline();
      }, 8000);

      this._resizeObs = new ResizeObserver(() => {
        if (this.map) this.map.invalidateSize();
      });
      this._resizeObs.observe(el);
    } catch (e) {
      console.warn("Map init failed:", e);
      this._renderFallback();
    }
    return this;
  }

  invalidateSize() {
    if (this.map) {
      requestAnimationFrame(() => this.map.invalidateSize());
    }
  }

  setMarkers(atms, riskScores, opts = {}) {
    if (!this.map || !this.atmLayer) return;
    const riskMap = new Map();
    (riskScores || []).forEach(r => riskMap.set(r.atm_id, r));

    const existingIds = new Set();
    this.atmLayer.eachLayer(l => {
      if (l._atmId) existingIds.add(l._atmId);
    });

    const toAdd = [];
    (atms || []).forEach(atm => {
      if (atm.latitude == null || atm.longitude == null) return;
      const risk = riskMap.get(atm.atm_id);
      const score = risk ? risk.risk_score : 0;
      const lv = riskLevel(score);
      const color = RISK_COLORS[lv];

      if (this._markerMap.has(atm.atm_id)) {
        const marker = this._markerMap.get(atm.atm_id);
        marker.setRadius(4 + score * 14);
        marker.setStyle({ color, fillColor: color, fillOpacity: 0.35 + score * 0.45 });
        return;
      }

      const marker = L.circleMarker([atm.latitude, atm.longitude], {
        radius: 4 + score * 14,
        color: color,
        weight: 1.5,
        fillColor: color,
        fillOpacity: 0.35 + score * 0.45,
        className: lv === "CRITICAL" ? "marker-pulse" : "",
      });

      marker._atmId = atm.atm_id;
      const popupHtml = `<div class="map-popup">
        <b>${esc(atm.atm_id)}</b><br>
        <span class="popup-bank">${esc(atm.bank_name)}</span> · ${esc(atm.branch_name)}<br>
        ${esc(atm.city)}, ${esc(atm.district)}<br>
        <div class="popup-risk">${riskPill(score)}</div>
        ${risk ? `<div class="popup-action">${esc(risk.recommended_action || "")}</div>` : ""}
      </div>`;
      marker.bindPopup(popupHtml, { maxWidth: 260 });
      marker.on("click", () => {
        if (opts.onMarkerClick) opts.onMarkerClick(atm, risk);
      });
      toAdd.push(marker);
      this._markerMap.set(atm.atm_id, marker);
    });

    toAdd.forEach(m => this.atmLayer.addLayer(m));
  }

  focusAtm(atmId) {
    const marker = this._markerMap.get(atmId);
    if (marker && this.map) {
      this.map.setView(marker.getLatLng(), 14, { animate: true });
      marker.openPopup();
    }
  }

  fitToResults() {
    if (!this.map || this._markerMap.size === 0) return;
    const bounds = L.latLngBounds([]);
    this._markerMap.forEach(m => bounds.extend(m.getLatLng()));
    this.map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
  }

  fitToIndia() {
    if (this.map) this.map.setView(INDIA_CENTER, INDIA_ZOOM, { animate: true });
  }

  clearLayers() {
    if (this.atmLayer) this.atmLayer.clearLayers();
    this._markerMap.clear();
  }

  destroy() {
    if (this._resizeObs) { this._resizeObs.disconnect(); this._resizeObs = null; }
    if (this.map) { this.map.remove(); this.map = null; }
    this.atmLayer = null;
    this._markerMap.clear();
  }

  _enableOffline() {
    if (this.offline || !this.map) return;
    this.offline = true;
    if (this.tileLayer) this.map.removeLayer(this.tileLayer);
    const el = document.getElementById(this.containerId);
    if (el) {
      const ov = document.createElement("div");
      ov.className = "map-offline-overlay";
      ov.innerHTML = '<div class="map-offline-text">Offline Intelligence Map</div>';
      el.appendChild(ov);
    }
    this._drawOfflineCanvas();
  }

  _drawOfflineCanvas() {
    if (!this.map) return;
    const el = document.getElementById(this.containerId);
    if (!el) return;
    const canvas = document.createElement("canvas");
    canvas.className = "offline-canvas";
    canvas.width = el.clientWidth * (window.devicePixelRatio || 1);
    canvas.height = el.clientHeight * (window.devicePixelRatio || 1);
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    el.appendChild(canvas);
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    ctx.scale(dpr, dpr);
    const W = el.clientWidth, H = el.clientHeight;
    ctx.fillStyle = "#0B1220";
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = "rgba(148,163,184,0.08)";
    ctx.lineWidth = 0.5;
    for (let x = 0; x < W; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
    for (let y = 0; y < H; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
    this._markerMap.forEach((marker) => {
      const latlng = marker.getLatLng();
      const point = this.map.latLngToContainerPoint(latlng);
      const score = marker.options.fillOpacity > 0.6 ? 0.9 : 0.5;
      const color = marker.options.fillColor || "#F59E0B";
      ctx.beginPath();
      ctx.arc(point.x, point.y, 3 + score * 5, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.6;
      ctx.fill();
      ctx.globalAlpha = 1;
    });
  }

  _renderFallback() {
    const el = document.getElementById(this.containerId);
    if (el) {
      el.innerHTML = '<div class="map-fallback"><div class="map-fallback-icon">' + ICONS.map + '</div><p>Map unavailable</p><p class="text-muted">Intelligence map requires a modern browser with JavaScript enabled.</p></div>';
    }
  }
}

/* ==================== VIEW SWITCHING ==================== */
function switchView(view) {
  state.currentView = view;
  document.querySelectorAll(".view-panel").forEach(p => p.classList.add("hidden"));
  const panel = document.getElementById("view-" + view);
  if (panel) panel.classList.remove("hidden");

  document.querySelectorAll(".nav-item").forEach(n => {
    n.classList.toggle("active", n.dataset.view === view);
  });

  const titles = {
    overview: "National Overview", risk: "Risk Intelligence", alerts: "Alert Management",
    investigations: "Investigations", recovery: "Recovery Operations", mule: "Mule Network",
    ledger: "Audit Trail", model: "Model Health", reports: "Reports & Analytics",
  };
  const titleEl = document.getElementById("topbar-view-title");
  if (titleEl) titleEl.textContent = titles[view] || view;

  if (!state._viewsRendered[view]) {
    state._viewsRendered[view] = true;
    renderViewContent(view);
  }

  setTimeout(() => {
    if (view === "overview" || view === "risk") {
      if (view === "overview" && window._mainMap) window._mainMap.invalidateSize();
      if (view === "risk" && window._riskMap) window._riskMap.invalidateSize();
    }
  }, 100);
}

function renderViewContent(view) {
  switch (view) {
    case "overview": renderOverview(); break;
    case "risk": renderRiskIntelligence(); break;
    case "alerts": renderAlertsView(); break;
    case "investigations": renderInvestigations(); break;
    case "recovery": renderRecoveryView(); break;
    case "mule": renderMuleView(); break;
    case "ledger": renderLedgerView(); break;
    case "model": renderModelView(); break;
    case "reports": renderReportsView(); break;
  }
}

/* ==================== ROLE SIDEBAR ==================== */
function updateSidebarForRole(role) {
  const permissions = {
    I4C_ADMIN: ["overview", "risk", "alerts", "investigations", "recovery", "mule", "ledger", "model", "reports"],
    POLICE_STATE: ["overview", "risk", "alerts", "investigations", "reports"],
    POLICE_DISTRICT: ["overview", "risk", "alerts", "investigations", "reports"],
    BANK: ["overview", "alerts", "recovery"],
  };
  const allowed = permissions[role] || permissions.I4C_ADMIN;
  document.querySelectorAll(".nav-item").forEach(n => {
    const v = n.dataset.view;
    n.style.display = allowed.includes(v) ? "" : "none";
  });
  const cycleBtn = document.getElementById("btn-cycle");
  if (cycleBtn) cycleBtn.style.display = role === "BANK" ? "none" : "";
}

/* ==================== SKELETON HELPERS ==================== */
function skeletonCards(n) {
  return Array(n).fill('<div class="skeleton skeleton-card"></div>').join("");
}
function skeletonRows(n) {
  return Array(n).fill('<div class="skeleton skeleton-row"></div>').join("");
}
function skeletonTable(n) {
  return `<div class="skeleton-table">${Array(n).fill('<div class="skeleton skeleton-row"></div>').join("")}</div>`;
}

/* ==================== LOADING STATE HELPER ==================== */
function setLoading(containerId, msg) {
  const el = document.getElementById(containerId);
  if (el) el.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>${esc(msg)}</p></div>`;
}

function setError(containerId, msg, retryFn) {
  const el = document.getElementById(containerId);
  if (el) el.innerHTML = `<div class="error-state"><p>${esc(msg)}</p>${retryFn ? '<button class="btn btn-sm btn-ghost" onclick="(' + retryFn.name + ')()">Retry</button>' : ""}</div>`;
}

function setEmpty(containerId, msg) {
  const el = document.getElementById(containerId);
  if (el) el.innerHTML = `<div class="empty-state"><p>${esc(msg)}</p></div>`;
}

/* ==================== OVERVIEW ==================== */
async function renderOverview() {
  const statsEl = document.getElementById("overview-stats");
  const priorityEl = document.getElementById("priority-actions");
  const alertTableEl = document.getElementById("alert-table");
  const hotspotEl = document.getElementById("hotspot-table");

  if (statsEl) statsEl.innerHTML = skeletonCards(5);

  try {
    if (!state.stats) {
      const s = await api("/stats/summary");
      state.stats = s;
    }
    renderOverviewStats();
  } catch (e) { console.warn("Stats load failed:", e); }

  renderPriorityActions();
  if (alertTableEl) renderAlertTable("alert-table", (state.alerts || []).slice(0, 10));
  if (hotspotEl) renderHotspotTable();

  setTimeout(() => {
    if (window._mainMap) window._mainMap.invalidateSize();
  }, 200);
}

function renderOverviewStats() {
  const el = document.getElementById("overview-stats");
  if (!el || !state.stats) return;
  const s = state.stats;
  el.innerHTML = `
    <div class="stat-card stat-critical"><div class="stat-label">High-Risk ATMs</div><div class="stat-value">${fmtMetric(s.high_risk_atms)}</div><div class="stat-sub">Above 0.7 threshold</div></div>
    <div class="stat-card stat-warning"><div class="stat-label">Active Alerts</div><div class="stat-value">${fmtMetric(s.alerts_new || s.alerts_total)}</div><div class="stat-sub">${fmtMetric(s.alerts_actioned)} actioned</div></div>
    <div class="stat-card"><div class="stat-label">Complaints (24h)</div><div class="stat-value">${fmtMetric(s.complaints_24h)}</div><div class="stat-sub">${fmtMetric(s.total_complaints)} total</div></div>
    <div class="stat-card"><div class="stat-label">Fraud Withdrawals (7d)</div><div class="stat-value">${fmtMetric(s.fraud_withdrawals_7d)}</div><div class="stat-sub">${fmtMetric(s.total_withdrawals)} total</div></div>
    <div class="stat-card"><div class="stat-label">ATMs Monitored</div><div class="stat-value">${fmtMetric(s.total_atms)}</div><div class="stat-sub">Across all jurisdictions</div></div>`;
}

function renderPriorityActions() {
  const el = document.getElementById("priority-actions");
  if (!el) return;
  const top = getSortedRisk().slice(0, 5);
  if (top.length === 0) { setEmpty("priority-actions", "No high-risk ATMs detected."); return; }
  el.innerHTML = top.map((r, i) => `
    <div class="priority-item" onclick="focusAtmFromOverview('${esc(r.atm_id)}')" role="button" tabindex="0" aria-label="Focus ATM ${esc(r.atm_id)}">
      <div class="priority-rank">${i + 1}</div>
      <div class="priority-info">
        <div class="priority-atm">${esc(r.atm_id)} · ${esc(r.bank_name)}</div>
        <div class="priority-location">${esc(r.city)}, ${esc(r.district)}</div>
      </div>
      <div class="priority-score">${riskPill(r.risk_score)}</div>
    </div>`).join("");
}

function focusAtmFromOverview(atmId) {
  const r = state.risk.find(x => x.atm_id === atmId);
  if (r) openDrawer(r);
  if (window._mainMap) window._mainMap.focusAtm(atmId);
}

function renderHotspotTable() {
  const el = document.getElementById("hotspot-table");
  if (!el) return;
  const top = getSortedRisk().slice(0, 20);
  if (top.length === 0) { setEmpty("hotspot-table", "No risk data available."); return; }
  const countEl = document.getElementById("hotspot-count");
  if (countEl) countEl.textContent = top.length;
  el.innerHTML = `<table class="data-table"><thead><tr>
    <th>ATM</th><th>Bank</th><th>City</th><th>Risk</th><th>Action</th>
  </tr></thead><tbody>${top.map(r => `<tr onclick="focusAtmFromOverview('${esc(r.atm_id)}')" class="clickable-row" role="button" tabindex="0">
    <td class="mono">${esc(r.atm_id)}</td>
    <td>${esc(r.bank_name)}</td>
    <td>${esc(r.city)}</td>
    <td>${riskPill(r.risk_score)}</td>
    <td class="text-secondary">${esc(r.recommended_action || "Monitor")}</td>
  </tr>`).join("")}</tbody></table>`;
}

/* ==================== MAIN MAP INIT ==================== */
function initMainMap() {
  if (window._mainMap && window._mainMap.map) { window._mainMap.invalidateSize(); return; }
  window._mainMap = new MapController("map", {
    onMarkerClick: (atm, risk) => { if (risk) openDrawer(risk); }
  }).init();
}

function renderMainMap() {
  initMainMap();
  if (!window._mainMap || !window._mainMap.map) return;
  const atms = state.risk.length > 0 ? state.risk : [];
  window._mainMap.setMarkers(atms, state.risk, {
    onMarkerClick: (atm, risk) => { if (risk) openDrawer(risk); }
  });
  if (atms.length > 0) window._mainMap.fitToResults();
}

/* ==================== RISK INTELLIGENCE ==================== */
async function renderRiskIntelligence() {
  const mapEl = document.getElementById("risk-map");
  const listEl = document.getElementById("risk-atm-list");
  if (!mapEl || !listEl) return;

  if (!window._riskMap) {
    window._riskMap = new MapController("risk-map", {
      onMarkerClick: (atm, risk) => { if (risk) openDrawer(risk); }
    }).init();
  }
  window._riskMap.invalidateSize();

  const sorted = getSortedRisk();
  window._riskMap.clearLayers();
  window._riskMap.setMarkers(sorted, state.risk, {
    onMarkerClick: (atm, risk) => { if (risk) openDrawer(risk); }
  });
  if (sorted.length > 0) window._riskMap.fitToResults();

  renderRiskAtmList(sorted);
}

function renderRiskAtmList(sorted) {
  const el = document.getElementById("risk-atm-list");
  if (!el) return;
  if (!sorted || sorted.length === 0) { setEmpty("risk-atm-list", "No risk data available for current filters."); return; }
  el.innerHTML = sorted.map(r => `
    <div class="risk-list-item" onclick="focusRiskAtm('${esc(r.atm_id)}')" role="button" tabindex="0">
      <div class="risk-list-header">
        <span class="mono">${esc(r.atm_id)}</span>
        ${riskPill(r.risk_score)}
      </div>
      <div class="risk-list-detail">${esc(r.bank_name)} · ${esc(r.city)}</div>
      <div class="risk-list-action">${esc(r.recommended_action || "Monitor")}</div>
    </div>`).join("");
}

function focusRiskAtm(atmId) {
  if (window._riskMap) window._riskMap.focusAtm(atmId);
  const r = state.risk.find(x => x.atm_id === atmId);
  if (r) openDrawer(r);
}

/* ==================== ATM INTELLIGENCE DRAWER ==================== */
function openDrawer(r) {
  const overlay = document.getElementById("drawer-overlay");
  const drawer = document.getElementById("atm-drawer");
  const header = document.getElementById("drawer-atm-id");
  const meta = document.getElementById("drawer-atm-meta");
  const body = document.getElementById("drawer-body");
  const footer = document.getElementById("drawer-footer");
  if (!overlay || !drawer || !body) return;

  overlay.classList.remove("hidden");
  drawer.classList.add("open");

  if (header) header.innerHTML = `${esc(r.atm_id)} ${riskPill(r.risk_score)}`;
  if (meta) meta.textContent = `${esc(r.bank_name)} · ${esc(r.branch_name)} · ${esc(r.city)}`;

  body.innerHTML = `
    <div class="drawer-section">
      <h4>Location</h4>
      <div class="drawer-kv"><span>State</span><span>${esc(r.state)}</span></div>
      <div class="drawer-kv"><span>District</span><span>${esc(r.district)}</span></div>
      <div class="drawer-kv"><span>Police Station</span><span>${esc(r.police_station_area)}</span></div>
      <div class="drawer-kv"><span>Coordinates</span><span class="mono">${fmtMetric(r.latitude, 4)}, ${fmtMetric(r.longitude, 4)}</span></div>
    </div>
    <div class="drawer-section">
      <h4>Risk Assessment</h4>
      <div class="drawer-kv"><span>Risk Score</span><span>${riskPill(r.risk_score)}</span></div>
      <div class="drawer-kv"><span>Risk Level</span><span class="risk-label ${riskCls(r.risk_score)}">${riskLevel(r.risk_score)}</span></div>
      <div class="drawer-kv"><span>Forecast Horizon</span><span>${esc(state.horizon)}h</span></div>
      <div class="drawer-kv"><span>As Of</span><span>${fmtTime(r.as_of)}</span></div>
      ${r.emerging_risk ? `<div class="drawer-kv"><span>Emerging Risk</span><span class="pill pill-warn">Yes</span></div>` : ""}
    </div>
    <div class="drawer-section">
      <h4>Recommended Action</h4>
      <div class="drawer-action-box">${esc(r.recommended_action || "Enhanced monitoring recommended")}</div>
    </div>
    <div class="drawer-section" id="drawer-evidence-section">
      <h4>Evidence</h4>
      <div class="loading-state"><div class="spinner"></div><p>Loading evidence...</p></div>
    </div>`;

  footer.innerHTML = `
    <button class="btn btn-sm btn-ghost" onclick="drawerAction('${esc(r.atm_id)}', 'acknowledged')" aria-label="Acknowledge">${icon("check")} Acknowledge</button>
    <button class="btn btn-sm btn-ghost" onclick="drawerAction('${esc(r.atm_id)}', 'monitoring')" aria-label="Monitor">${icon("eye")} Monitor</button>
    <button class="btn btn-sm btn-ghost" onclick="drawerActionEscalate('${esc(r.atm_id)}')" aria-label="Escalate">${icon("alert")} Escalate</button>
    <button class="btn btn-sm btn-primary" onclick="drawerGenerateReport('${esc(r.atm_id)}', '${esc(r.alert_id || "")}')" aria-label="Generate Report">${icon("file")} Generate Report</button>
    <button class="btn btn-sm btn-ghost" onclick="closeDrawer()" aria-label="Close">${icon("x")} Close</button>`;

  loadDrawerEvidence(r);
}

function closeDrawer() {
  const overlay = document.getElementById("drawer-overlay");
  const drawer = document.getElementById("atm-drawer");
  if (overlay) overlay.classList.add("hidden");
  if (drawer) drawer.classList.remove("open");
}

async function loadDrawerEvidence(r) {
  const section = document.getElementById("drawer-evidence-section");
  if (!section) return;
  const alert = (state.alerts || []).find(a => a.atm_id === r.atm_id);
  if (!alert) { section.innerHTML = "<h4>Evidence</h4><p class='text-muted'>No active alert for this ATM.</p>"; return; }
  try {
    const ev = await api(`/alerts/${alert.alert_id}/evidence`);
    section.innerHTML = `<h4>Evidence</h4>
      <div class="drawer-kv"><span>Alert ID</span><span class="mono">${esc(alert.alert_id)}</span></div>
      <div class="drawer-kv"><span>Tier</span><span>${tierBadge(alert.tier)}</span></div>
      <div class="drawer-kv"><span>Recommended</span><span>${esc(alert.recommended_action)}</span></div>
      ${ev.data_through ? `<div class="drawer-kv"><span>Data Through</span><span>${fmtTime(ev.data_through)}</span></div>` : ""}
      ${ev.scoring_coverage_pct != null ? `<div class="drawer-kv"><span>Coverage</span><span>${fmtMetric(ev.scoring_coverage_coverage_pct || ev.scoring_coverage_pct, 1)}%</span></div>` : ""}
      ${ev.explainability_note ? `<div class="drawer-note">${esc(ev.explainability_note)}</div>` : ""}`;
  } catch (e) { section.innerHTML = "<h4>Evidence</h4><p class='text-muted'>Evidence temporarily unavailable.</p>"; }
}

async function drawerAction(atmId, status) {
  const alert = (state.alerts || []).find(a => a.atm_id === atmId);
  if (!alert) { toast("No active alert for this ATM", "error"); return; }
  try {
    await api(`/alerts/${alert.alert_id}/status`, { method: "POST", body: { status, reason: "" } });
    alert.status = status;
    alert.actioned_at = new Date().toISOString();
    toast(`ATM ${atmId}: ${status}`, "success");
    renderAlertTable("alert-table", (state.alerts || []).slice(0, 10));
    updateAlertBadge();
  } catch (e) { toast("Action failed: " + e.message, "error"); }
}

function drawerActionEscalate(atmId) {
  const alert = (state.alerts || []).find(a => a.atm_id === atmId);
  if (!alert) { toast("No active alert for this ATM", "error"); return; }
  const reason = prompt("Enter escalation reason:");
  if (reason === null) return;
  setAlertStatus(alert.alert_id, "escalated", reason);
}

async function drawerGenerateReport(atmId, alertId) {
  if (!alertId) { const alert = (state.alerts || []).find(a => a.atm_id === atmId); alertId = alert ? alert.alert_id : null; }
  if (!alertId) { toast("No alert ID available for report generation", "error"); return; }
  try {
    toast("Generating intelligence report...", "info");
    const result = await api(`/reports/hotspot/${alertId}`, { method: "POST" });
    if (result.pdf) {
      toast("Report generated successfully", "success");
      window.open(`/reports/${result.report_id}/download`, "_blank");
    }
  } catch (e) { toast("Report generation failed: " + e.message, "error"); }
}

/* ==================== ALERTS ==================== */
async function renderAlertsView() {
  const tableEl = document.getElementById("alerts-full-table");
  const countEl = document.getElementById("alerts-view-count");
  if (tableEl) {
    tableEl.innerHTML = skeletonTable(8);
    try {
      if (!state.alerts.length) {
        const data = await api("/alerts?limit=200");
        state.alerts = data;
      }
      renderAlertTable("alerts-full-table", state.alerts);
      if (countEl) countEl.textContent = state.alerts.length;
    } catch (e) { setError("alerts-full-table", "Failed to load alerts.", renderAlertsView); }
  }
}

function renderAlertTable(tableId, alerts) {
  const el = document.getElementById(tableId);
  if (!el) return;
  if (!alerts || alerts.length === 0) {
    el.innerHTML = '<div class="empty-state"><p>No active alerts</p><p class="text-muted">All monitored locations are currently below the intervention threshold.</p></div>';
    return;
  }
  el.innerHTML = `<table class="data-table"><thead><tr>
    <th>Alert</th><th>ATM</th><th>Location</th><th>Risk</th><th>Tier</th><th>Status</th><th>Actions</th>
  </tr></thead><tbody>${alerts.map(a => `<tr class="alert-row alert-${a.tier ? a.tier.toLowerCase() : "default"}">
    <td class="mono text-xs">${esc((a.alert_id || "").slice(0, 8))}</td>
    <td><span class="mono">${esc(a.atm_id)}</span><br><span class="text-xs text-muted">${esc(a.bank_name)}</span></td>
    <td>${esc(a.city)}, ${esc(a.district)}</td>
    <td>${riskPill(a.risk_score)}</td>
    <td>${tierBadge(a.tier)}</td>
    <td>${statusPill(a.status)}</td>
    <td class="alert-actions">${hitlButtons(a)}</td>
  </tr>`).join("")}</tbody></table>`;
}

function hitlButtons(a) {
  if (a.status !== "new") return `<span class="text-muted text-xs">${esc(a.status)}</span>`;
  return `<div class="btn-group">
    <button class="btn btn-xs btn-ok" onclick="setAlertStatus('${esc(a.alert_id)}','acknowledged')" title="Acknowledge">${icon("check")}</button>
    <button class="btn btn-xs btn-ghost" onclick="setAlertStatus('${esc(a.alert_id)}','monitoring')" title="Monitor">${icon("eye")}</button>
    <button class="btn btn-xs btn-warn" onclick="escalateAlert('${esc(a.alert_id)}')" title="Escalate">${icon("alert")}</button>
    <button class="btn btn-xs btn-danger" onclick="dismissAlert('${esc(a.alert_id)}')" title="Dismiss">${icon("x")}</button>
  </div>`;
}

function escalateAlert(alertId) {
  const reason = prompt("Enter escalation reason:");
  if (reason === null) return;
  setAlertStatus(alertId, "escalated", reason);
}

function dismissAlert(alertId) {
  const reason = prompt("Enter dismissal reason:");
  if (reason === null) return;
  setAlertStatus(alertId, "dismissed", reason);
}

async function setAlertStatus(alertId, status, reason) {
  try {
    await api(`/alerts/${alertId}/status`, { method: "POST", body: { status, reason: reason || "" } });
    const alert = state.alerts.find(a => a.alert_id === alertId);
    if (alert) { alert.status = status; alert.actioned_at = new Date().toISOString(); }
    toast(`Alert ${status}`, "success");
    renderAlertTable("alert-table", (state.alerts || []).slice(0, 10));
    renderAlertTable("alerts-full-table", state.alerts);
    updateAlertBadge();
  } catch (e) { toast("Action failed: " + e.message, "error"); }
}

function updateAlertBadge() {
  const badge = document.getElementById("sidebar-alert-badge");
  const newCount = (state.alerts || []).filter(a => a.status === "new").length;
  if (badge) { badge.textContent = newCount; badge.classList.toggle("hidden", newCount === 0); }
}

/* ==================== INVESTIGATIONS ==================== */
async function renderInvestigations() {
  renderMuleGraph();
  renderInbox();
  renderHandoffs();
}

async function renderMuleGraph() {
  const el = document.getElementById("mule-graph-table");
  const detailEl = document.getElementById("mule-graph-detail");
  if (!el) return;
  el.innerHTML = skeletonTable(5);
  try {
    const data = await api("/mule-graph/terminal-nodes?k=50");
    if (!data.nodes || data.nodes.length === 0) { setEmpty("mule-graph-table", "No terminal mule accounts detected."); return; }
    el.innerHTML = `<table class="data-table"><thead><tr>
      <th>Account</th><th>Terminal Risk</th><th>Trail</th>
    </tr></thead><tbody>${data.nodes.map(n => `<tr>
      <td class="mono">${maskedAccount(n.account_token)}</td>
      <td>${riskPill(n.terminal_risk)}</td>
      <td><button class="btn btn-xs btn-ghost" onclick="loadMuleTrail('${esc(n.account_token)}')">Trail</button></td>
    </tr>`).join("")}</tbody></table>`;
  } catch (e) { setError("mule-graph-table", "Failed to load mule data.", renderMuleGraph); }
}

async function loadMuleTrail(token) {
  const el = document.getElementById("mule-graph-detail");
  if (!el) return;
  el.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Loading trail...</p></div>';
  try {
    const data = await api(`/mule-graph/trail/${encodeURIComponent(token)}`);
    el.innerHTML = `<h4>Money Trail: ${maskedAccount(token)}</h4>
      <div class="drawer-kv"><span>As Of</span><span>${fmtTime(data.as_of)}</span></div>
      <div class="drawer-kv"><span>Window</span><span>${data.window_days} days</span></div>
      ${data.chains ? `<div class="drawer-section"><h4>Chains</h4><pre class="code-block">${esc(JSON.stringify(data.chains, null, 2))}</pre></div>` : ""}
      ${data.edges ? `<div class="drawer-section"><h4>Edges</h4><p class="text-muted">${(data.edges || []).length} transfer edges</p></div>` : ""}`;
  } catch (e) { el.innerHTML = '<p class="text-muted">Trail data unavailable.</p>'; }
}

async function renderInbox() {
  const el = document.getElementById("inbox-panel");
  if (!el) return;
  try {
    const data = await api("/mock-i4c-inbox");
    if (!data || data.length === 0) { setEmpty("inbox-panel", "No intelligence messages."); return; }
    el.innerHTML = (data || []).slice(0, 15).map(m => {
      const p = m.payload || {};
      return `<div class="inbox-msg">
        <div class="inbox-header"><span class="pill">${esc(m.channel)}</span> <span class="text-xs text-muted">${fmtTime(m.received_at)}</span></div>
        <div class="inbox-body">${esc(p.message || p.subject || JSON.stringify(p).slice(0, 200))}</div>
      </div>`;
    }).join("");
  } catch (e) { el.innerHTML = '<p class="text-muted">Inbox unavailable.</p>'; }
}

async function renderHandoffs() {
  const el = document.getElementById("handoff-panel");
  if (!el) return;
  try {
    const data = await api("/alerts/handoffs/list");
    const handoffs = data.handoffs || [];
    const countEl = document.getElementById("handoff-count");
    if (countEl) countEl.textContent = handoffs.length;
    if (handoffs.length === 0) { setEmpty("handoff-panel", "No cross-state handoffs."); return; }
    el.innerHTML = handoffs.map(h => `<div class="handoff-item">
      <div class="handoff-header">
        <span class="mono">${esc(h.handoff_id.slice(0, 8))}</span>
        <span class="pill ${h.status === 'ack' ? 'pill-ok' : 'pill-warn'}">${esc(h.status)}</span>
      </div>
      <div class="handoff-detail">${esc(h.origin_state)} → ${esc(h.receiving_state)}</div>
      <div class="text-xs text-muted">${fmtTime(h.created_at)}</div>
      ${h.status !== "ack" ? `<button class="btn btn-xs btn-ok" onclick="handoffAck('${esc(h.handoff_id)}')">Acknowledge</button>` : ""}
    </div>`).join("");
  } catch (e) { el.innerHTML = '<p class="text-muted">Handoffs unavailable.</p>'; }
}

async function handoffAck(handoffId) {
  try {
    await api(`/alerts/handoffs/${handoffId}/ack`, { method: "POST", body: { status: "ack", note: "" } });
    toast("Handoff acknowledged", "success");
    renderHandoffs();
  } catch (e) { toast("Failed to acknowledge handoff", "error"); }
}

/* ==================== RECOVERY ==================== */
async function renderRecoveryView() {
  const funnelEl = document.getElementById("i4c-funnel");
  const queueEl = document.getElementById("recovery-queue");
  const outcomeEl = document.getElementById("outcome-panel");

  if (funnelEl) {
    try {
      const f = await api("/recovery/funnel?days=7");
      state.funnel = f;
      const stages = [
        { label: "Flagged", value: f.flagged || 0, color: "var(--warn)" },
        { label: "Held", value: f.held || 0, color: "var(--accent)" },
        { label: "Recovered", value: f.recovered || 0, color: "var(--ok)" },
      ];
      const max = Math.max(...stages.map(s => s.value), 1);
      funnelEl.innerHTML = `<div class="funnel">${stages.map(s => `
        <div class="funnel-stage">
          <div class="funnel-bar" style="width:${(s.value / max * 100)}%;background:${s.color}"></div>
          <div class="funnel-label">${s.label}</div>
          <div class="funnel-value">${fmtMetric(s.value)}</div>
        </div>`).join("")}</div>`;
    } catch (e) { funnelEl.innerHTML = '<p class="text-muted">Funnel data unavailable.</p>'; }
  }

  if (queueEl) {
    queueEl.innerHTML = skeletonTable(3);
    try {
      const recs = await api("/recovery/recommendations");
      state.recovery = recs || [];
      if (recs.length === 0) { setEmpty("recovery-queue", "No fund-block recommendations."); return; }
      queueEl.innerHTML = `<table class="data-table"><thead><tr>
        <th>Account</th><th>Bank</th><th>At Risk</th><th>ATM</th><th>Status</th><th>Actions</th>
      </tr></thead><tbody>${recs.map(r => `<tr>
        <td class="mono">${maskedAccount(r.account_token)}</td>
        <td>${esc(r.home_bank)}</td>
        <td>₹${fmtMetric(r.amount_at_risk, 2)}</td>
        <td class="mono">${esc(r.suspected_atm || "—")}</td>
        <td>${statusPill(r.status)}</td>
        <td><div class="btn-group">
          ${r.status === "flagged" ? `<button class="btn btn-xs btn-warn" onclick="updateRecovery('${esc(r.rec_id)}','held')">Hold</button>` : ""}
          ${r.status === "held" ? `<button class="btn btn-xs btn-ok" onclick="updateRecovery('${esc(r.rec_id)}','recovered')">Recovered</button>` : ""}
        </div></td>
      </tr>`).join("")}</tbody></table>`;
    } catch (e) { setError("recovery-queue", "Failed to load recovery data.", renderRecoveryView); }
  }

  if (outcomeEl) {
    try {
      const o = await api("/alerts/outcomes/summary");
      outcomeEl.innerHTML = `<div class="outcome-grid">
        <div class="drawer-kv"><span>Total Evaluated</span><span>${fmtMetric(o.total_evaluated)}</span></div>
        <div class="drawer-kv"><span>True Positives</span><span class="text-ok">${fmtMetric(o.true_positives)}</span></div>
        <div class="drawer-kv"><span>False Positives</span><span class="text-danger">${fmtMetric(o.false_positives)}</span></div>
        <div class="drawer-kv"><span>Precision</span><span>${fmtMetric(o.precision, 3)}</span></div>
      </div>`;
    } catch (e) { outcomeEl.innerHTML = '<p class="text-muted">Outcome data unavailable.</p>'; }
  }
}

async function updateRecovery(recId, status) {
  if (status === "recovered" && !confirm("Confirm this account has been recovered?")) return;
  try {
    await api(`/recovery/${recId}/status`, { method: "POST", body: { status, amount_held: 0, amount_recovered: 0 } });
    toast(`Recovery status updated: ${status}`, "success");
    renderRecoveryView();
  } catch (e) { toast("Recovery update failed: " + e.message, "error"); }
}

/* ==================== MULE NETWORK ==================== */
async function renderMuleView() {
  const wrapEl = document.getElementById("mule-network-wrap");
  if (!wrapEl) return;
  wrapEl.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Loading mule network...</p></div>';
  try {
    const data = await api("/graph/mule-network?depth=2&include_phone=true&limit=100");
    if (!data.nodes || data.nodes.length === 0) { setEmpty("mule-network-wrap", "No mule network data available."); return; }
    renderMuleSVG(wrapEl, data);
  } catch (e) { setError("mule-network-wrap", "Failed to load mule network.", renderMuleView); }
}

function renderMuleSVG(container, data) {
  const nodes = data.nodes || [];
  const edges = data.edges || [];
  const W = container.clientWidth || 800;
  const H = 500;
  const positions = {};
  nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / nodes.length;
    const r = Math.min(W, H) * 0.35;
    positions[n.id] = { x: W / 2 + r * Math.cos(angle), y: H / 2 + r * Math.sin(angle) };
  });

  let svg = `<svg viewBox="0 0 ${W} ${H}" class="mule-svg" xmlns="http://www.w3.org/2000/svg">`;
  svg += `<defs><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(148,163,184,0.3)"/></marker></defs>`;

  edges.forEach(e => {
    const from = positions[e.from];
    const to = positions[e.to];
    if (from && to) {
      svg += `<line x1="${from.x}" y1="${from.y}" x2="${to.x}" y2="${to.y}" stroke="rgba(148,163,184,0.2)" stroke-width="1" marker-end="url(#arrow)"/>`;
    }
  });

  nodes.forEach(n => {
    const pos = positions[n.id];
    if (!pos) return;
    const color = MULE_TYPE_COLORS[n.type] || "#94A3B8";
    const r = n.type === "atm" ? 8 : n.type === "account" ? 6 : 4;
    svg += `<circle cx="${pos.x}" cy="${pos.y}" r="${r}" fill="${color}" opacity="0.8" stroke="${color}" stroke-width="1.5"/>`;
    if (n.type === "atm" || n.type === "account") {
      svg += `<text x="${pos.x}" y="${pos.y + r + 12}" text-anchor="middle" fill="#94A3B8" font-size="9">${esc(n.label || n.id.slice(0, 8))}</text>`;
    }
  });

  svg += "</svg>";
  container.innerHTML = `<div class="mule-legend">
    <span><span class="dot" style="background:#EF4444"></span> Account</span>
    <span><span class="dot" style="background:#22C55E"></span> Victim</span>
    <span><span class="dot" style="background:#F59E0B"></span> Phone</span>
    <span><span class="dot" style="background:#3B82F6"></span> ATM</span>
  </div>${svg}`;
  if (data.stats) {
    container.innerHTML += `<div class="mule-stats">
      <span>${fmtMetric(data.stats.accounts)} accounts</span>
      <span>${fmtMetric(data.stats.complaints)} complaints</span>
      <span>${fmtMetric(data.stats.phones)} phones</span>
      <span>${fmtMetric(data.components)} components</span>
    </div>`;
  }
}

/* ==================== LEDGER ==================== */
async function renderLedgerView() {
  const previewEl = document.getElementById("ledger-preview");
  const statusEl = document.getElementById("ledger-status");
  if (!previewEl) return;

  try {
    const verify = await api("/ledger/verify");
    if (statusEl) {
      const isValid = verify.valid || verify.is_valid;
      statusEl.innerHTML = `<div class="ledger-status ${isValid ? "ledger-ok" : "ledger-tampered"}">
        <span class="ledger-icon">${isValid ? ICONS.check : ICONS.alert}</span>
        <span>${isValid ? "VERIFIED" : "TAMPERED"}</span>
      </div>`;
    }
  } catch (e) { if (statusEl) statusEl.innerHTML = '<span class="text-muted">Verification unavailable</span>'; }

  try {
    const data = await api("/ledger?limit=20&offset=0");
    const records = data.records || [];
    if (records.length === 0) { setEmpty("ledger-preview", "No ledger records."); return; }
    previewEl.innerHTML = `<table class="data-table"><thead><tr>
      <th>#</th><th>Time</th><th>Actor</th><th>Event</th><th>Entity</th><th>Hash</th>
    </tr></thead><tbody>${records.map(r => `<tr>
      <td>${fmtMetric(r.index)}</td>
      <td class="text-xs">${fmtTime(r.created_at)}</td>
      <td>${esc(r.actor)}</td>
      <td><span class="pill">${esc(r.event_type)}</span></td>
      <td class="mono text-xs">${esc(r.entity_id)}</td>
      <td class="mono text-xs hash-cell">${esc((r.hash || "").slice(0, 12))}…</td>
    </tr>`).join("")}</tbody></table>`;
  } catch (e) { setError("ledger-preview", "Failed to load ledger.", renderLedgerView); }
}

async function ledgerVerify() {
  try {
    const result = await api("/ledger/verify");
    const isValid = result.valid || result.is_valid;
    toast(isValid ? "Ledger integrity verified" : "Ledger TAMPERED", isValid ? "success" : "error");
    renderLedgerView();
  } catch (e) { toast("Verification failed", "error"); }
}

async function ledgerTamper() {
  if (!confirm("This will demonstrate a tamper event on the audit chain. Continue?")) return;
  try {
    await api("/ledger/tamper-demo", { method: "POST" });
    toast("Tamper demo applied — integrity check will fail", "warning");
    renderLedgerView();
  } catch (e) { toast("Tamper demo failed", "error"); }
}

async function ledgerRestore() {
  try {
    await api("/ledger/restore", { method: "POST" });
    toast("Ledger restored — integrity verified", "success");
    renderLedgerView();
  } catch (e) { toast("Restore failed", "error"); }
}

/* ==================== MODEL HEALTH ==================== */
async function renderModelView() {
  const gridEl = document.getElementById("model-health-grid");
  const metricsEl = document.getElementById("model-metrics");
  const driftEl = document.getElementById("drift-panel");

  if (gridEl) {
    try {
      const data = await api("/train/status");
      const m = data.metrics || {};
      gridEl.innerHTML = `
        <div class="model-check ${data.status === 'ok' ? 'check-ok' : 'check-pending'}">
          <div class="check-label">Training Status</div>
          <div class="check-value">${esc(data.status)}</div>
        </div>
        <div class="model-check check-ok">
          <div class="check-label">Leakage Audit</div>
          <div class="check-value">PASSED</div>
          <div class="check-detail">Same-day leakage fixed</div>
        </div>
        <div class="model-check check-ok">
          <div class="check-label">Data Source</div>
          <div class="check-value">Synthetic</div>
          <div class="check-detail">I4C-calibrated patterns</div>
        </div>`;
    } catch (e) { gridEl.innerHTML = '<p class="text-muted">Model status unavailable.</p>'; }
  }

  if (metricsEl) {
    metricsEl.innerHTML = `<div class="metrics-grid">
      <div class="metric-row"><span>ROC-AUC</span><span class="metric-value">0.6456</span></div>
      <div class="metric-row"><span>Precision@20</span><span class="metric-value">0.70</span></div>
      <div class="metric-row"><span>Precision@50</span><span class="metric-value">0.70</span></div>
      <div class="metric-row"><span>Precision@100</span><span class="metric-value">0.67</span></div>
      <div class="metric-row"><span>Brier Score</span><span class="metric-value">0.0467</span></div>
      <div class="metric-row"><span>Features</span><span class="metric-value">44</span></div>
      <div class="metric-row"><span>Lift vs Random @P100</span><span class="metric-value">7.9×</span></div>
      <div class="metric-row"><span>Median Lead Time</span><span class="metric-value">12.8h</span></div>
    </div>
    <p class="text-xs text-muted" style="margin-top:12px">Source: CURRENT_METRICS.md — Synthetic demonstration data. No real-world performance claimed.</p>`;
  }

  if (driftEl) {
    try {
      const d = await api("/drift/status");
      const stateClass = d.status === "green" ? "drift-green" : d.status === "yellow" ? "drift-yellow" : "drift-red";
      driftEl.innerHTML = `<div class="drift-status ${stateClass}">
        <span class="drift-dot"></span> ${esc(d.status.toUpperCase())}
      </div>
      <div class="drift-detail">
        <p>${esc(d.summary?.verdict || "Status unknown")}</p>
        ${d.n_flagged > 0 ? `<p class="text-danger">${d.n_flagged} features flagged</p>` : ""}
      </div>`;
    } catch (e) { driftEl.innerHTML = '<p class="text-muted">Drift status unavailable.</p>'; }
  }
}

/* ==================== REPORTS ==================== */
function renderReportsView() {
  const el = document.getElementById("reports-panel");
  if (!el) return;
  el.innerHTML = `
    <div class="reports-grid">
      <div class="report-card">
        <h4>${icon("file")} Situational Intelligence Report</h4>
        <p class="text-muted">National situational overview with risk distribution and recommendations.</p>
        <button class="btn btn-primary" onclick="generateSituationalReport()">${icon("download")} Generate PDF</button>
      </div>
      <div class="report-card">
        <h4>${icon("target")} Hotspot Report</h4>
        <p class="text-muted">Detailed analysis of current high-risk ATM locations.</p>
        <button class="btn btn-ghost" onclick="generateSituationalReport()">${icon("download")} Generate PDF</button>
      </div>
    </div>
    <div id="reports-output" class="reports-output"></div>`;
}

async function generateSituationalReport() {
  const el = document.getElementById("reports-output");
  if (el) el.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Generating report...</p></div>';
  try {
    const result = await api("/reports/situational", { method: "POST" });
    if (el) el.innerHTML = `<div class="report-result">
      <p>Report generated successfully.</p>
      <a href="/reports/${result.report_id}/download" target="_blank" class="btn btn-primary">${icon("download")} Download PDF</a>
    </div>`;
    toast("Report generated", "success");
  } catch (e) {
    if (el) el.innerHTML = '<p class="text-muted">Report generation unavailable.</p>';
    toast("Report generation failed", "error");
  }
}

/* ==================== THRESHOLD EXPLORER ==================== */
let THR_CURVE = null;
async function loadThresholdCurve() {
  try { THR_CURVE = await api("/threshold-explorer"); } catch { /* ignore */ }
}

function applyThresholdCurve() {
  const slider = document.getElementById("thr-slider");
  const valueEl = document.getElementById("thr-value");
  const metricsEl = document.getElementById("thr-metrics");
  if (!slider || !THR_CURVE) return;
  const val = parseInt(slider.value);
  if (valueEl) valueEl.textContent = val + "%";
  if (metricsEl && THR_CURVE.curve) {
    const point = THR_CURVE.curve.find(c => Math.round(c.threshold * 100) === val) || {};
    metricsEl.innerHTML = `<span>P: ${fmtMetric(point.precision, 3)}</span> <span>Vol: ${fmtMetric(point.alert_volume, 0)}</span>`;
  }
}

/* ==================== DATA LOADING ==================== */
async function loadCityCoords() {
  try {
    const atms = await api("/atms?limit=900");
    const coords = {};
    const stateSet = new Set();
    const citySet = new Set();
    const bankSet = new Set();
    atms.forEach(a => {
      if (a.latitude && a.longitude) {
        if (!coords[a.city]) coords[a.city] = { lat: 0, lon: 0, count: 0 };
        coords[a.city].lat += a.latitude;
        coords[a.city].lon += a.longitude;
        coords[a.city].count++;
      }
      stateSet.add(a.state);
      citySet.add(a.city);
      bankSet.add(a.bank_name);
    });
    Object.keys(coords).forEach(c => {
      coords[c].lat /= coords[c].count;
      coords[c].lon /= coords[c].count;
    });
    state.cityCoords = coords;
    populateDropdowns([...stateSet].sort(), [...citySet].sort(), [...bankSet].sort());
  } catch (e) { console.warn("City coords load failed:", e); }
}

function populateDropdowns(states, cities, banks) {
  const ddState = document.getElementById("dd-state");
  const ddCity = document.getElementById("dd-city");
  const ddBank = document.getElementById("dd-bank");
  if (ddState) ddState.innerHTML = '<option value="All">All States</option>' + states.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join("");
  if (ddCity) ddCity.innerHTML = '<option value="All">All Cities</option>' + cities.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
  if (ddBank) ddBank.innerHTML = '<option value="All">All Banks</option>' + banks.map(b => `<option value="${esc(b)}">${esc(b)}</option>`).join("");
}

async function loadComplaints() {
  try {
    const now = new Date();
    const weekAgo = new Date(now - 7 * 86400000).toISOString().slice(0, 10);
    state.complaints = await api(`/complaints?date_from=${weekAgo}&limit=200`);
  } catch { state.complaints = []; }
}

async function renderHorizonConfidence() {
  const el = document.getElementById("horizon-confidence");
  if (!el) return;
  try {
    const data = await api("/horizons");
    const h = data["horizon_" + state.horizon + "h"] || data["horizon_" + state.horizon] || {};
    el.textContent = h.precision ? `P@20: ${fmtMetric(h.precision, 2)}` : "";
  } catch { el.textContent = ""; }
}

async function loadAll() {
  state._loadGen++;
  const gen = state._loadGen;
  invalidateRiskCache();

  if (state.simulatedOptedIn) {
    try {
      const data = await api("/simulated/scenario");
      state.risk = data.risk_scores || [];
      state.alerts = data.alerts || [];
      state.stats = data.stats || state.stats;
    } catch (e) { toast("Failed to load scenario", "error"); return; }
  } else {
    try {
      const params = new URLSearchParams();
      if (state.horizon) params.set("horizon", state.horizon);
      const [risk, alerts] = await Promise.all([
        api("/risk-scores?" + params.toString()),
        api("/alerts?limit=200"),
      ]);
      if (gen !== state._loadGen) return;
      state.risk = risk;
      state.alerts = alerts;
    } catch (e) { console.warn("Data load failed:", e); }

    try {
      const s = await api("/stats/summary");
      if (gen === state._loadGen) state.stats = s;
    } catch { /* ignore */ }
  }

  render();
  updateAlertBadge();
}

function render() {
  if (state.user) {
    const nameEl = document.getElementById("user-display-name");
    const roleEl = document.getElementById("user-role-text");
    const avatarEl = document.getElementById("user-avatar");
    if (nameEl) nameEl.textContent = state.user.display_name || state.user.username;
    if (roleEl) roleEl.textContent = state.user.role.replace("_", " ");
    if (avatarEl) avatarEl.textContent = (state.user.username || "?")[0].toUpperCase();
  }

  const asOfPill = document.getElementById("as-of-pill");
  const scopePill = document.getElementById("scope-pill");
  if (asOfPill) asOfPill.textContent = state.asOf ? fmtTime(state.asOf) : "Live";
  if (scopePill) scopePill.textContent = state.user ? state.user.scope || "National" : "";

  updateSidebarForRole(state.user?.role);

  renderOverviewStats();
  renderPriorityActions();

  if (state.currentView === "overview") {
    renderMainMap();
    renderAlertTable("alert-table", (state.alerts || []).slice(0, 10));
    renderHotspotTable();
  }
}

/* ==================== SIMULATION ==================== */
function setSimulationUI(active) {
  state.simulatedOptedIn = active;
  const banner = document.getElementById("sim-banner");
  const watermark = document.getElementById("sim-watermark");
  const loadBtn = document.getElementById("btn-sim-load");
  const exitBtn = document.getElementById("btn-sim-exit");
  if (banner) banner.classList.toggle("hidden", !active);
  if (watermark) watermark.classList.toggle("hidden", !active);
  if (loadBtn) loadBtn.classList.toggle("hidden", active);
  if (exitBtn) exitBtn.classList.toggle("hidden", !active);
}

async function loadSimulatedScenario() {
  toast("Loading simulated scenario...", "info");
  state.simulatedOptedIn = true;
  setSimulationUI(true);
  await loadAll();
  toast("Simulated scenario loaded", "success");
}

function exitSimulated() {
  state.simulatedOptedIn = false;
  state.simulatedEvidence = {};
  setSimulationUI(false);
  loadAll();
  toast("Exited simulation mode", "info");
}

/* ==================== ALERT CYCLE ==================== */
async function runAlertCycle() {
  const btn = document.getElementById("btn-cycle");
  if (btn) { btn.disabled = true; btn.textContent = "Running..."; }
  try {
    toast("Running alert cycle...", "info");
    const r = await api("/alerts/run-now", { method: "POST" });
    const s = r.summary || {};
    toast(`Alert cycle: ${s.created || 0} new · ${s.flagged || 0} flagged · ${s.skipped || 0} deduped`, "success");
    const alerts = await api("/alerts?limit=200").catch(() => state.alerts);
    state.alerts = alerts;
    renderAlertTable("alert-table", (state.alerts || []).slice(0, 10));
    renderOverviewStats();
    updateAlertBadge();
  } catch (e) { toast("Alert cycle failed: " + e.message, "error"); }
  finally { if (btn) { btn.disabled = false; btn.textContent = icon("play") + " Run Cycle"; } }
}

/* ==================== WEBSOCKET ==================== */
let _wsReconnectTimer = null;
function connectWS() {
  try {
    if (_wsReconnectTimer) { clearTimeout(_wsReconnectTimer); _wsReconnectTimer = null; }
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/alerts?token=${encodeURIComponent(getToken())}`);
    ws._retries = 0;
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (state.simulatedOptedIn) return;
        if (msg.event === "alert") {
          toast(`LIVE: ${msg.payload.atm_id} flagged ${riskPct(msg.payload.risk_score)}`, "warning");
          const existing = state.alerts.findIndex(a => a.alert_id === msg.payload.alert_id);
          if (existing >= 0) { state.alerts[existing] = msg.payload; } else { state.alerts.unshift(msg.payload); }
          if (state.currentView === "overview") renderAlertTable("alert-table", (state.alerts || []).slice(0, 10));
          if (state.currentView === "alerts") renderAlertTable("alerts-full-table", state.alerts);
          renderOverviewStats();
          updateAlertBadge();
        } else if (msg.event === "recovery" || msg.event === "recovery_status") {
          if (state.currentView === "recovery") renderRecoveryView();
        }
      } catch { /* ignore */ }
    };
    ws.onclose = () => {
      const delay = Math.min(30000, 2000 * Math.pow(2, ws._retries || 0));
      ws._retries = ((ws._retries || 0) + 1);
      _wsReconnectTimer = setTimeout(connectWS, delay);
    };
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
  const username = userEl ? userEl.value.trim() : "";
  const password = passEl ? passEl.value : "";
  if (!username || !password) { loginStatus("Enter both username and password.", "error"); return; }
  loginStatus("Authenticating...", "");
  try {
    const data = await api("/auth/login", { method: "POST", body: { username, password } });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    state.user = data.user;
    hideLogin();
    connectWS();
    await loadAll();
    await loadCityCoords();
    await loadThresholdCurve();
    loginStatus("Ready — select a demo role to sign in.");
  } catch (e) {
    loginStatus("Authentication failed. Check credentials.", "error");
  }
}

function autofillDemo(u, p) {
  const userEl = document.getElementById("login-username");
  const passEl = document.getElementById("login-password");
  if (userEl) userEl.value = u;
  if (passEl) passEl.value = p;
  doLogin();
}

/* ==================== I18N ==================== */
const i18n = { locales: [], strings: {}, lang: "en" };

async function initI18n() {
  try {
    const data = await api("/i18n/locales");
    i18n.locales = data.locales || [];
    const sel = document.getElementById("i18n-select");
    if (sel) {
      sel.innerHTML = i18n.locales.map(l => `<option value="${esc(l.code)}">${esc(l.name)}</option>`).join("");
      const saved = localStorage.getItem("cashguard_lang") || data.default || "en";
      sel.value = saved;
      i18n.lang = saved;
      await setI18nLang(saved);
    }
  } catch { /* ignore */ }
}

async function setI18nLang(lang) {
  try {
    const data = await api(`/i18n/strings?lang=${encodeURIComponent(lang)}`);
    i18n.strings = data.strings || {};
    i18n.lang = lang;
    localStorage.setItem("cashguard_lang", lang);
    applyI18n();
  } catch { /* ignore */ }
}

function applyI18n() {
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.dataset.i18n;
    if (i18n.strings[key]) el.textContent = i18n.strings[key];
  });
  document.querySelectorAll("[data-i18n-title]").forEach(el => {
    const key = el.dataset.i18nTitle;
    if (i18n.strings[key]) el.title = i18n.strings[key];
  });
}

/* ==================== SIDEBAR TOGGLE ==================== */
function toggleSidebar() {
  state.sidebarCollapsed = !state.sidebarCollapsed;
  const sidebar = document.getElementById("sidebar");
  if (sidebar) sidebar.classList.toggle("collapsed", state.sidebarCollapsed);
  setTimeout(() => {
    if (window._mainMap) window._mainMap.invalidateSize();
    if (window._riskMap) window._riskMap.invalidateSize();
  }, 300);
}

/* ==================== EVENT BINDINGS ==================== */
function bindEvents() {
  const wire = (id, fn) => { const el = document.getElementById(id); if (el) el.addEventListener("click", fn); };

  wire("btn-login", doLogin);
  wire("btn-refresh", loadAll);
  wire("btn-cycle", runAlertCycle);
  wire("btn-sim-load", loadSimulatedScenario);
  wire("btn-sim-exit", exitSimulated);
  wire("btn-sim-banner-exit", exitSimulated);
  wire("btn-ledger-verify", ledgerVerify);
  wire("btn-ledger-tamper", ledgerTamper);
  wire("btn-ledger-restore", ledgerRestore);
  wire("btn-sit-report", generateSituationalReport);
  wire("btn-evaluate-outcomes", async () => {
    try { await api("/alerts/outcomes/evaluate", { method: "POST" }); toast("Outcomes evaluated", "success"); renderRecoveryView(); }
    catch (e) { toast("Evaluation failed", "error"); }
  });
  wire("btn-mobile-locate", () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        pos => renderMobile(pos.coords.latitude, pos.coords.longitude),
        () => renderMobile(22.66, 74.55)
      );
    } else { renderMobile(22.66, 74.55); }
  });
  wire("btn-switch", () => { localStorage.removeItem(TOKEN_KEY); state.user = null; showLogin(); });
  wire("ev-close", () => { document.getElementById("evidence-modal")?.classList.add("hidden"); });
  wire("btn-replay", () => { state.asOf = document.getElementById("asof-date")?.value || null; loadAll(); });
  wire("btn-live", () => { state.asOf = null; loadAll(); });
  wire("sidebar-toggle", toggleSidebar);

  const loginPass = document.getElementById("login-password");
  if (loginPass) loginPass.addEventListener("keydown", (e) => { if (e.key === "Enter") doLogin(); });

  const evModal = document.getElementById("evidence-modal");
  if (evModal) evModal.addEventListener("click", (e) => { if (e.target.id === "evidence-modal") evModal.classList.add("hidden"); });

  const drawerOverlay = document.getElementById("drawer-overlay");
  if (drawerOverlay) drawerOverlay.addEventListener("click", (e) => { if (e.target.id === "drawer-overlay") closeDrawer(); });

  document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("click", () => { const v = item.dataset.view; if (v) switchView(v); });
  });

  const ddState = document.getElementById("dd-state");
  const ddCity = document.getElementById("dd-city");
  const ddBank = document.getElementById("dd-bank");
  const thrSlider = document.getElementById("thr-slider");

  if (ddState) ddState.addEventListener("change", (e) => {
    state.stateFilter = e.target.value;
    state.cityFilter = "All";
    invalidateRiskCache();
    debounce(loadAll, 300)();
  });
  if (ddCity) ddCity.addEventListener("change", (e) => {
    state.cityFilter = e.target.value;
    invalidateRiskCache();
    debounce(loadAll, 300)();
  });
  if (ddBank) ddBank.addEventListener("change", (e) => {
    state.bankFilter = e.target.value;
    invalidateRiskCache();
    if (state.currentView === "overview") renderMainMap();
    if (state.currentView === "risk" && window._riskMap) renderRiskIntelligence();
  });
  if (thrSlider) thrSlider.addEventListener("input", applyThresholdCurve);

  const tHeat = document.getElementById("toggle-heat");
  const tForecast = document.getElementById("toggle-forecast");
  if (tHeat) tHeat.addEventListener("change", (e) => { state.showHeat = e.target.checked; if (state.currentView === "overview") renderMainMap(); });
  if (tForecast) tForecast.addEventListener("change", (e) => { state.showForecast = e.target.checked; if (state.currentView === "overview") renderMainMap(); });

  const chipBox = document.getElementById("category-chips");
  if (chipBox) {
    chipBox.innerHTML = '<button class="chip active" data-cat="All">All</button>' +
      COMPLAINT_TYPES.map(c => `<button class="chip" data-cat="${esc(c)}">${esc(c.replace(/_/g, " "))}</button>`).join("");
    chipBox.querySelectorAll(".chip").forEach(el => {
      el.addEventListener("click", () => {
        chipBox.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
        el.classList.add("active");
        state.category = el.dataset.cat;
        invalidateRiskCache();
        if (state.currentView === "overview") renderMainMap();
      });
    });
  }

  const i18nSel = document.getElementById("i18n-select");
  if (i18nSel) i18nSel.addEventListener("change", () => setI18nLang(i18nSel.value));
}

/* ==================== REPORTS (from drawer/evidence) ==================== */
async function hotspotReport(alertId) {
  try {
    toast("Generating report...", "info");
    const result = await api(`/reports/hotspot/${alertId}`, { method: "POST" });
    if (result.pdf) { toast("Report generated", "success"); window.open(`/reports/${result.report_id}/download`, "_blank"); }
  } catch (e) { toast("Report generation failed", "error"); }
}

async function renderMobile(lat, lon) {
  const el = document.getElementById("mobile-nearby");
  if (!el) return;
  try {
    const data = await api(`/mobile/nearby?lat=${lat}&lon=${lon}&max_km=50&limit=5`);
    if (!data.atms || data.atms.length === 0) { el.innerHTML = '<p class="text-muted">No nearby ATMs found.</p>'; return; }
    el.innerHTML = `<table class="data-table"><thead><tr><th>ATM</th><th>Distance</th><th>Risk</th></tr></thead><tbody>
      ${data.atms.map(a => `<tr><td class="mono">${esc(a.atm_id)}</td><td>${fmtMetric(a.distance_km, 1)} km</td><td>${riskPill(a.risk_score)}</td></tr>`).join("")}
    </tbody></table>`;
  } catch { el.innerHTML = '<p class="text-muted">Nearby ATMs unavailable.</p>'; }
}

/* ==================== BOOT ==================== */
window.cashguardLogin = doLogin;
window.autofillDemo = autofillDemo;
window.focusAtmFromOverview = focusAtmFromOverview;
window.focusRiskAtm = focusRiskAtm;
window.setAlertStatus = setAlertStatus;
window.escalateAlert = escalateAlert;
window.dismissAlert = dismissAlert;
window.handoffAck = handoffAck;
window.updateRecovery = updateRecovery;
window.loadMuleTrail = loadMuleTrail;
window.ledgerVerify = ledgerVerify;
window.ledgerTamper = ledgerTamper;
window.ledgerRestore = ledgerRestore;
window.generateSituationalReport = generateSituationalReport;
window.hotspotReport = hotspotReport;
window.closeDrawer = closeDrawer;
window.drawerAction = drawerAction;
window.drawerActionEscalate = drawerActionEscalate;
window.drawerGenerateReport = drawerGenerateReport;

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  initI18n();
  localStorage.removeItem("cashguard_role");
  window.__cashguardReady = true;
  const token = getToken();
  if (token) {
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      state.user = { username: payload.sub, role: payload.role, scope: payload.scope, display_name: payload.sub };
    } catch { /* ignore */ }
    connectWS();
    loadAll().then(() => {
      loadCityCoords();
      loadThresholdCurve();
    });
    hideLogin();
  } else {
    showLogin();
  }
});
