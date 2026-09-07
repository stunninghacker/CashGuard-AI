/* CashGuard AI — Frontend Application v4.0 (command center)
   Contract notes (do not regress):
   - WS: connect with ?token=, parse {event, payload}; single-path reconnect.
   - /ledger/verify returns `intact` (not `valid`).
   - /stats/summary returns `alerts_total`.
   - /risk-scores accepts only city/as_of/horizon — state/bank filters are client-side.
   - Alert status transitions: acknowledged|actioned|dismissed|escalated|monitoring|review_requested.
   - Recovery statuses: freeze_requested|held|recovered.
   - Evidence endpoint returns the full EvidenceOut (summary, activity, uncertainty, SHAP).
   All metrics stay exactly as reported by the API — nothing is rounded up or invented. */
"use strict";

const State = {
  token: localStorage.getItem("cg_token") || null,
  user: JSON.parse(localStorage.getItem("cg_user") || "null"),
  view: "overview",
  sidebarCollapsed: false,
  simulation: false,
  simulationData: null,
  replay: false,
  replayDay: null,
  replayData: null,
  riskScores: [],
  alerts: [],
  stats: null,
  recovery: [],
  ledger: { entries: [], total: 0, page: 0 },
  muleNetwork: null,
  ws: null,
  feedSeen: {},   // alert_id -> true (already shown a feed card this session)
};

const API = {
  BASE: "",
  async req(method, path, body) {
    const h = { "Content-Type": "application/json" };
    if (State.token) h["Authorization"] = "Bearer " + State.token;
    const opts = { method, headers: h };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(this.BASE + path, opts);
    if (res.status === 401) { Auth.logout(); throw new Error("Session expired"); }
    if (res.status === 403) return { _forbidden: true, _status: 403 };
    if (!res.ok) throw new Error("HTTP " + res.status);
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("json")) return res.json();
    if (ct.includes("pdf")) return res.blob();
    return res.text();
  },
  get(p) { return this.req("GET", p); },
  post(p, b) { return this.req("POST", p, b); },
};

const Auth = {
  async login(u, p) {
    const d = await API.req("POST", "/auth/login", { username: u, password: p });
    State.token = d.access_token; State.user = d.user;
    localStorage.setItem("cg_token", d.access_token);
    localStorage.setItem("cg_user", JSON.stringify(d.user));
    return d;
  },
  logout() {
    State.token = null; State.user = null;
    localStorage.removeItem("cg_token"); localStorage.removeItem("cg_user");
    if (State.ws) { State.ws.onclose = null; try { State.ws.close(); } catch (e) {} State.ws = null; }
    $("login-page").style.display = "flex";
    $("app-shell").classList.remove("active");
  },
  role() { return State.user?.role || ""; },
  canAccess(v) {
    const r = this.role();
    if (r === "I4C_ADMIN") return true;
    const m = {
      overview: true, risk: true, alerts: true,
      recovery: r === "BANK",
      investigations: ["POLICE_STATE","POLICE_DISTRICT","I4C_ADMIN"].includes(r),
      "mule-network": true,
      "model-health": ["POLICE_STATE","POLICE_DISTRICT","I4C_ADMIN"].includes(r),
      ledger: r !== "BANK", reports: true,
    };
    return m[v] === true;
  }
};

/* ── Helpers ───────────────────────────────────────────────── */
function $(id) { return document.getElementById(id); }
function esc(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
function shortId(id) { return id ? id.slice(-8) : "--"; }
function fmtDate(iso) {
  if (!iso) return "--";
  var d = new Date(iso);
  if (isNaN(d)) return "--";
  return d.toLocaleDateString("en-IN",{day:"2-digit",month:"short"}) + " " +
         d.toLocaleTimeString("en-IN",{hour:"2-digit",minute:"2-digit",hour12:false});
}
function fmtNum(n) { return n != null && !isNaN(n) ? Number(n).toLocaleString("en-IN") : "--"; }

/* Risk levels are ALWAYS color + icon + label — never color alone (a11y). */
var RISK_LEVELS = {
  LOW:      { ico: "○", word: "LOW",      cls: "lvl-low" },
  MEDIUM:   { ico: "◎", word: "MEDIUM",   cls: "lvl-medium" },
  HIGH:     { ico: "▲", word: "HIGH",     cls: "lvl-high" },
  CRITICAL: { ico: "●", word: "CRITICAL", cls: "lvl-critical" },
};
function levelOf(score) {
  return score >= 0.85 ? "CRITICAL" : score >= 0.7 ? "HIGH" : score >= 0.4 ? "MEDIUM" : "LOW";
}
function riskChip(score, withWord) {
  if (score == null || isNaN(score)) return '<span class="risk-chip lvl-low"><span class="lvl-ico">○</span>--</span>';
  var lvl = levelOf(score), meta = RISK_LEVELS[lvl];
  return '<span class="risk-chip ' + meta.cls + '" aria-label="' + meta.word + ' risk ' + (score*100).toFixed(1) + ' percent">' +
    '<span class="lvl-ico" aria-hidden="true">' + meta.ico + '</span>' + (score*100).toFixed(1) + '%' +
    (withWord ? ' <span class="lvl-word">' + meta.word + '</span>' : '') + '</span>';
}
function levelChip(lvl) {
  var meta = RISK_LEVELS[lvl] || { ico: "○", word: lvl || "LOW", cls: "lvl-low" };
  return '<span class="risk-chip ' + meta.cls + '"><span class="lvl-ico" aria-hidden="true">' + meta.ico + '</span><span class="lvl-word">' + esc(meta.word) + '</span></span>';
}
function statusChip(s) {
  var m = {
    new:"chip-critical", acknowledged:"chip-high", actioned:"chip-medium",
    monitoring:"chip-info", review_requested:"chip-info", escalated:"chip-critical",
    dismissed:"chip-info",
    freeze_requested:"chip-critical", held:"chip-high", recovered:"chip-low",
    flagged:"chip-critical", recovery_failed:"chip-critical",
  };
  var label = String(s || "--").replace(/_/g, " ");
  return '<span class="chip ' + (m[s] || "chip-info") + '">' + esc(label) + '</span>';
}
function tierChip(t) {
  var m = {dispatch:"dispatch",action:"action",monitor:"monitor"};
  return '<span class="alert-tier ' + (m[t]||"monitor") + '">' + esc(t||"monitor") + '</span>';
}
/* mobile card reflow: give every td a data-th label */
function td(val, th, extraCls) {
  return '<td data-th="' + esc(th) + '"' + (extraCls ? ' class="' + extraCls + '"' : '') + '>' + val + '</td>';
}

var SKEL = {
  stat: '<div class="skeleton skeleton-stat"></div>',
  row: '<div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div>',
  table: function(n){ var h=''; for(var i=0;i<(n||5);i++) h+='<div class="skeleton skeleton-row"></div>'; return h; },
  show: function(id, type){ var el=$(id); if(el) el.innerHTML=SKEL[type]||SKEL.row; },
};
function emptyState(icon, title, desc, actionHtml) {
  return '<div class="empty-state"><div class="empty-icon"><span class="lucide lucide-' + icon + '"></span></div>' +
    '<div class="empty-title">' + esc(title) + '</div>' +
    (desc ? '<div class="empty-desc">' + esc(desc) + '</div>' : '') +
    (actionHtml ? '<div class="empty-action">' + actionHtml + '</div>' : '') + '</div>';
}
async function withLoading(btnId, fn) {
  var btn = typeof btnId==="string" ? $(btnId) : btnId;
  if(btn){ btn.disabled=true; btn.dataset.origText=btn.textContent; btn.classList.add("loading"); }
  try { return await fn(); }
  finally { if(btn){ btn.disabled=false; btn.textContent=btn.dataset.origText||btn.textContent; btn.classList.remove("loading"); } }
}

/* ── Toast ─────────────────────────────────────────────────── */
const Toast = {
  _max: 5,
  show(title, msg, type, dur) {
    type = type || "info"; dur = dur || 4000;
    const c = $("toast-container");
    const icons = { success: "check-circle", error: "x-circle", warning: "alert-triangle", info: "info" };
    while (c.children.length >= this._max) { c.firstChild.remove(); }
    const el = document.createElement("div");
    el.className = "toast " + type;
    el.innerHTML = '<span class="toast-icon"><span class="lucide lucide-' + (icons[type]||icons.info) + '"></span></span>' +
      '<div class="toast-content"><div class="toast-title">' + esc(title) + '</div>' +
      '<div class="toast-message">' + esc(msg) + '</div></div>' +
      '<button class="toast-close" aria-label="Dismiss">&times;</button>';
    el.querySelector(".toast-close").onclick = function() { rm(); };
    c.appendChild(el);
    var timer = setTimeout(rm, dur);
    function rm() { clearTimeout(timer); el.classList.add("removing"); setTimeout(function(){ el.remove(); }, 200); }
  },
  success(t, m) { this.show(t, m, "success"); },
  error(t, m) { this.show(t, m, "error", 6000); },
  warning(t, m) { this.show(t, m, "warning", 5000); },
  info(t, m) { this.show(t, m, "info"); },
};

/* ── Modal / Drawer ────────────────────────────────────────── */
const Modal = {
  _prevFocus: null,
  show(cfg) {
    this._prevFocus = document.activeElement;
    $("modal-title").textContent = cfg.title || "Confirm";
    $("modal-body").innerHTML = cfg.body || "";
    $("modal-footer").innerHTML = cfg.footer || "";
    $("modal-overlay").classList.add("active");
    $("modal-close").onclick = function() { Modal.hide(); };
    $("modal-overlay").onclick = function(e) { if (e.target.id === "modal-overlay") Modal.hide(); };
    var closeBtn = $("modal-close");
    if (closeBtn) closeBtn.focus();
  },
  hide() {
    $("modal-overlay").classList.remove("active");
    if (this._prevFocus) try { this._prevFocus.focus(); } catch(e) {}
  },
  confirm(title, msg) {
    return new Promise(function(resolve) {
      var id = "mc-" + Date.now();
      Modal.show({
        title: title,
        body: '<p style="color:var(--text-secondary);line-height:1.6">' + esc(msg) + '</p>',
        footer: '<button class="btn btn-secondary btn-sm" id="' + id + '-no">Cancel</button>' +
                '<button class="btn btn-primary btn-sm" id="' + id + '-yes">Confirm</button>',
      });
      $(id + "-no").onclick = function() { Modal.hide(); resolve(false); };
      $(id + "-yes").onclick = function() { Modal.hide(); resolve(true); };
    });
  }
};
const Drawer = {
  _prevFocus: null,
  open(cfg) {
    this._prevFocus = document.activeElement;
    $("drawer-title").textContent = cfg.title || "Details";
    $("drawer-body").innerHTML = cfg.body || "";
    $("drawer-footer").innerHTML = cfg.footer || "";
    $("drawer-overlay").classList.add("active");
    $("drawer").classList.add("open");
    var closeBtn = $("drawer-close");
    if (closeBtn) closeBtn.focus();
  },
  close() {
    $("drawer-overlay").classList.remove("active");
    $("drawer").classList.remove("open");
    if (this._prevFocus) try { this._prevFocus.focus(); } catch(e) {}
  }
};

/* ── Navigation ────────────────────────────────────────────── */
function switchView(view) {
  if (!Auth.canAccess(view)) {
    Toast.warning("Access Denied", "Your role ("+Auth.role()+") cannot access this section.");
    return;
  }
  State.view = view;
  document.querySelectorAll(".workspace-view").forEach(function(v) { v.classList.remove("active"); });
  document.querySelectorAll(".nav-item[data-view]").forEach(function(n) { n.classList.remove("active"); });
  var ve = $("view-" + view);
  var ne = document.querySelector('.nav-item[data-view="'+view+'"]');
  if (ve) ve.classList.add("active");
  if (ne) ne.classList.add("active");
  var titles = {overview:"Overview",risk:"Risk Intelligence",alerts:"Alert Operations",
    recovery:"Recovery Center",investigations:"Investigations","mule-network":"Mule Network",
    "model-health":"Model Health",ledger:"Audit Trail",reports:"Reports"};
  $("breadcrumb").innerHTML = "<strong>" + esc(titles[view]||view) + "</strong>";
  switch(view) {
    case "overview": Overview.load(); break;
    case "risk": Risk.load(); break;
    case "alerts": Alerts.load(); break;
    case "recovery": Recovery.load(); break;
    case "investigations": Investigations.load(); break;
    case "mule-network": MuleNetwork.load(); break;
    case "model-health": ModelHealth.load(); break;
    case "ledger": Ledger.load(); break;
    case "reports": Reports.load(); break;
  }
}

/* ── MapController — keyless dark basemap + risk-matched heat ── */
function MapCtrl(containerId, opts) {
  this.containerId = containerId;
  this.map = null;
  this.markers = [];
  this.opts = Object.assign({ center: [22.5, 80], zoom: 5, minZoom: 3, maxZoom: 18 }, opts || {});
}
MapCtrl.prototype.init = function() {
  var el = $(this.containerId);
  if (!el) return;
  if (this.map) { this.map.remove(); this.map = null; }
  el.innerHTML = "";
  try {
    this.map = L.map(this.containerId, {
      center: this.opts.center, zoom: this.opts.zoom,
      minZoom: this.opts.minZoom, maxZoom: this.opts.maxZoom,
    });
    // Esri World Dark Gray Canvas — keyless, dark, command-center friendly.
    // (CARTO's dark tiles now render "API KEY REQUIRED" watermarks.)
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
      attribution: "Tiles &copy; Esri — Source: USGS, Esri, TANA, Garmin", maxZoom: 16,
    }).addTo(this.map);
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 16, opacity: 0.7,
    }).addTo(this.map);
  } catch(e) {
    el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted)">Map unavailable — markers and data below remain live.</div>';
  }
};
MapCtrl.prototype.riskColor = function(score) {
  return score >= 0.85 ? "#FF4757" : score >= 0.7 ? "#FF7A45" : score >= 0.4 ? "#FFB454" : "#2EE6A6";
};
MapCtrl.prototype.clearMarkers = function() {
  var self = this;
  this.markers.forEach(function(m) { if (self.map) self.map.removeLayer(m); });
  this.markers = [];
  if (this._heatLayer && this.map) { this.map.removeLayer(this._heatLayer); this._heatLayer = null; }
};
MapCtrl.prototype.addMarker = function(lat, lng, opts) {
  if (!this.map || lat == null || lng == null) return null;
  opts = opts || {};
  var score = opts.risk || 0;
  var lvl = levelOf(score);
  var color = this.riskColor(score);
  var radius = lvl === "CRITICAL" ? 11 : lvl === "HIGH" ? 9 : lvl === "MEDIUM" ? 7 : 5;
  var m = L.circleMarker([lat, lng], {
    radius: radius, fillColor: color, fillOpacity: 0.85,
    color: color, weight: 2, opacity: 0.9,
  }).addTo(this.map);
  if (opts.popup) m.bindPopup(opts.popup, { maxWidth: 300 });
  this.markers.push(m);
  return m;
};
MapCtrl.prototype.fitBounds = function(data) {
  if (!this.map || !data.length) return;
  var valid = data.filter(function(d) { return d.latitude && d.longitude; });
  if (!valid.length) return;
  this.map.fitBounds(L.latLngBounds(valid.map(function(d) { return [d.latitude, d.longitude]; })), { padding: [40, 40] });
};
MapCtrl.prototype.resize = function() {
  var self = this;
  setTimeout(function() { if (self.map) self.map.invalidateSize(); }, 100);
};
MapCtrl.prototype.addHeat = function(data) {
  if (!this.map || !data.length || !L.heatLayer) return;
  if (this._heatLayer) { this.map.removeLayer(this._heatLayer); this._heatLayer = null; }
  var hd = data.filter(function(d){return d.latitude&&d.longitude;}).map(function(d){return [d.latitude,d.longitude,Math.min(1,Math.max(0,d.risk_score||0))];});
  if (hd.length) {
    this._heatLayer = L.heatLayer(hd, {radius:26,blur:16,maxZoom:11,max:1.0,
      gradient:{0.1:"#2EE6A6",0.4:"#FFB454",0.7:"#FF7A45",0.85:"#FF4757",1.0:"#FF1F3D"}
    }).addTo(this.map);
  }
};

/* ── WebSocket — authenticated, correct shape, single reconnect ── */
function connectWS() {
  if (State.ws) {
    State.ws.onopen = State.ws.onmessage = State.ws.onclose = State.ws.onerror = null;
    try { State.ws.close(); } catch(e) {}
  }
  var proto = location.protocol === "https:" ? "wss" : "ws";
  try {
    var sock = new WebSocket(proto + "://" + location.host + "/ws/alerts?token=" + encodeURIComponent(State.token || ""));
    State.ws = sock;
    sock.onopen = function() { $("conn-status-text").textContent = "Connected"; };
    sock.onclose = function() {
      if (State.ws !== sock) return;
      $("conn-status-text").textContent = "Reconnecting…";
      setTimeout(connectWS, 5000);
    };
    sock.onerror = function() { /* onclose always follows */ };
    sock.onmessage = function(evt) {
      try {
        var msg = JSON.parse(evt.data);
        if (msg.event === "alert" && msg.payload) {
          AlertFeed.push(msg.payload);
          if (State.view === "overview") Overview.load();
          if (State.view === "alerts") Alerts.load();
          updateBadge();
        }
      } catch(e) {}
    };
  } catch(e) {}
}

async function updateBadge() {
  try {
    var a = await API.get("/alerts?limit=200");
    if (a._forbidden) return;
    var n = (a||[]).filter(function(x){return x.status==="new";}).length;
    var b = $("nav-alert-count");
    if (n > 0) { b.textContent = n; b.style.display = ""; } else { b.style.display = "none"; }
    var nb = $("notif-count");
    if (nb) { nb.textContent = n; nb.style.display = n > 0 ? "" : "none"; }
    var fc = $("feed-counter");
    if (fc) { fc.textContent = n + " new"; fc.style.display = n > 0 ? "" : "none"; }
  } catch(e) {}
}

/* ── LIVE ALERT FEED (P2): animated in, inline ack/dismiss ──── */
var AlertFeed = {
  push: function(p) {
    if (!p || !p.alert_id) return;
    if (State.feedSeen[p.alert_id]) return;
    State.feedSeen[p.alert_id] = true;
    var stack = $("feed-stack");
    if (!stack) return;
    while (stack.children.length >= 4) { stack.firstElementChild.remove(); }
    var el = document.createElement("div");
    el.className = "feed-card";
    el.setAttribute("role", "alert");
    el.innerHTML =
      '<div class="feed-top"><span class="feed-tag"><span class="lucide lucide-bell-ring"></span> Live Alert</span>' +
      '<span class="feed-time">' + fmtDate(new Date().toISOString()) + '</span></div>' +
      '<div class="feed-title">' + esc(p.atm_id || "ATM") + ' — ' + esc(p.city || "--") + '</div>' +
      '<div class="feed-meta">' + esc(p.recommended_action || "Review recommended") + '</div>' +
      '<div class="feed-risk">' + riskChip(p.risk_score, true) + '</div>' +
      '<div class="feed-actions">' +
        '<button class="btn btn-primary btn-sm" data-act="ack">Acknowledge</button>' +
        '<button class="btn btn-ghost btn-sm" data-act="dismiss">Dismiss</button>' +
        '<button class="btn btn-ghost btn-sm" data-act="open">Details</button>' +
      '</div>';
    el.querySelector('[data-act="ack"]').onclick = function() { AlertFeed.setStatus(p.alert_id, "acknowledged", el); };
    el.querySelector('[data-act="dismiss"]').onclick = function() { AlertFeed.setStatus(p.alert_id, "dismissed", el); };
    el.querySelector('[data-act="open"]').onclick = function() { Alerts.openDetail(p.alert_id); AlertFeed.remove(el); };
    stack.prepend(el);
    setTimeout(function() { AlertFeed.remove(el); }, 45000);
  },
  remove: function(el) {
    if (!el || !el.isConnected) return;
    el.classList.add("leaving");
    setTimeout(function() { el.remove(); }, 220);
  },
  setStatus: async function(alertId, status, el) {
    try {
      var body = { status: status };
      if (status === "dismissed") body.reason = "Dismissed from live feed (demo)";
      var r = await API.post("/alerts/" + alertId + "/status", body);
      if (r._forbidden) { Toast.warning("Access Denied", "Your role cannot change alert status."); return; }
      Toast.success(status === "acknowledged" ? "Acknowledged" : "Dismissed", shortId(alertId) + " → " + status + " (ledger-logged)");
      AlertFeed.remove(el);
      updateBadge();
      if (State.view === "alerts") Alerts.load();
    } catch(e) { Toast.error("Action Failed", e.message); }
  },
};

/* ═══ VIEW: OVERVIEW — command deck ═══ */
var Overview = {
  map: null,
  load: async function() {
    await Promise.all([this.loadStats(), this.loadMap(), this.loadAlerts(), this.loadHotspots(), ModelStatus.load()]);
  },
  loadStats: async function() {
    try {
      ["stat-atms","stat-alerts","stat-risk","stat-complaints-7d","stat-fraud-7d"].forEach(function(id){ SKEL.show(id,"stat"); });
      var s = await API.get("/stats/summary");
      if (s._forbidden) {
        if (State.simulation && State.simulationData && State.simulationData.stats) {
          var sd = State.simulationData.stats;
          $("stat-atms").textContent = fmtNum(sd.total_atms);
          $("stat-alerts").textContent = fmtNum(sd.alerts_total);
          $("stat-risk").textContent = fmtNum(sd.high_risk_atms);
          $("stat-complaints-7d").textContent = fmtNum(sd.complaints_7d);
          $("stat-fraud-7d").textContent = fmtNum(sd.fraud_withdrawals_7d);
        } else {
          ["stat-atms","stat-alerts","stat-risk","stat-complaints-7d","stat-fraud-7d"].forEach(function(id){
            $(id).textContent = "N/A";
          });
        }
        return;
      }
      State.stats = s;
      $("stat-atms").textContent = fmtNum(s.total_atms);
      $("stat-alerts").textContent = fmtNum(s.alerts_total != null ? s.alerts_total : (s.active_alerts || 0));
      $("stat-risk").textContent = fmtNum(s.high_risk_atms);
      $("stat-risk-label").textContent = "High Risk ATMs";
      $("stat-complaints-7d").textContent = fmtNum(s.complaints_7d);
      $("stat-fraud-7d").textContent = fmtNum(s.fraud_withdrawals_7d);
      if (State.replay && State.replayData) {
        // During a historical replay the risk snapshot reflects the replay day,
        // not "now" — relabel so the two are never conflated.
        var rd = State.replayData.risk_scores || [];
        var nAbove = rd.filter(function(x){ return (x.risk_score||0) >= 0.7; }).length;
        $("stat-risk").textContent = fmtNum(nAbove);
        $("stat-risk-label").textContent = "High Risk ATMs (Replay Day)";
      }
    } catch(e) { ["stat-atms","stat-alerts","stat-risk","stat-complaints-7d","stat-fraud-7d"].forEach(function(id){ $(id).textContent="--"; }); }
  },
  loadMap: async function() {
    if (!this.map) { this.map = new MapCtrl("main-map"); this.map.init(); }
    this.map.resize();
    var hud = $("map-hud-mode");
    try {
      var data;
      if (State.replay && State.replayData) {
        data = State.replayData.risk_scores || [];
        if (hud) { hud.className = "hud-pill replay"; hud.innerHTML = '<span class="lucide lucide-history"></span> HISTORICAL REPLAY — ' + esc(State.replayDay.date); }
      } else if (State.simulation) {
        data = (State.simulationData||{}).risk_scores || [];
        if (hud) { hud.className = "hud-pill replay"; hud.innerHTML = '<span class="lucide lucide-alert-triangle"></span> SCRIPTED SIMULATED SCENARIO'; }
      } else {
        data = await API.get("/risk-scores?horizon=24");
        if (data._forbidden) data = [];
        if (hud) { hud.className = "hud-pill live"; hud.innerHTML = '<span class="lucide lucide-radio"></span> LIVE RISK MAP — next 24h'; }
      }
      this.map.clearMarkers();
      if (!data.length) {
        // designed empty state on the map itself
        // (markers layer only; tiles/legend stay)
      }
      data.slice(0, 300).forEach(function(a) {
        var pop = '<b>'+esc(a.atm_id)+'</b><br>'+esc(a.bank_name||"")+'<br>'+esc(a.city||"")+'<br>Risk: '+(a.risk_score*100).toFixed(1)+'% ('+levelOf(a.risk_score)+')';
        Overview.map.addMarker(a.latitude, a.longitude, { risk: a.risk_score, popup: pop });
      });
      this.map.addHeat(data);
      this.map.fitBounds(data);
    } catch(e) { /* Map load failed — tiles stay, data retries on next cycle */ }
  },
  loadAlerts: async function() {
    try {
      var alerts = await API.get("/alerts?limit=10&status=new");
      if (alerts._forbidden) {
        $("recent-alerts-list").innerHTML = emptyState("lock", "Access Restricted", "Your role cannot view the alert feed.");
        $("priority-actions").innerHTML = emptyState("lock", "Access Restricted", "");
        return;
      }
      State.alerts = alerts || [];
      if (!alerts.length) {
        $("recent-alerts-list").innerHTML = emptyState("bell-off", "No active alerts", "No alerts with status NEW in your jurisdiction. On a calm day this is expected — watch the Model Status strip above.");
        $("priority-actions").innerHTML = emptyState("check-circle", "All Clear", "No priority actions. Run an Alert Cycle to force a scoring pass.");
        return;
      }
      $("recent-alerts-list").innerHTML = alerts.slice(0,6).map(function(a){
        return '<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border-subtle);cursor:pointer" onclick="Alerts.openDetail(\''+esc(a.alert_id)+'\')">'+
          '<span class="status-dot '+(a.risk_score>=0.7?"critical":"medium")+'" aria-hidden="true"></span>'+
          '<div style="flex:1;min-width:0"><div style="font-size:12px;font-weight:600" class="truncate">'+esc(a.atm_id)+' · '+esc(a.city||"--")+'</div>'+
          '<div style="font-size:11px;color:var(--text-muted)">'+fmtDate(a.created_at)+'</div></div>'+
          riskChip(a.risk_score)+'</div>';
      }).join("");
      var crit = alerts.filter(function(a){return a.risk_score>=0.7&&a.status==="new";});
      if (crit.length) {
        $("priority-actions").innerHTML = crit.slice(0,3).map(function(a){
          return '<div style="padding:11px;background:var(--risk-critical-bg);border:1px solid var(--risk-critical-brd);border-radius:var(--radius-md);margin-bottom:8px;cursor:pointer" onclick="Alerts.openDetail(\''+esc(a.alert_id)+'\')">'+
            '<div style="font-size:12px;font-weight:700;color:var(--risk-critical);margin-bottom:3px"><span class="lucide lucide-alert-triangle"></span> '+esc(a.atm_id)+' — '+riskChip(a.risk_score)+'</div>'+
            '<div style="font-size:11px;color:var(--text-secondary)">'+esc(a.recommended_action||"Investigate")+'</div></div>';
        }).join("");
      } else {
        $("priority-actions").innerHTML = emptyState("check-circle", "All Clear", "New alerts exist but none cross the 70% priority bar.");
      }
    } catch(e) {
      $("recent-alerts-list").innerHTML = emptyState("wifi-off", "Couldn't load alerts", "The API may be busy scoring — it will retry automatically.");
    }
  },
  loadHotspots: async function() {
    try {
      var data = await API.get("/hotspots?k=8");
      if (data._forbidden) { $("top-hotspots-list").innerHTML = emptyState("lock","Access Restricted",""); return; }
      if (!data.length) {
        $("top-hotspots-list").innerHTML = emptyState("flame","No hotspot data","No ATMs in scope right now.");
        return;
      }
      $("top-hotspots-list").innerHTML = data.slice(0,8).map(function(h, i){
        return '<div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid var(--border-subtle)">'+
          '<span class="mono" style="color:var(--text-muted);font-size:11px;width:18px">'+(i+1)+'</span>'+
          '<div style="flex:1;min-width:0"><div class="truncate" style="font-size:12px;font-weight:600">'+esc(h.atm_id)+'</div>'+
          '<div style="font-size:11px;color:var(--text-muted)" class="truncate">'+esc(h.city||"--")+' · '+esc(h.bank_name||"")+'</div></div>'+
          riskChip(h.risk_score)+'</div>';
      }).join("");
    } catch(e) { $("top-hotspots-list").innerHTML = emptyState("wifi-off","Couldn't load hotspots",""); }
  },
};

/* ═══ MODEL STATUS STRIP (P1) ═══ */
var ModelStatus = {
  last: null,
  load: async function() {
    if (!$("model-status-strip")) return;
    try {
      var url = "/model/status?horizon=24";
      if (State.replay && State.replayDay) url += "&as_of=" + encodeURIComponent(State.replayDay.as_of);
      var d = await API.get(url);
      if (d._forbidden) { $("ms-note").textContent = "Model status unavailable for your role."; return; }
      ModelStatus.last = d;
      ModelStatus.render(d);
    } catch(e) {
      $("ms-note").textContent = "Model status unavailable — check that the API server is running.";
      var dot = $("ms-dot"); if (dot) dot.className = "ms-dot ms-dot-down";
    }
  },
  render: function(d) {
    $("ms-computed").textContent = d.computed_at ? fmtDate(d.computed_at) : (d.as_of ? fmtDate(d.as_of) : "--");
    $("ms-atms").textContent = fmtNum(d.atms_scored);
    $("ms-max").textContent = d.max_risk != null ? (d.max_risk*100).toFixed(1) + "%" : "--";
    $("ms-median").textContent = d.median_risk != null ? (d.median_risk*100).toFixed(1) + "%" : "--";
    var dot = $("ms-dot"); var chip = $("ms-source-chip");
    if (State.replay && State.replayDay) {
      dot.className = "ms-dot ms-dot-replay";
      chip.textContent = "HISTORICAL REPLAY";
      $("ms-note").innerHTML = 'Replaying <b>' + esc(State.replayDay.date) + '</b> — the <b>live model</b> re-forecasts that day from data available up to the previous evening. Real historical synthetic data, not the scripted scenario. ' +
        (d.calm_day
          ? 'Peak risk that day: <b>' + ((d.max_risk||0)*100).toFixed(1) + '%</b> — below the ' + ((d.threshold||0.7)*100).toFixed(0) + '% alert threshold, so no alerts would have fired.'
          : '<b>' + fmtNum(d.above_threshold) + '</b> ATM(s) would have crossed the ' + ((d.threshold||0.7)*100).toFixed(0) + '% alert threshold that day.');
      return;
    }
    chip.textContent = d.demo_mode ? "DEMO CACHE" : "LIVE MODEL";
    dot.className = "ms-dot " + (d.calm_day ? "ms-dot-calm" : "ms-dot-alert");
    if (d.calm_day) {
      $("ms-note").innerHTML = '<b>Calm day</b> — no ATM currently crosses the ' + ((d.threshold||0.7)*100).toFixed(0) + '% alert threshold (max ' + ((d.max_risk||0)*100).toFixed(1) + '%). <b>This is expected behavior, not a failure.</b> Use "Replay High-Risk Day" to watch the same live model score a day that actually surged.';
    } else {
      $("ms-note").innerHTML = '<b>' + fmtNum(d.above_threshold) + ' ATM' + (d.above_threshold===1?"":"s") + '</b> at or above the ' + ((d.threshold||0.7)*100).toFixed(0) + '% alert threshold — max risk ' + ((d.max_risk||0)*100).toFixed(1) + '%. Alerts are being raised for crossers.';
    }
  },
};

/* ═══ HISTORICAL REPLAY (P1) ═══ */
var Replay = {
  openPicker: async function() {
    var btn = $("btn-replay-day") ;
    var topBtn = $("btn-replay-day-top");
    if (btn) btn.disabled = true;
    if (topBtn) topBtn.disabled = true;
    try {
      var d = await API.get("/replay/high-risk-days?limit=5");
      if (d._forbidden) { Toast.warning("Access Denied", "Insufficient permissions."); return; }
      var days = d.days || [];
      if (!days.length) { Toast.info("No History", "No fraud-withdrawal history found in your jurisdiction."); return; }
      var rows = days.map(function(day, i) {
        return '<div class="replay-day-row">' +
          '<div class="replay-day-info"><div class="replay-day-date">' + esc(day.date) + '</div>' +
          '<div class="replay-day-meta">' + fmtNum(day.fraud_withdrawals) + ' fraud withdrawals &middot; ' +
          fmtNum(day.complaints_filed) + ' complaints &middot; ₹' + fmtNum(Math.round(day.fraud_amount_inr||0)) + ' exposed</div></div>' +
          '<button class="btn btn-primary btn-sm" id="replay-go-' + i + '">Replay This Day</button></div>';
      }).join("");
      Modal.show({
        title: "Replay Historical High-Risk Day",
        body: '<p class="replay-picker-note">Days with the most <b>actual fraud withdrawals</b> in your jurisdiction. The <b>live model</b> re-forecasts the next 24h using only data available up to the previous evening — a genuine out-of-sample replay, not the scripted scenario. Inference takes up to ~30&nbsp;seconds.</p>' + rows,
        footer: '<button class="btn btn-secondary btn-sm" onclick="Modal.hide()">Cancel</button>',
      });
      days.forEach(function(day, i) {
        var b = $("replay-go-" + i);
        if (b) b.onclick = function() { Replay.start(day); };
      });
    } catch(e) { Toast.error("Replay Failed", e.message); }
    finally { if (btn) btn.disabled = false; if (topBtn) topBtn.disabled = false; }
  },
  start: async function(day) {
    if (State.simulation) Simulation.exit();
    Modal.hide();
    var btn = $("btn-replay-day");
    if (btn) { btn.disabled = true; btn.classList.add("loading"); }
    Toast.info("Replay Running", "Live model scoring " + day.date + " — inference can take up to ~30 seconds. The map will update when it lands.");
    try {
      var data = await API.get("/risk-scores?as_of=" + encodeURIComponent(day.as_of) + "&horizon=24");
      if (data._forbidden) { Toast.warning("Access Denied", "Insufficient permissions."); return; }
      State.replay = true; State.replayDay = day;
      State.replayData = { risk_scores: data, as_of: day.as_of };
      $("replay-banner").classList.add("active");
      $("replay-banner-text").textContent = "Live model scoring " + day.date + " — " + fmtNum(data.length) + " ATMs scored (as_of " + fmtDate(day.as_of) + "). Real historical synthetic data, not the scripted scenario.";
      var maxR = data.length ? Math.max.apply(null, data.map(function(s){return s.risk_score||0;})) : 0;
      var above = data.filter(function(s){ return (s.risk_score||0) >= 0.7; }).length;
      var calm = ModelStatus.last && !State.replay ? null : (ModelStatus.last ? ModelStatus.last.max_risk : null);
      Toast.success("Replay Ready", day.date + ": max risk " + (maxR*100).toFixed(1) + "%" +
        (calm != null && calm < maxR ? " (calm-day max: " + (calm*100).toFixed(1) + "%)" : "") +
        ", " + above + " ATM(s) above the 70% threshold.");
      Overview.load();
    } catch(e) { Toast.error("Replay Failed", e.message); }
    finally { if (btn) { btn.disabled = false; btn.classList.remove("loading"); } }
  },
  exit: function() {
    State.replay = false; State.replayDay = null; State.replayData = null;
    $("replay-banner").classList.remove("active");
    Toast.info("Replay Exited", "Returned to live data mode.");
    Overview.load();
  },
};

/* ═══ VIEW: RISK INTELLIGENCE ═══ */
var Risk = {
  map: null,
  load: async function() {
    if (!this.map) { this.map = new MapCtrl("risk-map", {zoom:5}); this.map.init(); }
    this.map.resize();
    await this.loadScores();
  },
  loadScores: async function() {
    var horizon = $("risk-horizon").value || "24";
    var city = $("risk-city-filter").value || "";
    var bank = $("risk-bank-filter") ? $("risk-bank-filter").value : "";
    var riskLevel = $("risk-level-filter") ? $("risk-level-filter").value : "";
    // /risk-scores accepts only city/as_of/horizon — bank & level are filtered client-side.
    var url = "/risk-scores?horizon=" + horizon;
    if (city) url += "&city=" + encodeURIComponent(city);
    try {
      SKEL.show("risk-atm-table","table");
      var data = await API.get(url);
      if (data._forbidden) { Toast.warning("Access Denied", "Your role cannot view risk scores."); return; }
      var rows = data || [];
      if (bank) rows = rows.filter(function(a){ return a.bank_name === bank; });
      if (riskLevel) rows = rows.filter(function(a){ return a.risk_level === riskLevel; });
      State.riskScores = rows;
      this.render(data || []);
      this.renderMap();
    } catch(e) { Toast.error("Load Failed", e.message); }
  },
  render: function(allRows) {
    var data = State.riskScores;
    var c = {critical:0,high:0,medium:0,low:0};
    allRows.forEach(function(d){
      var lvl = levelOf(d.risk_score);
      if(lvl==="CRITICAL")c.critical++;else if(lvl==="HIGH")c.high++;else if(lvl==="MEDIUM")c.medium++;else c.low++;
    });
    $("risk-total-atms").textContent = fmtNum(allRows.length);
    $("risk-critical-count").textContent = fmtNum(c.critical);
    $("risk-high-count").textContent = fmtNum(c.high);
    $("risk-medium-count").textContent = fmtNum(c.medium);
    $("risk-low-count").textContent = fmtNum(c.low);
    var cities = []; var seen = {};
    var banks = []; var seenB = {};
    allRows.forEach(function(d){ if(d.city&&!seen[d.city]){seen[d.city]=1;cities.push(d.city);} if(d.bank_name&&!seenB[d.bank_name]){seenB[d.bank_name]=1;banks.push(d.bank_name);} });
    cities.sort(); banks.sort();
    var cf = $("risk-city-filter"); var cur = cf.value;
    cf.innerHTML = '<option value="">All Cities</option>' + cities.map(function(c){return '<option value="'+esc(c)+'"'+(c===cur?' selected':'')+'>'+esc(c)+'</option>';}).join("");
    var bf = $("risk-bank-filter"); var bcur = bf.value;
    bf.innerHTML = '<option value="">All Banks</option>' + banks.map(function(b){return '<option value="'+esc(b)+'"'+(b===bcur?' selected':'')+'>'+esc(b)+'</option>';}).join("");
    var scoped = Auth.role() !== "I4C_ADMIN";
    $("risk-scoped-note").style.display = scoped ? "" : "none";
    var tbody = $("risk-atm-table");
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="8" class="table-empty">No ATMs match the current filters in your jurisdiction.</td></tr>'; return; }
    tbody.innerHTML = data.slice(0,100).map(function(a){
      return '<tr>'+
        td('<span class="mono">'+esc(a.atm_id)+'</span>','ATM ID')+
        td(esc(a.bank_name),'Bank')+
        td(esc(a.city),'City')+
        td(esc(a.district),'District')+
        td(esc(a.state),'State')+
        td(riskChip(a.risk_score, true),'Risk')+
        td(levelChip(a.risk_level),'Level')+
        td('<button class="btn btn-ghost btn-sm" onclick="Risk.openDetail(\''+esc(a.atm_id)+'\')">Details</button>','', 'no-label')+
      '</tr>';
    }).join("");
  },
  renderMap: function() {
    if (!this.map||!this.map.map) return;
    this.map.clearMarkers();
    State.riskScores.forEach(function(a){
      var pop = '<b>'+esc(a.atm_id)+'</b><br>'+esc(a.bank_name)+'<br>'+esc(a.city)+'<br>Risk: '+(a.risk_score*100).toFixed(1)+'% ('+levelOf(a.risk_score)+')';
      Risk.map.addMarker(a.latitude,a.longitude,{risk:a.risk_score,popup:pop});
    });
    this.map.addHeat(State.riskScores);
    if (State.riskScores.length) this.map.fitBounds(State.riskScores);
  },
  openDetail: function(atmId) {
    var atm = State.riskScores.find(function(a){return a.atm_id===atmId;});
    if (!atm) return;
    Drawer.open({
      title: "ATM: " + atm.atm_id,
      body: '<div class="drawer-section"><div class="drawer-section-title"><span class="lucide lucide-map-pin"></span> Location</div>'+
        '<div class="drawer-kv"><span class="k">Bank</span><span class="v">'+esc(atm.bank_name)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Branch</span><span class="v">'+esc(atm.branch_name)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">City</span><span class="v">'+esc(atm.city)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">District</span><span class="v">'+esc(atm.district)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">State</span><span class="v">'+esc(atm.state)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">PS Area</span><span class="v">'+esc(atm.police_station_area)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">PIN</span><span class="v mono">'+esc(atm.pin)+'</span></div></div>'+
        '<div class="drawer-section"><div class="drawer-section-title"><span class="lucide lucide-activity"></span> Risk Assessment — next 24h</div>'+
        '<div class="drawer-kv"><span class="k">Risk Score</span><span class="v">'+riskChip(atm.risk_score, true)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Emerging Risk</span><span class="v mono">'+(atm.emerging_risk!=null?(atm.emerging_risk*100).toFixed(1)+'%':'--')+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Intervention Priority</span><span class="v mono">'+(atm.intervention_priority!=null?(atm.intervention_priority*100).toFixed(1)+'%':'--')+'</span></div>'+
        '<div class="drawer-kv"><span class="k">As of</span><span class="v mono">'+fmtDate(atm.as_of)+'</span></div>'+
        (atm.simulated?'<div class="drawer-kv"><span class="k">Source</span><span class="v"><span class="chip chip-gold">Simulated</span></span></div>':'')+'</div>'+
        '<div class="report-output" style="font-size:11.5px">Risk levels: LOW &lt;40% · MEDIUM 40–70% · HIGH 70–85% · CRITICAL &ge;85%. The alert threshold is 70% — scores are calibrated probabilities from controlled synthetic evaluation, decision support only.</div>',
    });
  },
};

/* ═══ VIEW: ALERT OPERATIONS ═══ */
var Alerts = {
  load: async function() {
    var status = $("alerts-status-filter").value || "";
    var url = "/alerts?limit=200";
    if (status) url += "&status=" + encodeURIComponent(status);
    try {
      SKEL.show("alerts-full-table","table");
      var data = await API.get(url);
      if (data._forbidden) { Toast.warning("Access Denied", "Your role cannot view alerts."); return; }
      State.alerts = data || [];
      var chip = $("alerts-count-chip");
      chip.textContent = State.alerts.length + (status ? " (" + status + ")" : "");
      chip.style.display = "";
      this.render();
    } catch(e) { Toast.error("Load Failed", e.message); }
  },
  render: function() {
    var data = State.alerts;
    var tbody = $("alerts-full-table");
    if (!data.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="table-empty">' +
        'No alerts' + ($("alerts-status-filter").value ? ' with status "' + esc($("alerts-status-filter").value) + '"' : '') +
        ' in your jurisdiction. On a calm day this is expected — the Model Status strip on Overview explains why.</td></tr>';
      return;
    }
    tbody.innerHTML = data.map(function(a){
      var actions = '';
      if (a.status==='new') actions =
        '<button class="btn btn-secondary btn-sm" onclick="event.stopPropagation();Alerts.setStatus(\''+esc(a.alert_id)+'\',\'acknowledged\')">Acknowledge</button> ' +
        '<button class="btn btn-primary btn-sm" onclick="event.stopPropagation();Alerts.setStatus(\''+esc(a.alert_id)+'\',\'actioned\')">Action</button> ' +
        '<button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();Alerts.setStatus(\''+esc(a.alert_id)+'\',\'dismissed\')">Dismiss</button>';
      else if (a.status==='acknowledged') actions =
        '<button class="btn btn-primary btn-sm" onclick="event.stopPropagation();Alerts.setStatus(\''+esc(a.alert_id)+'\',\'actioned\')">Action</button> ' +
        '<button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();Alerts.setStatus(\''+esc(a.alert_id)+'\',\'escalated\')">Escalate</button>';
      else if (a.status==='actioned') actions =
        '<button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();Alerts.setStatus(\''+esc(a.alert_id)+'\',\'escalated\')">Escalate</button>';
      else if (a.status==='monitoring') actions =
        '<button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();Alerts.setStatus(\''+esc(a.alert_id)+'\',\'review_requested\')">Request Review</button>';
      return '<tr class="alert-row" onclick="Alerts.openDetail(\''+esc(a.alert_id)+'\')">'+
        td('<span class="mono">'+shortId(a.alert_id)+'</span>','Alert ID')+
        td(esc(a.atm_id),'ATM')+
        td(esc(a.city||"--"),'City')+
        td(riskChip(a.risk_score, true),'Risk')+
        td(tierChip(a.tier),'Tier')+
        td(statusChip(a.status),'Status')+
        td('<span class="mono" style="font-size:11px">'+fmtDate(a.created_at)+'</span>','Created')+
        td('<div style="display:flex;gap:4px;flex-wrap:wrap">'+actions+'</div>','Actions','no-label')+
      '</tr>';
    }).join("");
  },
  setStatus: async function(alertId, status) {
    try {
      var body = { status: status };
      if (status === "dismissed") body.reason = "Dismissed from Alert Operations (demo)";
      if (status === "escalated") body.reason = "Escalated from Alert Operations (demo)";
      var r = await API.post("/alerts/"+alertId+"/status", body);
      if (r._forbidden) { Toast.warning("Access Denied", "Insufficient permissions."); return; }
      Toast.success("Alert Updated", shortId(alertId)+" → "+status.replace(/_/g," ")+" (ledger-logged)");
      this.load(); updateBadge();
    } catch(e) { Toast.error("Action Failed", e.message); }
  },
  openDetail: async function(alertId) {
    var alert = State.alerts.find(function(a){return a.alert_id===alertId;});
    if (!alert) { try { alert = await API.get("/alerts/"+alertId); } catch(e){} }
    if (!alert || alert._forbidden) return;
    var self = this;
    Drawer.open({
      title: "Alert " + shortId(alert.alert_id),
      body: '<div class="skeleton skeleton-text" style="width:90%"></div><div class="skeleton skeleton-text" style="width:70%"></div>',
      footer: this.footerFor(alert),
    });
    API.get("/alerts/"+alert.alert_id+"/evidence").then(function(ev) {
      if (!ev || ev._forbidden) {
        $("drawer-body").innerHTML = self.infoHtml(alert) + emptyState("lock","Evidence restricted","Your role cannot view the evidence panel for this alert.");
        return;
      }
      $("drawer-body").innerHTML = Evidence.render(ev) + '<div class="drawer-section" style="margin-top:18px"><div class="drawer-section-title">Alert Record</div>' + self.kvHtml(alert) + '</div>';
      $("drawer-footer").innerHTML = self.footerFor(alert);
    }).catch(function(){
      $("drawer-body").innerHTML = self.infoHtml(alert) + emptyState("wifi-off","Evidence unavailable","The evidence service didn't respond.");
    });
  },
  footerFor: function(alert) {
    var f = '';
    if (alert.status==='new') f += '<button class="btn btn-secondary btn-sm" onclick="Alerts.setStatus(\''+esc(alert.alert_id)+'\',\'acknowledged\');Drawer.close()">Acknowledge</button>' +
      '<button class="btn btn-primary btn-sm" onclick="Alerts.setStatus(\''+esc(alert.alert_id)+'\',\'actioned\');Drawer.close()">Action</button>' +
      '<button class="btn btn-ghost btn-sm" onclick="Alerts.setStatus(\''+esc(alert.alert_id)+'\',\'dismissed\');Drawer.close()">Dismiss</button>';
    else if (alert.status==='acknowledged') f += '<button class="btn btn-primary btn-sm" onclick="Alerts.setStatus(\''+esc(alert.alert_id)+'\',\'actioned\');Drawer.close()">Action</button>';
    return f + '<button class="btn btn-secondary btn-sm" onclick="Drawer.close()">Close</button>';
  },
  kvHtml: function(alert) {
    return '<div class="drawer-kv"><span class="k">Alert ID</span><span class="v mono">'+esc(alert.alert_id)+'</span></div>'+
      '<div class="drawer-kv"><span class="k">ATM</span><span class="v mono">'+esc(alert.atm_id)+'</span></div>'+
      '<div class="drawer-kv"><span class="k">Bank</span><span class="v">'+esc(alert.bank_name||"--")+'</span></div>'+
      '<div class="drawer-kv"><span class="k">Jurisdiction</span><span class="v">'+esc(alert.police_station_area||"--")+', '+esc(alert.district||"--")+', '+esc(alert.state||"--")+'</span></div>'+
      '<div class="drawer-kv"><span class="k">Tier</span><span class="v">'+tierChip(alert.tier)+'</span></div>'+
      '<div class="drawer-kv"><span class="k">Status</span><span class="v">'+statusChip(alert.status)+'</span></div>'+
      '<div class="drawer-kv"><span class="k">Created</span><span class="v mono">'+fmtDate(alert.created_at)+'</span></div>'+
      (alert.model_version?'<div class="drawer-kv"><span class="k">Model</span><span class="v mono">'+esc(alert.model_version)+'</span></div>':'');
  },
  infoHtml: function(alert) {
    return '<div class="drawer-section"><div class="drawer-section-title">Alert Record</div>' + this.kvHtml(alert) + '</div>';
  },
};

/* ═══ EVIDENCE (P2): summary → 3 fields → uncertainty → SHAP collapsed ═══ */
var Evidence = {
  render: function(ev) {
    if (!ev || !Object.keys(ev).length) return emptyState("file-text","No evidence","No evidence found for this alert.");
    var html = '';
    // 1) plain-language summary
    var atm = ev.atm_id || "--";
    var unc = ev.uncertainty || {};
    var risk = unc.risk_score != null ? unc.risk_score : null;
    html += '<div class="evidence-summary">' +
      '<div class="es-headline">' +
      (risk != null
        ? '<b>' + esc(atm) + '</b> is at <b>' + (risk*100).toFixed(1) + '%</b> model-estimated risk of a fraud cash-out in the next 24h. ' +
          (levelOf(risk) === "CRITICAL" || levelOf(risk) === "HIGH"
            ? 'Recommended: <b>' + esc(ev.suggested_action || ev.recommended_action || "priority review") + '</b>.'
            : 'This is below the 70% alert threshold — hold and monitor per the evidence-first policy.')
        : esc(ev.suggested_action || "Review this alert.")) +
      '</div>' +
      '<div class="es-rule">Fired rule: ' + esc(ev.fired_rule || "--") +
      (ev.data_through ? ' · data through ' + fmtDate(ev.data_through) : '') + '</div></div>';
    // 2) the 3 evidence fields
    html += '<div class="evidence-fields">' + Evidence.field("complaint activity", "message-square", Evidence.activityText(ev.complaint_activity)) +
      Evidence.field("withdrawal activity", "credit-card", Evidence.activityText(ev.withdrawal_activity)) +
      Evidence.field("context signal", "radio", Evidence.contextText(ev.context_signal)) + '</div>';
    // 3) recommended actions
    if (ev.recommended_actions && ev.recommended_actions.length) {
      html += '<div class="drawer-section"><div class="drawer-section-title">Recommended Actions</div>';
      ev.recommended_actions.forEach(function(a, i) {
        html += '<div class="drawer-kv"><span class="k">' + (a.step || (i+1)) + '. ' + esc(a.owner || "") + '</span><span class="v">' + esc(a.action || "") + '</span></div>';
      });
      html += '</div>';
    }
    // 4) freeze accounts
    if (ev.recommended_freeze_accounts && ev.recommended_freeze_accounts.length) {
      html += '<div class="drawer-section"><div class="drawer-section-title">Fund-Freeze Candidates (CFCFRMS)</div>';
      ev.recommended_freeze_accounts.slice(0,5).forEach(function(acc) {
        html += '<div class="drawer-kv"><span class="k mono">'+esc(acc.account_token ? acc.account_token.slice(-12) : "--")+'</span><span class="v mono">'+fmtNum(acc.recent_withdrawals)+' wd</span></div>';
      });
      html += '</div>';
    }
    // 5) uncertainty
    if (unc && Object.keys(unc).length) {
      html += '<div class="drawer-section"><div class="drawer-section-title">Uncertainty & Confidence</div>' +
        '<div class="drawer-kv"><span class="k">Confidence</span><span class="v mono">'+(unc.confidence!=null?(unc.confidence*100).toFixed(0)+'%':'--')+'</span></div>' +
        '<div class="drawer-kv"><span class="k">Evidence strength</span><span class="v mono">'+(unc.evidence_strength!=null?(unc.evidence_strength*100).toFixed(0)+'%':'--')+'</span></div>' +
        '<div class="drawer-kv"><span class="k">Data freshness</span><span class="v mono">'+(unc.data_freshness_hours!=null?unc.data_freshness_hours.toFixed(1)+'h':'--')+'</span></div>' +
        '<div class="drawer-kv"><span class="k">Model disagreement</span><span class="v mono">'+(unc.model_disagreement_abs!=null?unc.model_disagreement_abs.toFixed(3):'--')+'</span></div>' +
        (unc.synthetic_evaluation ? '<div class="drawer-kv"><span class="k">Evaluation</span><span class="v"><span class="chip chip-gold">synthetic</span></span></div>' : '') +
        '</div>';
    }
    // 6) counterfactual
    var cf = ev.counterfactual_whatif;
    if (cf && cf.current_risk != null) {
      html += '<div class="drawer-section"><div class="drawer-section-title">Counterfactual (what-if)</div>' +
        '<div class="report-output" style="font-size:12px">Without the complaint surge, this ATM would score <b>' + ((cf.risk_without_complaint_surge||0)*100).toFixed(1) + '%</b> (' +
        (cf.delta>=0 ? '-' : '+') + Math.abs(cf.delta*100).toFixed(1) + ' pts). ' + esc(cf.interpretation || "") + '</div></div>';
    }
    // 7) SHAP — collapsed by default (P2 requirement)
    var shap = ev.per_instance_shap || [];
    var glob = ev.feature_contributions || [];
    if (shap.length || glob.length) {
      html += '<details class="shap-toggle"><summary>Why this score — SHAP & feature contributions (technical)</summary><div class="shap-body">';
      if (shap.length) {
        var maxAbs = Math.max.apply(null, shap.map(function(f){return Math.abs(f.shap||0);})) || 1;
        html += '<div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.7px;color:var(--text-muted);margin:10px 0 8px">Per-instance TreeSHAP (pushes risk up / down)</div><div class="feature-bars">';
        shap.forEach(function(f){
          var v = f.shap || 0;
          var pct = Math.abs(v)/maxAbs*100;
          html += '<div class="feature-bar"><span class="feature-bar-name">'+esc(f.feature)+'</span><div class="feature-bar-track"><div class="feature-bar-fill '+(v>=0?"positive":"negative")+'" style="width:'+pct.toFixed(0)+'%"></div></div><span class="feature-bar-value">'+(v>=0?"+":"")+v.toFixed(3)+'</span></div>';
        });
        html += '</div>';
      }
      if (glob.length) {
        html += '<div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.7px;color:var(--text-muted);margin:14px 0 8px">Global importance & instance percentile</div>';
        glob.forEach(function(f){
          html += '<div class="drawer-kv"><span class="k mono">'+esc(f.feature)+'</span><span class="v mono">value '+(f.value!=null?f.value:"--")+' · pct '+(f.percentile!=null?(f.percentile*100).toFixed(0)+"%":"--")+' · imp '+(f.global_importance!=null?f.global_importance.toFixed(3):"--")+'</span></div>';
        });
      }
      if (ev.explainability_note) html += '<div style="font-size:10.5px;color:var(--text-muted);margin-top:10px;line-height:1.55">'+esc(ev.explainability_note)+'</div>';
      html += '</div></details>';
    }
    // scoring coverage
    if (ev.atms_scored != null) {
      html += '<div style="font-size:10.5px;color:var(--text-muted);margin-top:12px">Scoring coverage: '+fmtNum(ev.atms_scored)+'/'+fmtNum(ev.atms_total)+' ATMs ('+(ev.scoring_coverage_pct!=null?ev.scoring_coverage_pct.toFixed(1):"--")+'%)</div>';
    }
    return html;
  },
  field: function(label, icon, value) {
    return '<div class="evidence-field"><div class="ef-label"><span class="lucide lucide-'+icon+'"></span> ' + esc(label) + '</div><div class="ef-value">' + value + '</div></div>';
  },
  activityText: function(a) {
    if (!a || typeof a !== "object") return "--";
    var parts = [];
    if (a.count_24h != null) parts.push('<b>'+fmtNum(a.count_24h)+'</b> in 24h');
    if (a.count_7d != null) parts.push('<b>'+fmtNum(a.count_7d)+'</b> in 7d');
    if (a.amount_24h != null) parts.push('₹'+fmtNum(Math.round(a.amount_24h))+' in 24h');
    if (a.fraud_count_24h != null) parts.push('<b>'+fmtNum(a.fraud_count_24h)+'</b> fraud in 24h');
    if (!parts.length) {
      Object.entries(a).slice(0,3).forEach(function(p){ parts.push(esc(p[0])+': <b>'+(typeof p[1]==="number"?fmtNum(Math.round(p[1]*100)/100):esc(String(p[1])))+'</b>'); });
    }
    return parts.join('<br>') || "--";
  },
  contextText: function(c) {
    if (c == null) return "--";
    if (typeof c === "object") {
      var parts = [];
      Object.entries(c).slice(0,4).forEach(function(p){ parts.push(esc(p[0].replace(/_/g," "))+': <b>'+(typeof p[1]==="number"?(Math.abs(p[1])<10?p[1].toFixed(2):fmtNum(Math.round(p[1]))):esc(String(p[1])))+'</b>'); });
      return parts.join('<br>') || "--";
    }
    return esc(String(c));
  },
};

/* ═══ VIEW: RECOVERY CENTER ═══ */
var Recovery = {
  load: async function() {
    try {
      var data = await API.get("/recovery/recommendations");
      if (data._forbidden) { Toast.warning("Access Denied", "Recovery data is restricted to BANK and I4C_ADMIN roles."); return; }
      State.recovery = data || [];
      this.render();
    } catch(e) { Toast.error("Load Failed", e.message); }
  },
  render: function() {
    var data = State.recovery;
    var c = {total:data.length,flagged:0,held:0,recovered:0};
    data.forEach(function(r){
      if(r.status==="freeze_requested")c.flagged++;if(r.status==="held")c.held++;if(r.status==="recovered")c.recovered++;
    });
    $("rec-total").textContent = fmtNum(c.total);
    $("rec-flagged").textContent = fmtNum(c.flagged);
    $("rec-held").textContent = fmtNum(c.held);
    $("rec-recovered").textContent = fmtNum(c.recovered);
    var tbody = $("recovery-table");
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="7" class="table-empty">No recovery recommendations yet — they are generated when alerts fire with linked mule accounts.</td></tr>'; return; }
    tbody.innerHTML = data.map(function(r){
      var acts = '';
      if (r.status==='freeze_requested') acts = '<button class="btn btn-primary btn-sm" onclick="Recovery.freeze(\''+esc(r.rec_id)+'\')">Place Hold</button>';
      else if (r.status==='held') acts = '<button class="btn btn-primary btn-sm" onclick="Recovery.markRecovered(\''+esc(r.rec_id)+'\')">Mark Recovered</button>';
      acts += ' <button class="btn btn-ghost btn-sm" onclick="Recovery.detail(\''+esc(r.rec_id)+'\')">Details</button>';
      return '<tr>'+
        td('<span class="mono">'+shortId(r.rec_id)+'</span>','Rec ID')+
        td('<span class="mono">'+esc(r.account_token?r.account_token.slice(-8):"--")+'</span>','Account')+
        td(esc(r.home_bank),'Bank')+
        td('<span class="mono">₹'+fmtNum(r.amount_at_risk)+'</span>','Amount')+
        td(esc(r.suspected_atm||"--"),'Suspected ATM')+
        td(statusChip(r.status),'Status')+
        td('<div style="display:flex;gap:4px;flex-wrap:wrap">'+acts+'</div>','Actions','no-label')+
      '</tr>';
    }).join("");
  },
  freeze: async function(recId) {
    var ok = await Modal.confirm("Confirm Hold", "Place a hold on the account for "+shortId(recId)+"?");
    if (!ok) return;
    try {
      var r = await API.post("/recovery/"+recId+"/status",{status:"held",amount_held:0});
      if (r._forbidden) { Toast.warning("Access Denied","Insufficient permissions."); return; }
      Toast.success("Hold Placed","Account freeze initiated for "+shortId(recId));
      this.load();
    } catch(e) { Toast.error("Freeze Failed",e.message); }
  },
  markRecovered: async function(recId) {
    var ok = await Modal.confirm("Confirm Recovery","Mark "+shortId(recId)+" as recovered?");
    if (!ok) return;
    try {
      var r = await API.post("/recovery/"+recId+"/status",{status:"recovered",amount_recovered:0});
      if (r._forbidden) { Toast.warning("Access Denied","Insufficient permissions."); return; }
      Toast.success("Recovered",shortId(recId)+" marked as recovered");
      this.load();
    } catch(e) { Toast.error("Update Failed",e.message); }
  },
  detail: function(recId) {
    var r = State.recovery.find(function(x){return x.rec_id===recId;});
    if (!r) return;
    Drawer.open({
      title: "Recovery: "+shortId(r.rec_id),
      body: '<div class="drawer-section"><div class="drawer-section-title">Details</div>'+
        '<div class="drawer-kv"><span class="k">Rec ID</span><span class="v mono">'+esc(r.rec_id)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Alert ID</span><span class="v mono">'+esc(r.alert_id||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Account</span><span class="v mono">'+esc(r.account_token?r.account_token.slice(-12):"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Home Bank</span><span class="v">'+esc(r.home_bank)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Amount at Risk</span><span class="v mono">₹'+fmtNum(r.amount_at_risk)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Amount Held</span><span class="v mono">₹'+fmtNum(r.amount_held)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Amount Recovered</span><span class="v mono">₹'+fmtNum(r.amount_recovered)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Suspected ATM</span><span class="v">'+esc(r.suspected_atm||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Window</span><span class="v">'+esc(r.predicted_window||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Action</span><span class="v">'+esc(r.recommended_action||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Status</span><span class="v">'+statusChip(r.status)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Created</span><span class="v mono">'+fmtDate(r.created_at)+'</span></div></div>',
      footer: '<button class="btn btn-secondary btn-sm" onclick="Drawer.close()">Close</button>',
    });
  },
};

/* ═══ VIEW: INVESTIGATIONS ═══ */
var Investigations = {
  complaints: [],
  load: async function() { await this.loadComplaints(); },
  loadComplaints: async function() {
    try {
      var data = await API.get("/complaints?limit=50");
      if (data._forbidden) { $("complaints-table").innerHTML = '<tr><td colspan="6" class="table-empty">Complaints are not visible to the BANK role (bank sees linked accounts via evidence only).</td></tr>'; return; }
      this.complaints = Array.isArray(data) ? data : (data && data.items || data && data.complaints || []);
      this.renderComplaints();
    } catch(e) { $("complaints-table").innerHTML = '<tr><td colspan="6" class="table-empty">Failed to load complaints.</td></tr>'; }
  },
  renderComplaints: function(filter) {
    var data = this.complaints;
    if (filter) {
      var f = filter.toLowerCase();
      data = data.filter(function(c){return (c.complaint_id||"").toLowerCase().indexOf(f)>=0||(c.victim_city||c.city||"").toLowerCase().indexOf(f)>=0;});
    }
    var tbody = $("complaints-table");
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="6" class="table-empty">No complaints in your jurisdiction.</td></tr>'; return; }
    tbody.innerHTML = data.slice(0,50).map(function(c){
      return '<tr>'+
        td('<span class="mono">'+esc(c.complaint_id||"--")+'</span>','Complaint ID')+
        td(esc(c.victim_city||c.city||"--"),'City')+
        td('<span class="mono">₹'+fmtNum(c.amount_lost!=null?c.amount_lost:c.amount)+'</span>','Amount')+
        td(esc(c.complaint_type||"--"),'Type')+
        td('<span class="mono" style="font-size:11px">'+fmtDate(c.filing_timestamp||c.date||c.created_at)+'</span>','Date')+
        td('<button class="btn btn-ghost btn-sm" onclick="Investigations.openComplaint(\''+esc(c.complaint_id)+'\')">View</button>','', 'no-label')+
      '</tr>';
    }).join("");
  },
  openComplaint: function(id) {
    var c = this.complaints.find(function(x){return x.complaint_id===id;});
    if (!c) return;
    Drawer.open({
      title: "Complaint: "+id,
      body: '<div class="drawer-section"><div class="drawer-section-title">Complaint Details</div>'+
        '<div class="drawer-kv"><span class="k">ID</span><span class="v mono">'+esc(c.complaint_id)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Type</span><span class="v">'+esc(c.complaint_type||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Amount Lost</span><span class="v mono">₹'+fmtNum(c.amount_lost!=null?c.amount_lost:c.amount)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">City</span><span class="v">'+esc(c.victim_city||c.city||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">District</span><span class="v">'+esc(c.victim_district||c.district||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">State</span><span class="v">'+esc(c.victim_state||c.state||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Filed</span><span class="v mono">'+fmtDate(c.filing_timestamp||c.date||c.created_at)+'</span></div>'+
        (c.linked_account_token?'<div class="drawer-kv"><span class="k">Linked Account</span><span class="v mono">'+esc(c.linked_account_token.slice(-12))+'</span></div>':'')+
        (c.status?'<div class="drawer-kv"><span class="k">Status</span><span class="v">'+esc(c.status)+'</span></div>':'')+'</div>',
      footer: '<button class="btn btn-secondary btn-sm" onclick="Drawer.close()">Close</button>',
    });
  },
  loadAtmProfile: async function(atmId) {
    try {
      $("inv-atm-profile-content").innerHTML = '<div class="skeleton skeleton-card"></div>';
      var rd = State.riskScores.length ? State.riskScores : (await API.get("/risk-scores?horizon=24") || []);
      if (rd._forbidden) rd = [];
      var ad = await API.get("/alerts?atm_id="+encodeURIComponent(atmId)+"&limit=10");
      var atmRisk = rd.find(function(a){return a.atm_id===atmId;});
      var atmAlerts = ad._forbidden?[]:ad||[];
      var html = '';
      if (atmRisk) {
        html += '<div class="drawer-section"><div class="drawer-section-title">Risk Profile — next 24h</div>'+
          '<div class="drawer-kv"><span class="k">ATM</span><span class="v mono">'+esc(atmRisk.atm_id)+'</span></div>'+
          '<div class="drawer-kv"><span class="k">Bank</span><span class="v">'+esc(atmRisk.bank_name)+'</span></div>'+
          '<div class="drawer-kv"><span class="k">City</span><span class="v">'+esc(atmRisk.city)+'</span></div>'+
          '<div class="drawer-kv"><span class="k">Risk</span><span class="v">'+riskChip(atmRisk.risk_score, true)+'</span></div>'+
          '<div class="drawer-kv"><span class="k">Level</span><span class="v">'+levelChip(atmRisk.risk_level)+'</span></div></div>';
      }
      if (atmAlerts.length) {
        html += '<div class="drawer-section"><div class="drawer-section-title">Alerts ('+atmAlerts.length+')</div>';
        atmAlerts.forEach(function(a){
          html += '<div class="drawer-kv"><span class="k mono">'+shortId(a.alert_id)+'</span><span class="v">'+statusChip(a.status)+' '+riskChip(a.risk_score)+'</span></div>';
        });
        html += '</div>';
      }
      if (!html) html = emptyState("search","No data for this ATM","No risk record or alerts found for \""+atmId+"\" in your jurisdiction. Check the ID (format ATM-XXX0000).");
      $("inv-atm-profile-content").innerHTML = html;
    } catch(e) { $("inv-atm-profile-content").innerHTML = '<div class="error-banner"><span class="error-banner-icon"><span class="lucide lucide-x-circle"></span></span><div class="error-banner-text"><div class="error-banner-title">Load Failed</div><div class="error-banner-msg">'+esc(e.message)+'</div></div></div>'; }
  },
  loadMoneyTrail: async function(accountToken) {
    try {
      $("money-trail-output").innerHTML = '<div class="skeleton skeleton-card"></div>';
      var data = await API.get("/mule-graph/trail/"+encodeURIComponent(accountToken));
      if (data._forbidden) { Toast.warning("Access Denied","Insufficient permissions."); return; }
      if (!data || (!(data.chains||[]).length && !(data.edges||[]).length)) {
        $("money-trail-output").innerHTML = emptyState("network","No trail found","No money trail for this account token in the lookback window.");
        return;
      }
      var html = '<div style="padding:16px;width:100%"><div style="font-size:13px;color:var(--text-secondary);margin-bottom:12px">Account: <span class="mono">'+esc(data.account_token)+'</span> | Window: '+(data.window_days||30)+'d</div>';
      (data.chains||[]).forEach(function(chain,i){
        html += '<div style="margin-bottom:16px;padding:12px;background:var(--bg-elevated);border-radius:var(--radius-md);border:1px solid var(--border-subtle)">';
        html += '<div style="font-size:12px;font-weight:700;color:var(--accent-gold);margin-bottom:8px">Chain '+(i+1)+' — Risk: '+((chain.total_risk||0)*100).toFixed(1)+'%</div>';
        (chain.nodes||[]).forEach(function(node,j){
          html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px"><span style="font-size:11px;color:var(--text-muted)">'+(j+1)+'.</span><span class="mono" style="font-size:12px">'+esc(node.id||node.account_token||"--")+'</span><span class="chip chip-'+(node.type==="victim"?"info":node.type==="atm"?"high":"medium")+'" style="font-size:10px">'+esc(node.type||"--")+'</span></div>';
        });
        html += '</div>';
      });
      html += '</div>';
      $("money-trail-output").innerHTML = html;
    } catch(e) { Toast.error("Load Failed",e.message); }
  },
  loadEvidence: async function(alertId) {
    try {
      $("evidence-output").innerHTML = '<div class="skeleton skeleton-card"></div>';
      var data = await API.get("/alerts/"+encodeURIComponent(alertId)+"/evidence");
      if (data._forbidden) { Toast.warning("Access Denied","Insufficient permissions."); return; }
      $("evidence-output").innerHTML = Evidence.render(data);
    } catch(e) { Toast.error("Load Failed",e.message); }
  },
};

/* ═══ VIEW: MULE NETWORK ═══ */
var MuleNetwork = {
  canvasCtx: null,
  nodes: [],
  edges: [],
  load: async function() {
    this.initCanvas();
    await this.loadTerminalNodes();
  },
  initCanvas: function() {
    var canvas = $("mule-canvas");
    if (!canvas) return;
    var p = canvas.parentElement;
    canvas.width = p.clientWidth; canvas.height = p.clientHeight;
    this.canvasCtx = canvas.getContext("2d");
    this.canvasCtx.fillStyle = "#050B14"; this.canvasCtx.fillRect(0,0,canvas.width,canvas.height);
    this.canvasCtx.fillStyle = "#9AABC4"; this.canvasCtx.font = "14px Inter, sans-serif";
    this.canvasCtx.textAlign = "center";
    this.canvasCtx.fillText('Click "Load Network" to visualize mule connections', canvas.width/2, canvas.height/2);
  },
  loadNetwork: async function(atmId, depth) {
    var url = "/graph/mule-network?depth="+(depth||2)+"&limit=200";
    if (atmId) url += "&atm_id="+encodeURIComponent(atmId);
    try {
      var data = await API.get(url);
      if (data._forbidden) { Toast.warning("Access Denied","Insufficient permissions."); return; }
      if (!data||(!(data.nodes||[]).length&&!(data.edges||[]).length)) {
        Toast.info("No Data","No mule network data found for this query."); return;
      }
      this.nodes = data.nodes||[]; this.edges = data.edges||[];
      this.renderGraph();
    } catch(e) { Toast.error("Load Failed",e.message); }
  },
  renderGraph: function() {
    var canvas = $("mule-canvas"); if (!canvas||!this.canvasCtx) return;
    var ctx = this.canvasCtx, W = canvas.width, H = canvas.height;
    ctx.clearRect(0,0,W,H); ctx.fillStyle = "#050B14"; ctx.fillRect(0,0,W,H);
    if (!this.nodes.length) { ctx.fillStyle="#9AABC4";ctx.font="14px Inter";ctx.textAlign="center";ctx.fillText("No network data",W/2,H/2);return; }
    var pos = {};
    var self = this;
    this.nodes.forEach(function(n,i){
      var angle = (i/MuleNetwork.nodes.length)*2*Math.PI;
      var r = Math.min(W,H)*0.35;
      pos[n.id||n.account_token] = {x:W/2+Math.cos(angle)*r*(0.5+Math.random()*0.5), y:H/2+Math.sin(angle)*r*(0.5+Math.random()*0.5)};
    });
    ctx.strokeStyle = "#223354"; ctx.lineWidth = 1.5;
    this.edges.forEach(function(e){
      var f=pos[e.from||e.source], t=pos[e.to||e.target];
      if(f&&t){ctx.beginPath();ctx.moveTo(f.x,f.y);ctx.lineTo(t.x,t.y);ctx.stroke();}
    });
    function colorFor(risk){ return risk>=0.85?"#FF4757":risk>=0.7?"#FF7A45":risk>=0.4?"#FFB454":"#2EE6A6"; }
    this.nodes.forEach(function(n){
      var id=n.id||n.account_token, p=pos[id]; if(!p)return;
      var risk=n.risk||n.terminal_risk||0;
      var r=risk>=0.85?10:risk>=0.7?8:6;
      ctx.beginPath();ctx.arc(p.x,p.y,r,0,Math.PI*2);ctx.fillStyle=colorFor(risk);ctx.fill();
      ctx.strokeStyle="rgba(255,255,255,0.2)";ctx.lineWidth=2;ctx.stroke();
      ctx.fillStyle="#F2F6FC";ctx.font="10px Inter";ctx.textAlign="center";ctx.fillText(id.slice(-8),p.x,p.y+r+14);
    });
  },
  loadTerminalNodes: async function() {
    try {
      var data = await API.get("/mule-graph/terminal-nodes?k=20");
      if (data._forbidden) { $("mule-terminal-table").innerHTML='<tr><td colspan="3" class="table-empty">Access restricted.</td></tr>';return; }
      var nodes = data&&data.nodes||data||[];
      var tbody = $("mule-terminal-table");
      if (!nodes.length) { tbody.innerHTML='<tr><td colspan="3" class="table-empty">No terminal nodes in the lookback window.</td></tr>';return; }
      tbody.innerHTML = nodes.map(function(n){
        return '<tr>'+
          td('<span class="mono">'+esc(n.account_token)+'</span>','Account Token')+
          td(riskChip(n.terminal_risk, true),'Terminal Risk')+
          td('<button class="btn btn-ghost btn-sm" onclick="Investigations.loadMoneyTrail(\''+esc(n.account_token)+'\');switchView(\'investigations\')">Trace</button>','','no-label')+
        '</tr>';
      }).join("");
    } catch(e) { $("mule-terminal-table").innerHTML='<tr><td colspan="3" class="table-empty">Failed to load terminal nodes.</td></tr>'; }
  },
};

/* ═══ VIEW: MODEL HEALTH ═══ */
var ModelHealth = {
  load: async function() { await Promise.all([this.loadMetrics(),this.loadDrift()]); },
  loadMetrics: async function() {
    try {
      var d = await API.get("/metrics/current");
      if (!d || d.error) { return; }
      var m = d.current_headline_metrics || {};
      var g = d.generalization_current && d.generalization_current.split || {};
      var b = d.baseline_superiority_current || {};
      var p = d.dispatch_threshold_operating_point || {};
      var s = d.statistical_confidence_current && d.statistical_confidence_current.cv_5fold || {};

      if(m.roc_auc!=null)$("m-roc-auc").textContent=m.roc_auc.toFixed(4);
      if(m.precision_at_20!=null)$("m-prec-20").textContent=m.precision_at_20.toFixed(2);
      if(m.precision_at_100!=null)$("m-prec-100").textContent=m.precision_at_100.toFixed(2);
      if(m.recall_at_100!=null)$("m-rec-100").textContent=m.recall_at_100.toFixed(4);
      if(m.brier_score!=null)$("m-brier").textContent=m.brier_score.toFixed(4);
      if(m.lead_time_median_hours!=null)$("m-lead-time").textContent=m.lead_time_median_hours.toFixed(1)+"h";
      if(s.mean_auc!=null)$("m-cv-auc").textContent=s.mean_auc.toFixed(4);
      if(s.ci_95)$("m-ci").textContent="["+s.ci_95[0].toFixed(4)+", "+s.ci_95[1].toFixed(4)+"]";

      var tf = g.time_forward || {};
      if(tf.roc_auc!=null)$("m-tf-auc").textContent=tf.roc_auc.toFixed(4);
      var ca = g.cold_atm || {};
      if(ca.roc_auc!=null)$("m-cold-atm").textContent=ca.roc_auc.toFixed(4);
      var nh = g.new_hotspot || {};
      if(nh.roc_auc!=null)$("m-new-hotspot").textContent=nh.roc_auc.toFixed(4);

      if(dp.precision!=null)$("m-disp-prec").textContent=(dp.precision*100).toFixed(0)+"%";
      if(dp.alerts!=null)$("m-disp-alerts").textContent=dp.alerts;

      // Baseline comparison bars (P3) — live from canonical metrics, never hardcoded.
      // CashGuard's bar is full width; each baseline renders at 100/lift % of it.
      var cg = b.cashguard_p_at_100;
      var rows = [
        { id: "b-val-random", note: "b-note-random", lift: b.cashguard_vs_random_precision_at_100_lift },
        { id: "b-val-hist", note: "b-note-hist", lift: b.cashguard_vs_historical_hotspot_precision_at_100_lift },
        { id: "b-val-compvol", note: null, lift: b.cashguard_vs_complaint_volume_precision_at_100_lift },
        { id: "b-val-prox", note: null, lift: b.cashguard_vs_proximity_precision_at_100_lift },
      ];
      rows.forEach(function(r){
        var el = $(r.id); if (!el || r.lift == null) return;
        el.textContent = r.lift.toFixed(1) + "×";
        var track = el.parentElement.querySelector(".b-fill");
        if (track) track.style.width = Math.max(5, Math.min(100, 100 / r.lift)).toFixed(1) + "%";
        if (r.note) { var ne = $(r.note); if (ne) ne.textContent = r.lift.toFixed(1); }
      });

      var fi = d.feature_importances || {};
      if (Object.keys(fi).length) {
        var sorted = Object.entries(fi).sort(function(a,b){return Math.abs(b[1])-Math.abs(a[1]);}).slice(0,10);
        var maxAbs = Math.max.apply(null, sorted.map(function(pr){return Math.abs(pr[1]);}));
        var html = '';
        sorted.forEach(function(pr){
          var name = pr[0], val = pr[1];
          var pct = maxAbs > 0 ? (Math.abs(val)/maxAbs*100) : 0;
          var cls = val >= 0 ? 'positive' : 'negative';
          html += '<div class="feature-bar"><span class="feature-bar-name">' + esc(name) + '</span><div class="feature-bar-track"><div class="feature-bar-fill ' + cls + '" style="width:' + pct.toFixed(0) + '%"></div></div><span class="feature-bar-value">' + val.toFixed(3) + '</span></div>';
        });
        $("feature-impact-bars").innerHTML = html;
      } else {
        $("feature-impact-bars").innerHTML = emptyState("bar-chart-2","No feature importances","Run scripts/train_model.py to generate per-feature AUCs.");
      }
    } catch(e){ /* Metrics load failed */ }
  },
  loadDrift: async function() {
    try {
      var data = await API.get("/drift/status");
      if (data._forbidden) { $("drift-status-content").innerHTML=emptyState("lock","Access Restricted","Drift monitoring requires I4C_ADMIN or police roles.");return; }
      if (!data||data.status==="PENDING_REFERENCE"||data.status==="missing") {
        $("drift-status-content").innerHTML=emptyState("radar","No reference snapshot","Capture a reference snapshot to enable drift monitoring.", '<button class="btn btn-primary btn-sm" onclick="ModelHealth.captureReference()">Capture Reference</button>');
        return;
      }
      var features = data.features||data;
      if (typeof features==="object"&&!Array.isArray(features)) {
        var html='<div style="display:flex;flex-direction:column;gap:6px">';
        Object.entries(features).forEach(function(pair){
          var k=pair[0],v=pair[1];
          var psi=typeof v==="object"?v.psi:v;
          var status=typeof v==="object"?v.status:(psi>0.2?"red":psi>0.1?"yellow":"green");
          var cls=status==="red"?"drift-crit":status==="yellow"?"drift-warn":"drift-ok";
          var icon=status==="green"?'<span class="lucide lucide-check-circle"></span>':status==="yellow"?'<span class="lucide lucide-alert-triangle"></span>':'<span class="lucide lucide-x-circle"></span>';
          html+='<div class="drawer-kv"><span class="k mono">'+esc(k)+'</span><span class="v '+cls+'">'+(typeof psi==="number"?psi.toFixed(4):esc(String(psi)))+' '+icon+'</span></div>';
        });
        html+='</div>';
        $("drift-status-content").innerHTML=html;
      } else {
        $("drift-status-content").innerHTML='<div class="table-empty">Drift data available</div>';
      }
    } catch(e) { $("drift-status-content").innerHTML='<div class="table-empty">Failed to load drift data.</div>'; }
  },
  captureReference: async function() {
    try {
      var r = await API.post("/drift/capture-reference",{});
      if (r._forbidden) { Toast.warning("Access Denied","I4C_ADMIN role required.");return; }
      Toast.success("Reference Captured","Drift reference snapshot created.");
      this.loadDrift();
    } catch(e) { Toast.error("Capture Failed",e.message); }
  },
};

/* ═══ VIEW: AUDIT TRAIL (LEDGER) ═══ */
var Ledger = {
  load: async function() { await Promise.all([this.loadEntries(),this.verify()]); },
  loadEntries: async function() {
    try {
      var offset = State.ledger.page * 30;
      var data = await API.get("/ledger?limit=30&offset=" + offset);
      if (data._forbidden) { $("ledger-entries").innerHTML='<div class="table-empty">Ledger is restricted for the BANK role.</div>';return; }
      State.ledger.entries=data&&data.records||[]; State.ledger.total=data&&data.total||0;
      this.render();
    } catch(e) { $("ledger-entries").innerHTML='<div class="table-empty">Failed to load ledger.</div>'; }
  },
  render: function() {
    var entries=State.ledger.entries, container=$("ledger-entries");
    $("ledger-total-entries").textContent=fmtNum(State.ledger.total);
    var totalPages = Math.max(1, Math.ceil(State.ledger.total / 30));
    $("ledger-page-info").textContent = "Page " + (State.ledger.page + 1) + " of " + totalPages;
    $("btn-ledger-prev").disabled = State.ledger.page <= 0;
    $("btn-ledger-next").disabled = State.ledger.page >= totalPages - 1;
    if (!entries.length) { container.innerHTML='<div class="table-empty">No ledger entries.</div>';return; }
    container.innerHTML=entries.map(function(e){
      return '<div class="ledger-block"><span class="ledger-idx">#'+e.index+'</span><span class="ledger-actor">'+esc(e.actor)+'</span><span style="color:var(--accent-gold);font-weight:600;font-size:11px">'+esc(e.event_type)+'</span><span class="ledger-hash">'+esc(e.entity_id||e.payload_hash||"--")+'</span><span class="ledger-time">'+fmtDate(e.created_at)+'</span></div>';
    }).join("");
  },
  verify: async function() {
    try {
      var data = await API.get("/ledger/verify");
      if (data._forbidden) { $("ledger-chain-status").textContent="Restricted";$("ledger-verify-result").textContent="--";return; }
      // Backend key is `intact` (not `valid`)
      var intact = !!(data && (data.intact || data.valid));
      $("ledger-chain-status").textContent=intact?"INTACT":"TAMPERED";
      $("ledger-chain-status").className="stat-value "+(intact?"low":"critical");
      $("ledger-verify-result").textContent=intact?"PASSED":"FAILED";
      $("ledger-verify-result").className="stat-value "+(intact?"low":"critical");
      return intact;
    } catch(e) { $("ledger-chain-status").textContent="Error"; }
  },
};

/* ═══ REPORTS ═══ */
var Reports = {
  load: async function() { await this.loadHotspots(); },
  generateSituational: async function() {
    try {
      var data = await API.post("/reports/situational");
      if (data._forbidden) { Toast.warning("Access Denied","I4C_ADMIN role required.");return; }
      var o = $("report-output"); o.style.display="";
      o.innerHTML='<h3>Situational Report</h3><p>Report generated successfully.</p>'+
        '<div class="drawer-kv"><span class="k">Report ID</span><span class="v mono">'+esc(data.report_id||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Ledger Hash</span><span class="v mono" style="font-size:11px">'+esc(data.ledger_hash||"--")+'</span></div>'+
        (data.pdf?'<a href="/reports/'+data.report_id+'/download" target="_blank" class="btn btn-primary btn-sm" style="margin-top:12px">Download PDF</a>':'');
      Toast.success("Report Generated","Situational report created and anchored to ledger.");
    } catch(e) { Toast.error("Generation Failed",e.message); }
  },
  loadHotspots: async function() {
    try {
      var data = await API.get("/hotspots?k=20");
      if (data._forbidden) { Toast.warning("Access Denied","Insufficient permissions.");return; }
      var o = $("hotspot-output");
      if (!data||!data.length) { o.innerHTML=emptyState("flame","No Hotspots","No high-risk ATMs in scope.");return; }
      var html='<div class="table-wrap"><table><thead><tr><th>ATM</th><th>City</th><th>District</th><th>Risk</th><th>Level</th></tr></thead><tbody>';
      data.forEach(function(h){
        html+='<tr>'+
          td('<span class="mono">'+esc(h.atm_id)+'</span>','ATM')+
          td(esc(h.city),'City')+
          td(esc(h.district),'District')+
          td(riskChip(h.risk_score, true),'Risk')+
          td(levelChip(h.risk_level),'Level')+
        '</tr>';
      });
      html+='</tbody></table></div>'; o.innerHTML=html;
    } catch(e) { Toast.error("Load Failed",e.message); }
  },
  generateCity: async function() {
    var city = $("city-report-input").value.trim();
    if (!city) { Toast.warning("Input Required","Enter a city name.");return; }
    try {
      var data = await API.get("/reports/city?city="+encodeURIComponent(city));
      if (data._forbidden) { Toast.warning("Access Denied","Insufficient permissions.");return; }
      var o = $("city-report-output"); o.style.display="";
      if (typeof data==="string") { o.textContent=data; }
      else {
        var html = '<h3>City Report: '+esc(city)+'</h3>';
        html += '<div class="drawer-kv"><span class="k">Complaints 24h / 7d</span><span class="v mono">'+fmtNum(data.complaints_24h)+' / '+fmtNum(data.complaints_7d)+'</span></div>';
        html += '<div class="drawer-kv"><span class="k">ATMs scored</span><span class="v mono">'+fmtNum(data.atms_scored)+'</span></div>';
        html += '<div class="drawer-kv"><span class="k">High-risk ATMs</span><span class="v mono">'+fmtNum(data.high_risk_atms)+'</span></div>';
        html += '<div class="drawer-kv"><span class="k">Open alerts</span><span class="v mono">'+fmtNum((data.open_alerts||[]).length)+'</span></div>';
        if (data.methodology_note) html += '<p style="font-size:11px;color:var(--text-muted);margin-top:10px">'+esc(data.methodology_note)+'</p>';
        o.innerHTML = html;
      }
    } catch(e) { Toast.error("Generation Failed",e.message); }
  },
};

/* ═══ SCRIPTED SIMULATION (labeling preserved verbatim) ═══ */
var Simulation = {
  load: async function() {
    if (State.replay) Replay.exit();
    try {
      var data = await API.get("/simulated/scenario");
      if (data._forbidden) { Toast.warning("Access Denied","Insufficient permissions.");return; }
      State.simulation=true; State.simulationData=data;
      $("sim-banner").classList.add("active"); $("sim-watermark").classList.add("active");
      $("sim-banner-text").textContent=data.scenario||"Simulated scenario loaded";
      Toast.info("Simulation Loaded","Simulated scenario data is now active. All data is synthetic.");
      Overview.load();
    } catch(e) { Toast.error("Simulation Failed",e.message); }
  },
  exit: function() {
    State.simulation=false; State.simulationData=null;
    $("sim-banner").classList.remove("active"); $("sim-watermark").classList.remove("active");
    Toast.info("Simulation Exited","Returned to live data mode."); Overview.load();
  },
};

/* ═══ SETUP & EVENT BINDING ═══ */
function setupUI() {
  document.addEventListener("keydown", function(e) {
    if (e.key === "Escape") {
      if ($("modal-overlay")?.classList.contains("active")) { Modal.hide(); return; }
      if ($("drawer")?.classList.contains("open")) { Drawer.close(); return; }
    }
  });
  $("login-form").addEventListener("submit", async function(e) {
    e.preventDefault();
    var btn=$("btn-login"), err=$("login-error");
    btn.disabled=true; btn.textContent="Authenticating…"; err.textContent="";
    try { await Auth.login($("login-username").value.trim(),$("login-password").value); enterApp(); }
    catch(ex) { err.textContent=ex.message||"Authentication failed"; }
    finally { btn.disabled=false; btn.textContent="Authenticate"; }
  });

  document.querySelectorAll(".nav-item[data-view]").forEach(function(item){
    item.addEventListener("click",function(){ switchView(item.dataset.view); });
    item.addEventListener("keydown",function(e){ if(e.key==="Enter"||e.key===" "){e.preventDefault();switchView(item.dataset.view);} });
  });

  $("sidebar-toggle").addEventListener("click",function(){
    State.sidebarCollapsed=!State.sidebarCollapsed;
    $("app-shell").classList.toggle("sidebar-collapsed",State.sidebarCollapsed);
  });

  $("mobile-menu-btn")?.addEventListener("click",function(){
    $("sidebar").classList.add("mobile-open"); $("sidebar-overlay").classList.add("active");
  });
  $("sidebar-overlay")?.addEventListener("click",function(){
    $("sidebar").classList.remove("mobile-open"); $("sidebar-overlay").classList.remove("active");
  });

  $("btn-logout").addEventListener("click",function(){ Auth.logout(); Toast.info("Signed Out","Session ended."); });
  $("drawer-close").addEventListener("click",function(){ Drawer.close(); });
  $("drawer-overlay").addEventListener("click",function(){ Drawer.close(); });
  $("modal-close")?.addEventListener("click",function(){ Modal.hide(); });

  $("risk-horizon").addEventListener("change",function(){ Risk.loadScores(); });
  $("risk-city-filter").addEventListener("change",function(){ Risk.loadScores(); });
  $("risk-bank-filter")?.addEventListener("change",function(){ Risk.loadScores(); });
  $("risk-level-filter")?.addEventListener("change",function(){ Risk.loadScores(); });
  $("alerts-status-filter").addEventListener("change",function(){ Alerts.load(); });

  var runAlerts = async function() {
    await withLoading("btn-run-alerts", async function() {
      try {
        var r = await API.post("/alerts/run-now");
        if (r._forbidden) { Toast.warning("Access Denied","Insufficient permissions.");return; }
        var s = r.summary || {};
        Toast.success("Alert Cycle Complete","Checked "+fmtNum(s.checked)+" · flagged "+fmtNum(s.flagged)+" · created "+fmtNum(s.created)+" · re-observed "+fmtNum(s.reobserved||0));
        Alerts.load(); updateBadge(); ModelStatus.load();
      } catch(e) { Toast.error("Alert Cycle Failed",e.message); }
    });
  };
  $("btn-run-alerts").addEventListener("click",runAlerts);
  $("btn-run-alerts-2").addEventListener("click",runAlerts);

  $("investigation-search")?.addEventListener("input",function(e){ Investigations.renderComplaints(e.target.value); });
  $("btn-load-atm-profile")?.addEventListener("click",function(){ var id=$("inv-atm-id-input").value.trim();if(id)Investigations.loadAtmProfile(id); });
  $("btn-load-trail")?.addEventListener("click",function(){ var id=$("inv-account-input").value.trim();if(id)Investigations.loadMoneyTrail(id); });
  $("btn-load-evidence")?.addEventListener("click",function(){ var id=$("inv-evidence-alert-id").value.trim();if(id)Investigations.loadEvidence(id); });

  $("btn-load-mule")?.addEventListener("click",function(){
    MuleNetwork.loadNetwork($("mule-atm-id").value.trim(),$("mule-depth").value);
  });

  $("btn-retrain")?.addEventListener("click",async function(){
    try {
      $("train-status").textContent="Retraining…";
      var r = await API.post("/train?days_back=30");
      if (r._forbidden) { Toast.warning("Access Denied","I4C_ADMIN role required.");$("train-status").textContent="";return; }
      Toast.success("Retraining Complete",r.message||"Model updated.");
      $("train-status").textContent=r.message||"Done"; ModelHealth.loadMetrics();
    } catch(e) { Toast.error("Retraining Failed",e.message);$("train-status").textContent="Failed"; }
  });

  $("btn-ledger-verify")?.addEventListener("click",function(){ Ledger.verify(); });
  $("btn-ledger-prev")?.addEventListener("click",function(){ if(State.ledger.page>0){State.ledger.page--;Ledger.loadEntries();} });
  $("btn-ledger-next")?.addEventListener("click",function(){ var totalPages=Math.ceil(State.ledger.total/30); if(State.ledger.page<totalPages-1){State.ledger.page++;Ledger.loadEntries();} });

  $("btn-sit-report")?.addEventListener("click",function(){ withLoading("btn-sit-report",function(){ Reports.generateSituational(); }); });
  $("btn-hotspot-report")?.addEventListener("click",function(){ withLoading("btn-hotspot-report",function(){ Reports.loadHotspots(); }); });
  $("btn-city-report")?.addEventListener("click",function(){ withLoading("btn-city-report",function(){ Reports.generateCity(); }); });

  document.querySelectorAll(".tab-bar").forEach(function(bar){
    bar.querySelectorAll(".tab-item[data-tab]").forEach(function(tab){
      tab.addEventListener("click",function(){
        bar.querySelectorAll(".tab-item").forEach(function(t){t.classList.remove("active");});
        tab.classList.add("active");
        var target=tab.dataset.tab;
        var parent=bar.parentElement;
        parent.querySelectorAll(":scope > .tab-content").forEach(function(tc){
          tc.classList.toggle("active",tc.id===target);
        });
      });
    });
  });

  $("btn-sim-toggle")?.addEventListener("click",function(){ if(State.simulation)Simulation.exit();else Simulation.load(); });
  $("btn-sim-exit")?.addEventListener("click",function(){ Simulation.exit(); });

  $("btn-replay-day")?.addEventListener("click",function(){ Replay.openPicker(); });
  $("btn-replay-day-top")?.addEventListener("click",function(){ Replay.openPicker(); });
  $("btn-replay-exit")?.addEventListener("click",function(){ Replay.exit(); });

  $("btn-notifications")?.addEventListener("click",function(){
    if (State.alerts.length) {
      Drawer.open({
        title:"Notifications",
        body: State.alerts.slice(0,10).map(function(a){
          return '<div style="padding:8px 0;border-bottom:1px solid var(--border-subtle);cursor:pointer" onclick="Alerts.openDetail(\''+esc(a.alert_id)+'\');Drawer.close()">'+
            '<div style="display:flex;align-items:center;gap:8px"><span class="status-dot '+(a.risk_score>=0.7?"critical":"medium")+'"></span>'+
            '<div style="flex:1"><div style="font-size:12px;font-weight:600">'+esc(a.atm_id)+' — '+riskChip(a.risk_score)+'</div>'+
            '<div style="font-size:11px;color:var(--text-muted)">'+esc(a.city||"--")+' | '+fmtDate(a.created_at)+'</div></div>'+
            statusChip(a.status)+'</div></div>';
        }).join("") || '<div class="table-empty">No notifications</div>',
      });
    } else { Toast.info("Notifications","No active notifications."); }
  });
}

function enterApp() {
  $("login-page").style.display="none"; $("app-shell").classList.add("active");
  var user = State.user;
  if (user) {
    $("user-display-name").textContent=user.display_name||user.username;
    $("user-role-text").textContent=(user.role||"").replace(/_/g," ");
    $("user-avatar").textContent=(user.username||"A").charAt(0).toUpperCase();
    var roleMap={"I4C_ADMIN":"I4C Admin","POLICE_STATE":"State Police","POLICE_DISTRICT":"District Police","BANK":"Bank Officer"};
    $("topbar-role-name").textContent=roleMap[user.role]||user.role;
    // P2: scope permanently visible in the header, e.g. "District Police — Northsagar only"
    var scopeMap = {
      "I4C_ADMIN": "National",
      "POLICE_STATE": (user.scope || "") + " only",
      "POLICE_DISTRICT": (user.scope || "") + " only",
      "BANK": (user.scope || "") + " only",
    };
    $("topbar-role-scope").textContent = scopeMap[user.role] || (user.scope || "");
  }
  document.querySelectorAll(".nav-item[data-view]").forEach(function(item){
    item.style.display = Auth.canAccess(item.dataset.view) ? "" : "none";
  });
  Overview.load();
  connectWS();
  updateBadge();
}

/* ── Init ──────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", function() {
  setupUI();
  if (State.token && State.user) {
    enterApp();
  } else {
    document.querySelectorAll(".nav-item[data-view]").forEach(function(item){
      item.style.display = Auth.canAccess(item.dataset.view) ? "" : "none";
    });
  }
  // Command-center cadence: silent refresh of the overview + badge every 60 s.
  setInterval(function() {
    if (!State.token || !State.user) return;
    if (State.view === "overview" && !State.replay && !State.simulation) Overview.load();
    else updateBadge();
  }, 60000);
});
