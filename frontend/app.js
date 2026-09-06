/* CashGuard AI — Frontend Application v3.0 */
"use strict";

const State = {
  token: localStorage.getItem("cg_token") || null,
  user: JSON.parse(localStorage.getItem("cg_user") || "null"),
  view: "overview",
  sidebarCollapsed: false,
  simulation: false,
  simulationData: null,
  riskScores: [],
  alerts: [],
  stats: null,
  recovery: [],
  ledger: { entries: [], total: 0, page: 0 },
  muleNetwork: null,
  mapController: null,
  ws: null,
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
    if (State.ws) try { State.ws.close(); } catch(e) {}
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

/* ── Toast ─────────────────────────────────────────────────── */
const Toast = {
  show(title, msg, type, dur) {
    type = type || "info"; dur = dur || 4000;
    const c = $("toast-container");
    const icons = { success: "\u2713", error: "\u2717", warning: "\u26A0", info: "\u2139" };
    const el = document.createElement("div");
    el.className = "toast " + type;
    el.innerHTML = '<span class="toast-icon">' + (icons[type]||icons.info) + '</span>' +
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

/* ── Modal ─────────────────────────────────────────────────── */
const Modal = {
  show(cfg) {
    $("modal-title").textContent = cfg.title || "Confirm";
    $("modal-body").innerHTML = cfg.body || "";
    $("modal-footer").innerHTML = cfg.footer || "";
    $("modal-overlay").classList.add("active");
    $("modal-close").onclick = function() { Modal.hide(); };
    $("modal-overlay").onclick = function(e) { if (e.target.id === "modal-overlay") Modal.hide(); };
  },
  hide() { $("modal-overlay").classList.remove("active"); },
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

/* ── Drawer ─────────────────────────────────────────────────── */
const Drawer = {
  open(cfg) {
    $("drawer-title").textContent = cfg.title || "Details";
    $("drawer-body").innerHTML = cfg.body || "";
    $("drawer-footer").innerHTML = cfg.footer || "";
    $("drawer-overlay").classList.add("active");
    $("drawer").classList.add("open");
  },
  close() {
    $("drawer-overlay").classList.remove("active");
    $("drawer").classList.remove("open");
  }
};

function $(id) { return document.getElementById(id); }
function esc(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
function shortId(id) { return id ? id.slice(-8) : "--"; }
function fmtDate(iso) {
  if (!iso) return "--";
  var d = new Date(iso);
  return d.toLocaleDateString("en-IN",{day:"2-digit",month:"short"}) + " " +
         d.toLocaleTimeString("en-IN",{hour:"2-digit",minute:"2-digit",hour12:false});
}
function fmtNum(n) { return n != null ? n.toLocaleString("en-IN") : "--"; }
function riskChip(score) {
  var lvl = score >= 0.7 ? "critical" : score >= 0.5 ? "high" : score >= 0.3 ? "medium" : "low";
  return '<span class="chip chip-' + lvl + '">' + (score*100).toFixed(1) + '%</span>';
}
function statusChip(s) {
  var m = {new:"chip-critical",actioned:"chip-high",dispatched:"chip-medium",
    dismissed:"chip-info",resolved:"chip-low",flagged:"chip-critical",
    hold_placed:"chip-high",recovered:"chip-low",recovery_failed:"chip-critical"};
  return '<span class="chip '+(m[s]||"chip-info")+'">'+esc(s)+'</span>';
}
function tierChip(t) {
  var m = {dispatch:"dispatch",action:"action",monitor:"monitor"};
  return '<span class="alert-tier '+(m[t]||"monitor")+'">'+esc(t||"monitor")+'</span>';
}

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
  $("breadcrumb").innerHTML = "<strong>" + (titles[view]||view) + "</strong>";
  switch(view) {
    case "overview": Overview.load(); break;
    case "risk": Risk.load(); break;
    case "alerts": Alerts.load(); break;
    case "recovery": Recovery.load(); break;
    case "investigations": Investigations.load(); break;
    case "mule-network": MuleNetwork.load(); break;
    case "model-health": ModelHealth.load(); break;
    case "ledger": Ledger.load(); break;
  }
}

/* ── MapController ─────────────────────────────────────────── */
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
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: "&copy; CARTO", subdomains: "abcd", maxZoom: 19,
    }).addTo(this.map);
  } catch(e) {
    el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted)">Map unavailable</div>';
  }
};
MapCtrl.prototype.clearMarkers = function() {
  var self = this;
  this.markers.forEach(function(m) { if (self.map) self.map.removeLayer(m); });
  this.markers = [];
};
MapCtrl.prototype.addMarker = function(lat, lng, opts) {
  if (!this.map || lat == null || lng == null) return null;
  opts = opts || {};
  var score = opts.risk || 0;
  var color = score >= 0.7 ? "#EF4444" : score >= 0.5 ? "#F59E0B" : score >= 0.3 ? "#3B82F6" : "#22C55E";
  var radius = score >= 0.7 ? 10 : score >= 0.5 ? 8 : 6;
  var m = L.circleMarker([lat, lng], {
    radius: radius, fillColor: color, fillOpacity: 0.85,
    color: color, weight: 2, opacity: 0.9,
  }).addTo(this.map);
  if (opts.popup) m.bindPopup(opts.popup, { maxWidth: 280 });
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
  var hd = data.filter(function(d){return d.latitude&&d.longitude;}).map(function(d){return [d.latitude,d.longitude,d.risk_score||0.5];});
  if (hd.length) {
    L.heatLayer(hd, {radius:25,blur:15,maxZoom:10,max:1.0,
      gradient:{0.2:"#22C55E",0.4:"#3B82F6",0.6:"#F59E0B",0.8:"#EF4444",1.0:"#FF0000"}
    }).addTo(this.map);
  }
};

/* ── WebSocket ─────────────────────────────────────────────── */
function connectWS() {
  if (State.ws) try { State.ws.close(); } catch(e) {}
  var proto = location.protocol === "https:" ? "wss" : "ws";
  try {
    State.ws = new WebSocket(proto + "://" + location.host + "/ws/alerts");
    State.ws.onopen = function() { $("conn-status-text").textContent = "Connected"; };
    State.ws.onclose = function() { $("conn-status-text").textContent = "Reconnecting..."; setTimeout(connectWS, 3000); };
    State.ws.onerror = function() { $("conn-status-text").textContent = "Error"; };
    State.ws.onmessage = function(evt) {
      try {
        var msg = JSON.parse(evt.data);
        if (msg.type === "alert") {
          Toast.warning("New Alert", "ATM " + (msg.atm_id||"") + " — Risk: " + ((msg.risk_score||0)*100).toFixed(1) + "%");
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
    $("notif-dot").style.display = n > 0 ? "" : "none";
  } catch(e) {}
}

/* ═══ VIEW: OVERVIEW ═══ */
var Overview = {
  map: null,
  load: async function() {
    await Promise.all([this.loadStats(), this.loadMap(), this.loadAlerts()]);
  },
  loadStats: async function() {
    try {
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
      $("stat-alerts").textContent = fmtNum(s.active_alerts || s.total_alerts);
      $("stat-risk").textContent = fmtNum(s.high_risk_atms);
      $("stat-complaints-7d").textContent = fmtNum(s.complaints_7d);
      $("stat-fraud-7d").textContent = fmtNum(s.fraud_withdrawals_7d);
    } catch(e) { console.error("Stats:", e); }
  },
  loadMap: async function() {
    if (!this.map) { this.map = new MapCtrl("main-map"); this.map.init(); }
    this.map.resize();
    try {
      var data = State.simulation ? (State.simulationData||{}).risk_scores || [] : [];
      if (!data.length) {
        data = await API.get("/risk-scores?horizon=24");
        if (data._forbidden) data = [];
      }
      if (data.length) {
        this.map.clearMarkers();
        data.slice(0,200).forEach(function(a) {
          var pop = '<b>'+esc(a.atm_id)+'</b><br>'+esc(a.bank_name)+'<br>'+esc(a.city)+'<br>Risk: '+(a.risk_score*100).toFixed(1)+'%';
          Overview.map.addMarker(a.latitude, a.longitude, { risk: a.risk_score, popup: pop });
        });
        this.map.addHeat(data);
        this.map.fitBounds(data);
      }
    } catch(e) { console.error("Map:", e); }
  },
  loadAlerts: async function() {
    try {
      var alerts = await API.get("/alerts?limit=10&status=new");
      if (alerts._forbidden) {
        $("recent-alerts-list").innerHTML = '<div class="table-empty">Access restricted</div>';
        $("priority-actions").innerHTML = '<div class="empty-state"><div class="empty-icon">&#128274;</div><div class="empty-title">Access Restricted</div></div>';
        return;
      }
      State.alerts = alerts || [];
      if (!alerts.length) {
        $("recent-alerts-list").innerHTML = '<div class="table-empty">No active alerts</div>';
        $("priority-actions").innerHTML = '<div class="empty-state"><div class="empty-icon">&#10003;</div><div class="empty-title">All Clear</div><div class="empty-desc">No priority actions.</div></div>';
        return;
      }
      $("recent-alerts-list").innerHTML = alerts.slice(0,5).map(function(a){
        return '<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border-subtle);cursor:pointer" onclick="Alerts.openDetail(\''+esc(a.alert_id)+'\')">'+
          '<span class="status-dot '+(a.risk_score>=0.7?"critical":"medium")+'"></span>'+
          '<div style="flex:1;min-width:0"><div style="font-size:12px;font-weight:600" class="truncate">'+esc(a.atm_id)+'</div>'+
          '<div style="font-size:11px;color:var(--text-muted)">'+esc(a.city||"--")+'</div></div>'+
          riskChip(a.risk_score)+'</div>';
      }).join("");
      var crit = alerts.filter(function(a){return a.risk_score>=0.7&&a.status==="new";});
      if (crit.length) {
        $("priority-actions").innerHTML = crit.slice(0,3).map(function(a){
          return '<div style="padding:10px;background:var(--critical-bg);border:1px solid var(--critical-border);border-radius:var(--radius-md);margin-bottom:8px;cursor:pointer" onclick="Alerts.openDetail(\''+esc(a.alert_id)+'\')">'+
            '<div style="font-size:12px;font-weight:700;color:var(--critical);margin-bottom:2px">&#9888; '+esc(a.atm_id)+'</div>'+
            '<div style="font-size:11px;color:var(--text-secondary)">'+esc(a.recommended_action||"Investigate")+'</div></div>';
        }).join("");
      } else {
        $("priority-actions").innerHTML = '<div class="empty-state"><div class="empty-icon">&#10003;</div><div class="empty-title">All Clear</div></div>';
      }
    } catch(e) { console.error("Alerts:", e); }
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
    var url = "/risk-scores?horizon=" + horizon;
    if (city) url += "&city=" + encodeURIComponent(city);
    try {
      var data = await API.get(url);
      if (data._forbidden) { Toast.warning("Access Denied", "Your role cannot view risk scores."); return; }
      State.riskScores = data || [];
      this.render();
      this.renderMap();
    } catch(e) { Toast.error("Load Failed", e.message); }
  },
  render: function() {
    var data = State.riskScores;
    var c = {critical:0,high:0,medium:0,low:0};
    data.forEach(function(d){
      if(d.risk_score>=0.7)c.critical++;else if(d.risk_score>=0.5)c.high++;else if(d.risk_score>=0.3)c.medium++;else c.low++;
    });
    $("risk-total-atms").textContent = fmtNum(data.length);
    $("risk-critical-count").textContent = fmtNum(c.critical);
    $("risk-high-count").textContent = fmtNum(c.high);
    $("risk-medium-count").textContent = fmtNum(c.medium);
    $("risk-low-count").textContent = fmtNum(c.low);
    var cities = []; var seen = {};
    data.forEach(function(d){ if(d.city&&!seen[d.city]){seen[d.city]=1;cities.push(d.city);} });
    cities.sort();
    var cf = $("risk-city-filter"); var cur = cf.value;
    cf.innerHTML = '<option value="">All Cities</option>' + cities.map(function(c){return '<option value="'+esc(c)+'"'+(c===cur?' selected':'')+'>'+esc(c)+'</option>';}).join("");
    var tbody = $("risk-atm-table");
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="8" class="table-empty">No risk scores</td></tr>'; return; }
    tbody.innerHTML = data.slice(0,100).map(function(a){
      return '<tr><td class="mono">'+esc(a.atm_id)+'</td><td>'+esc(a.bank_name)+'</td><td>'+esc(a.city)+'</td><td>'+esc(a.district)+'</td><td>'+esc(a.state)+'</td><td>'+riskChip(a.risk_score)+'</td><td><span class="chip chip-'+(a.risk_level==="CRITICAL"?"critical":a.risk_level==="HIGH"?"high":"medium")+'">'+esc(a.risk_level)+'</span></td><td><button class="btn btn-ghost btn-sm" onclick="Risk.openDetail(\''+esc(a.atm_id)+'\')">Details</button></td></tr>';
    }).join("");
  },
  renderMap: function() {
    if (!this.map||!this.map.map) return;
    this.map.clearMarkers();
    State.riskScores.forEach(function(a){
      var pop = '<b>'+esc(a.atm_id)+'</b><br>'+esc(a.bank_name)+'<br>'+esc(a.city)+'<br>Risk: '+(a.risk_score*100).toFixed(1)+'%';
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
      body: '<div class="drawer-section"><div class="drawer-section-title">Location</div>'+
        '<div class="drawer-kv"><span class="k">Bank</span><span class="v">'+esc(atm.bank_name)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Branch</span><span class="v">'+esc(atm.branch_name)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">City</span><span class="v">'+esc(atm.city)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">District</span><span class="v">'+esc(atm.district)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">State</span><span class="v">'+esc(atm.state)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">PS Area</span><span class="v">'+esc(atm.police_station_area)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">PIN</span><span class="v">'+esc(atm.pin)+'</span></div></div>'+
        '<div class="drawer-section"><div class="drawer-section-title">Risk Assessment</div>'+
        '<div class="drawer-kv"><span class="k">Risk Score</span><span class="v">'+(atm.risk_score*100).toFixed(1)+'%</span></div>'+
        '<div class="drawer-kv"><span class="k">Emerging Risk</span><span class="v">'+(atm.emerging_risk!=null?(atm.emerging_risk*100).toFixed(1)+'%':'--')+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Intervention Priority</span><span class="v">'+(atm.intervention_priority!=null?(atm.intervention_priority*100).toFixed(1)+'%':'--')+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Risk Level</span><span class="v">'+riskChip(atm.risk_score)+' '+esc(atm.risk_level)+'</span></div>'+
        (atm.simulated?'<div class="drawer-kv"><span class="k">Source</span><span class="v"><span class="chip chip-gold">Simulated</span></span></div>':'')+'</div>',
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
      var data = await API.get(url);
      if (data._forbidden) { Toast.warning("Access Denied", "Your role cannot view alerts."); return; }
      State.alerts = data || [];
      this.render();
    } catch(e) { Toast.error("Load Failed", e.message); }
  },
  render: function() {
    var data = State.alerts;
    var tbody = $("alerts-full-table");
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="8" class="table-empty">No alerts found</td></tr>'; return; }
    tbody.innerHTML = data.map(function(a){
      var actions = '';
      if (a.status==='new') actions = '<button class="btn btn-primary btn-sm" onclick="event.stopPropagation();Alerts.action(\''+esc(a.alert_id)+'\',\'actioned\')">Action</button> <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();Alerts.action(\''+esc(a.alert_id)+'\',\'dismissed\')">Dismiss</button>';
      else if (a.status==='actioned') actions = '<button class="btn btn-primary btn-sm" onclick="event.stopPropagation();Alerts.action(\''+esc(a.alert_id)+'\',\'dispatched\')">Dispatch</button>';
      return '<tr class="alert-row" onclick="Alerts.openDetail(\''+esc(a.alert_id)+'\')">'+
        '<td class="mono">'+shortId(a.alert_id)+'</td><td>'+esc(a.atm_id)+'</td><td>'+esc(a.city||"--")+'</td>'+
        '<td>'+riskChip(a.risk_score)+'</td><td>'+tierChip(a.tier)+'</td><td>'+statusChip(a.status)+'</td>'+
        '<td>'+fmtDate(a.created_at)+'</td><td><div style="display:flex;gap:4px">'+actions+'</div></td></tr>';
    }).join("");
  },
  action: async function(alertId, status) {
    try {
      var r = await API.post("/alerts/"+alertId+"/status", {status:status});
      if (r._forbidden) { Toast.warning("Access Denied", "Insufficient permissions."); return; }
      Toast.success("Alert Updated", "Alert "+shortId(alertId)+" marked as "+status);
      this.load(); updateBadge();
    } catch(e) { Toast.error("Action Failed", e.message); }
  },
  openDetail: async function(alertId) {
    var alert = State.alerts.find(function(a){return a.alert_id===alertId;});
    if (!alert) { try { alert = await API.get("/alerts/"+alertId); } catch(e){} }
    if (!alert || alert._forbidden) return;
    var self = this;
    API.get("/alerts/"+alert.alert_id+"/evidence").then(function(ev) {
      var evHtml = ev && !ev._forbidden ? '<div class="drawer-section"><div class="drawer-section-title">Evidence</div>'+
        '<div class="drawer-kv"><span class="k">Source</span><span class="v">'+esc(ev.source||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Confidence</span><span class="v">'+(ev.confidence!=null?(ev.confidence*100).toFixed(1)+"%":"--")+'</span></div></div>' : '';
      Drawer.open({
        title: "Alert: " + shortId(alert.alert_id),
        body: '<div class="drawer-section"><div class="drawer-section-title">Alert Info</div>'+
          '<div class="drawer-kv"><span class="k">Alert ID</span><span class="v mono">'+esc(alert.alert_id)+'</span></div>'+
          '<div class="drawer-kv"><span class="k">ATM</span><span class="v">'+esc(alert.atm_id)+'</span></div>'+
          '<div class="drawer-kv"><span class="k">Bank</span><span class="v">'+esc(alert.bank_name||"--")+'</span></div>'+
          '<div class="drawer-kv"><span class="k">City</span><span class="v">'+esc(alert.city||"--")+'</span></div>'+
          '<div class="drawer-kv"><span class="k">District</span><span class="v">'+esc(alert.district||"--")+'</span></div>'+
          '<div class="drawer-kv"><span class="k">State</span><span class="v">'+esc(alert.state||"--")+'</span></div></div>'+
          '<div class="drawer-section"><div class="drawer-section-title">Risk Assessment</div>'+
          '<div class="drawer-kv"><span class="k">Risk Score</span><span class="v">'+riskChip(alert.risk_score)+'</span></div>'+
          '<div class="drawer-kv"><span class="k">Tier</span><span class="v">'+tierChip(alert.tier)+'</span></div>'+
          '<div class="drawer-kv"><span class="k">Status</span><span class="v">'+statusChip(alert.status)+'</span></div>'+
          '<div class="drawer-kv"><span class="k">Action</span><span class="v">'+esc(alert.recommended_action||"--")+'</span></div>'+
          '<div class="drawer-kv"><span class="k">Created</span><span class="v">'+fmtDate(alert.created_at)+'</span></div></div>'+evHtml,
        footer: (alert.status==='new'?'<button class="btn btn-primary btn-sm" onclick="Alerts.action(\''+esc(alert.alert_id)+'\',\'actioned\');Drawer.close()">Action</button>':'')+
          (alert.status==='actioned'?'<button class="btn btn-primary btn-sm" onclick="Alerts.action(\''+esc(alert.alert_id)+'\',\'dispatched\');Drawer.close()">Dispatch</button>':'')+
          '<button class="btn btn-secondary btn-sm" onclick="Drawer.close()">Close</button>',
      });
    });
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
      if(r.status==="flagged")c.flagged++;if(r.status==="hold_placed")c.held++;if(r.status==="recovered")c.recovered++;
    });
    $("rec-total").textContent = fmtNum(c.total);
    $("rec-flagged").textContent = fmtNum(c.flagged);
    $("rec-held").textContent = fmtNum(c.held);
    $("rec-recovered").textContent = fmtNum(c.recovered);
    var tbody = $("recovery-table");
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="7" class="table-empty">No recovery recommendations</td></tr>'; return; }
    tbody.innerHTML = data.map(function(r){
      var acts = '';
      if (r.status==='flagged') acts = '<button class="btn btn-primary btn-sm" onclick="Recovery.freeze(\''+esc(r.rec_id)+'\')">Freeze</button>';
      else if (r.status==='hold_placed') acts = '<button class="btn btn-primary btn-sm" onclick="Recovery.markRecovered(\''+esc(r.rec_id)+'\')">Mark Recovered</button>';
      acts += ' <button class="btn btn-ghost btn-sm" onclick="Recovery.detail(\''+esc(r.rec_id)+'\')">Details</button>';
      return '<tr><td class="mono">'+shortId(r.rec_id)+'</td><td class="mono">'+esc(r.account_token?r.account_token.slice(-8):"--")+'</td>'+
        '<td>'+esc(r.home_bank)+'</td><td style="font-weight:600">₹'+fmtNum(r.amount_at_risk)+'</td>'+
        '<td>'+esc(r.suspected_atm||"--")+'</td><td>'+statusChip(r.status)+'</td><td><div style="display:flex;gap:4px">'+acts+'</div></td></tr>';
    }).join("");
  },
  freeze: async function(recId) {
    var ok = await Modal.confirm("Confirm Freeze", "Place a hold on the account for "+shortId(recId)+"?");
    if (!ok) return;
    try {
      var r = await API.post("/recovery/"+recId+"/status",{status:"hold_placed",amount_held:0});
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
        '<div class="drawer-kv"><span class="k">Amount at Risk</span><span class="v">₹'+fmtNum(r.amount_at_risk)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Amount Held</span><span class="v">₹'+fmtNum(r.amount_held)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Amount Recovered</span><span class="v">₹'+fmtNum(r.amount_recovered)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Suspected ATM</span><span class="v">'+esc(r.suspected_atm||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Window</span><span class="v">'+esc(r.predicted_window||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Action</span><span class="v">'+esc(r.recommended_action||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Status</span><span class="v">'+statusChip(r.status)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Created</span><span class="v">'+fmtDate(r.created_at)+'</span></div></div>',
      footer: '<button class="btn btn-secondary btn-sm" onclick="Drawer.close()">Close</button>',
    });
  },
};

/* ═══ VIEW: INVESTIGATIONS ═══ */
var Investigations = {
  complaints: [],
  load: async function() {
    await this.loadComplaints();
    this.initTabs();
  },
  initTabs: function() {
    document.querySelectorAll("#investigation-tabs .tab-item").forEach(function(tab){
      tab.onclick = function(){
        document.querySelectorAll("#investigation-tabs .tab-item").forEach(function(t){t.classList.remove("active");});
        document.querySelectorAll("#view-investigations .tab-content").forEach(function(c){c.classList.remove("active");});
        tab.classList.add("active");
        $(tab.dataset.tab).classList.add("active");
      };
    });
  },
  loadComplaints: async function() {
    try {
      var data = await API.get("/complaints?limit=50");
      if (data._forbidden) { $("complaints-table").innerHTML = '<tr><td colspan="6" class="table-empty">Access restricted</td></tr>'; return; }
      this.complaints = Array.isArray(data) ? data : (data && data.items || data && data.complaints || []);
      this.renderComplaints();
    } catch(e) { $("complaints-table").innerHTML = '<tr><td colspan="6" class="table-empty">Failed to load</td></tr>'; }
  },
  renderComplaints: function(filter) {
    var data = this.complaints;
    if (filter) {
      var f = filter.toLowerCase();
      data = data.filter(function(c){return (c.complaint_id||"").toLowerCase().indexOf(f)>=0||(c.city||"").toLowerCase().indexOf(f)>=0;});
    }
    var tbody = $("complaints-table");
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="6" class="table-empty">No complaints</td></tr>'; return; }
    tbody.innerHTML = data.slice(0,50).map(function(c){
      return '<tr><td class="mono">'+esc(c.complaint_id||"--")+'</td><td>'+esc(c.city||"--")+'</td>'+
        '<td style="font-weight:600">₹'+fmtNum(c.amount)+'</td><td>'+esc(c.complaint_type||"--")+'</td>'+
        '<td>'+fmtDate(c.date||c.created_at)+'</td>'+
        '<td><button class="btn btn-ghost btn-sm" onclick="Investigations.openComplaint(\''+esc(c.complaint_id)+'\')">View</button></td></tr>';
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
        '<div class="drawer-kv"><span class="k">Amount</span><span class="v">₹'+fmtNum(c.amount)+'</span></div>'+
        '<div class="drawer-kv"><span class="k">City</span><span class="v">'+esc(c.city||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">District</span><span class="v">'+esc(c.district||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">State</span><span class="v">'+esc(c.state||"--")+'</span></div>'+
        '<div class="drawer-kv"><span class="k">Date</span><span class="v">'+fmtDate(c.date||c.created_at)+'</span></div>'+
        (c.account_number?'<div class="drawer-kv"><span class="k">Account</span><span class="v mono">'+esc(c.account_number)+'</span></div>':'')+
        (c.atm_id?'<div class="drawer-kv"><span class="k">ATM</span><span class="v mono">'+esc(c.atm_id)+'</span></div>':'')+'</div>',
      footer: '<button class="btn btn-secondary btn-sm" onclick="Drawer.close()">Close</button>',
    });
  },
  loadAtmProfile: async function(atmId) {
    try {
      var rd = await API.get("/risk-scores?horizon=24");
      var ad = await API.get("/alerts?atm_id="+encodeURIComponent(atmId)+"&limit=10");
      var atmRisk = (rd._forbidden?[]:rd||[]).find(function(a){return a.atm_id===atmId;});
      var atmAlerts = ad._forbidden?[]:ad||[];
      var html = '';
      if (atmRisk) {
        html += '<div class="drawer-section"><div class="drawer-section-title">Risk Profile</div>'+
          '<div class="drawer-kv"><span class="k">ATM</span><span class="v mono">'+esc(atmRisk.atm_id)+'</span></div>'+
          '<div class="drawer-kv"><span class="k">Bank</span><span class="v">'+esc(atmRisk.bank_name)+'</span></div>'+
          '<div class="drawer-kv"><span class="k">City</span><span class="v">'+esc(atmRisk.city)+'</span></div>'+
          '<div class="drawer-kv"><span class="k">Risk</span><span class="v">'+riskChip(atmRisk.risk_score)+'</span></div>'+
          '<div class="drawer-kv"><span class="k">Level</span><span class="v">'+esc(atmRisk.risk_level)+'</span></div></div>';
      }
      if (atmAlerts.length) {
        html += '<div class="drawer-section"><div class="drawer-section-title">Alerts ('+atmAlerts.length+')</div>';
        atmAlerts.forEach(function(a){
          html += '<div class="drawer-kv"><span class="k">'+shortId(a.alert_id)+'</span><span class="v">'+statusChip(a.status)+' '+riskChip(a.risk_score)+'</span></div>';
        });
        html += '</div>';
      }
      if (!html) html = '<div class="empty-state"><div class="empty-icon">&#128269;</div><div class="empty-title">No Data</div><div class="empty-desc">No risk data found for this ATM.</div></div>';
      $("inv-atm-profile-content").innerHTML = html;
    } catch(e) { $("inv-atm-profile-content").innerHTML = '<div class="error-banner"><span class="error-banner-icon">&#10007;</span><div class="error-banner-text"><div class="error-banner-title">Load Failed</div><div class="error-banner-msg">'+esc(e.message)+'</div></div></div>'; }
  },
  loadMoneyTrail: async function(accountToken) {
    try {
      var data = await API.get("/mule-graph/trail/"+encodeURIComponent(accountToken));
      if (data._forbidden) { Toast.warning("Access Denied","Insufficient permissions."); return; }
      if (!data || (!data.chains||!data.chains.length) && (!data.edges||!data.edges.length)) {
        $("money-trail-output").innerHTML = '<div class="empty-state"><div class="empty-icon">&#128279;</div><div class="empty-title">No Trail</div><div class="empty-desc">No money trail found.</div></div>';
        return;
      }
      var html = '<div style="padding:16px"><div style="font-size:13px;color:var(--text-secondary);margin-bottom:12px">Account: <span class="mono">'+esc(data.account_token)+'</span> | Window: '+(data.window_days||30)+'d</div>';
      if (data.chains) {
        data.chains.forEach(function(chain,i){
          html += '<div style="margin-bottom:16px;padding:12px;background:var(--bg-elevated);border-radius:var(--radius-md);border:1px solid var(--border-subtle)">';
          html += '<div style="font-size:12px;font-weight:700;color:var(--accent-gold);margin-bottom:8px">Chain '+(i+1)+' — Risk: '+((chain.total_risk||0)*100).toFixed(1)+'%</div>';
          if (chain.nodes) {
            chain.nodes.forEach(function(node,j){
              html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px"><span style="font-size:11px;color:var(--text-muted)">'+(j+1)+'.</span><span class="mono" style="font-size:12px">'+esc(node.id||node.account_token||"--")+'</span><span class="chip chip-'+(node.type==="victim"?"info":node.type==="atm"?"high":"medium")+'" style="font-size:10px">'+esc(node.type||"--")+'</span></div>';
            });
          }
          html += '</div>';
        });
      }
      html += '</div>';
      $("money-trail-output").innerHTML = html;
    } catch(e) { Toast.error("Load Failed",e.message); }
  },
  loadEvidence: async function(alertId) {
    try {
      var data = await API.get("/alerts/"+alertId+"/evidence");
      if (data._forbidden) { Toast.warning("Access Denied","Insufficient permissions."); return; }
      if (!data || Object.keys(data).length===0) {
        $("evidence-output").innerHTML = '<div class="empty-state"><div class="empty-icon">&#128196;</div><div class="empty-title">No Evidence</div><div class="empty-desc">No evidence found for this alert.</div></div>';
        return;
      }
      var html = '<div class="report-output"><h4>Evidence for '+esc(alertId)+'</h4>';
      Object.entries(data).forEach(function(pair){
        var k=pair[0],v=pair[1];
        if (k==="feature_impacts"&&typeof v==="object") {
          html += '<div style="margin-top:12px"><strong style="color:var(--text-primary)">Feature Impacts:</strong></div>';
          Object.entries(v).forEach(function(fp){
            var pct = Math.abs(fp[1])*100;
            html += '<div class="feature-bar" style="margin:4px 0"><span class="feature-bar-name" style="width:160px">'+esc(fp[0])+'</span><div class="feature-bar-track"><div class="feature-bar-fill '+(fp[1]>=0?"positive":"negative")+'" style="width:'+Math.min(pct,100)+'%"></div></div><span class="feature-bar-value">'+(typeof fp[1]==="number"?fp[1].toFixed(4):esc(String(fp[1])))+'</span></div>';
          });
        } else if (typeof v!=='object') {
          html += '<div class="drawer-kv"><span class="k">'+esc(k)+'</span><span class="v">'+esc(String(v))+'</span></div>';
        }
      });
      html += '</div>';
      $("evidence-output").innerHTML = html;
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
    this.canvasCtx.fillStyle = "#0a1628"; this.canvasCtx.fillRect(0,0,canvas.width,canvas.height);
    this.canvasCtx.fillStyle = "#94A3B8"; this.canvasCtx.font = "14px Inter, sans-serif";
    this.canvasCtx.textAlign = "center";
    this.canvasCtx.fillText('Click "Load Network" to visualize mule connections', canvas.width/2, canvas.height/2);
  },
  loadNetwork: async function(atmId, depth) {
    var url = "/graph/mule-network?depth="+(depth||2)+"&limit=200";
    if (atmId) url += "&atm_id="+encodeURIComponent(atmId);
    try {
      var data = await API.get(url);
      if (data._forbidden) { Toast.warning("Access Denied","Insufficient permissions."); return; }
      if (!data||(!data.nodes||!data.nodes.length)&&(!data.edges||!data.edges.length)) {
        Toast.info("No Data","No mule network data found."); return;
      }
      this.nodes = data.nodes||[]; this.edges = data.edges||[];
      this.renderGraph();
    } catch(e) { Toast.error("Load Failed",e.message); }
  },
  renderGraph: function() {
    var canvas = $("mule-canvas"); if (!canvas||!this.canvasCtx) return;
    var ctx = this.canvasCtx, W = canvas.width, H = canvas.height;
    ctx.clearRect(0,0,W,H); ctx.fillStyle = "#0a1628"; ctx.fillRect(0,0,W,H);
    if (!this.nodes.length) { ctx.fillStyle="#94A3B8";ctx.font="14px Inter";ctx.textAlign="center";ctx.fillText("No network data",W/2,H/2);return; }
    var pos = {};
    this.nodes.forEach(function(n,i){
      var angle = (i/MuleNetwork.nodes.length)*2*Math.PI;
      var r = Math.min(W,H)*0.35;
      pos[n.id||n.account_token] = {x:W/2+Math.cos(angle)*r*(0.5+Math.random()*0.5), y:H/2+Math.sin(angle)*r*(0.5+Math.random()*0.5)};
    });
    ctx.strokeStyle = "#243352"; ctx.lineWidth = 1.5;
    this.edges.forEach(function(e){
      var f=pos[e.from||e.source], t=pos[e.to||e.target];
      if(f&&t){ctx.beginPath();ctx.moveTo(f.x,f.y);ctx.lineTo(t.x,t.y);ctx.stroke();}
    });
    this.nodes.forEach(function(n){
      var id=n.id||n.account_token, p=pos[id]; if(!p)return;
      var risk=n.risk||n.terminal_risk||0;
      var color=risk>=0.7?"#EF4444":risk>=0.5?"#F59E0B":risk>=0.3?"#3B82F6":"#22C55E";
      var r=risk>=0.7?10:risk>=0.5?8:6;
      ctx.beginPath();ctx.arc(p.x,p.y,r,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();
      ctx.strokeStyle="rgba(255,255,255,0.2)";ctx.lineWidth=2;ctx.stroke();
      ctx.fillStyle="#F8FAFC";ctx.font="10px Inter";ctx.textAlign="center";ctx.fillText(id.slice(-8),p.x,p.y+r+14);
    });
  },
  loadTerminalNodes: async function() {
    try {
      var data = await API.get("/mule-graph/terminal-nodes?k=20");
      if (data._forbidden) { $("mule-terminal-table").innerHTML='<tr><td colspan="3" class="table-empty">Access restricted</td></tr>';return; }
      var nodes = data&&data.nodes||data||[];
      var tbody = $("mule-terminal-table");
      if (!nodes.length) { tbody.innerHTML='<tr><td colspan="3" class="table-empty">No terminal nodes</td></tr>';return; }
      tbody.innerHTML = nodes.map(function(n){
        return '<tr><td class="mono">'+esc(n.account_token)+'</td><td>'+riskChip(n.terminal_risk)+'</td><td><button class="btn btn-ghost btn-sm" onclick="Investigations.loadMoneyTrail(\''+esc(n.account_token)+'\');switchView(\'investigations\')">Trace</button></td></tr>';
      }).join("");
    } catch(e) { $("mule-terminal-table").innerHTML='<tr><td colspan="3" class="table-empty">Failed</td></tr>'; }
  },
};

/* ═══ VIEW: MODEL HEALTH ═══ */
var ModelHealth = {
  load: async function() { await Promise.all([this.loadMetrics(),this.loadDrift()]); },
  loadMetrics: async function() {
    try {
      var d = await API.get("/train/status");
      if (d&&d.metrics) {
        var m=d.metrics;
        if(m.roc_auc!=null)$("m-roc-auc").textContent=m.roc_auc.toFixed(4);
        if(m.precision_at_20!=null)$("m-prec-20").textContent=m.precision_at_20.toFixed(4);
        if(m.recall_at_20!=null)$("m-rec-20").textContent=m.recall_at_20.toFixed(4);
        if(m.average_precision_at_50!=null)$("m-ap-50").textContent=m.average_precision_at_50.toFixed(4);
        if(m.rba_lift!=null)$("m-rba-lift").textContent=m.rba_lift.toFixed(2);
      }
    } catch(e){}
  },
  loadDrift: async function() {
    try {
      var data = await API.get("/drift/status");
      if (data._forbidden) { $("drift-status-content").innerHTML='<div class="empty-state"><div class="empty-icon">&#128274;</div><div class="empty-title">Access Restricted</div><div class="empty-desc">Requires I4C_ADMIN role.</div></div>';return; }
      if (!data||data.status==="PENDING_REFERENCE"||data.status==="missing") {
        $("drift-status-content").innerHTML='<div class="empty-state"><div class="empty-icon">&#128163;</div><div class="empty-title">No Reference Data</div><div class="empty-desc">Capture a reference snapshot to enable drift monitoring.</div><div class="empty-action"><button class="btn btn-primary btn-sm" onclick="ModelHealth.captureReference()">Capture Reference</button></div></div>';
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
          html+='<div class="drawer-kv"><span class="k">'+esc(k)+'</span><span class="v '+cls+'">'+(typeof psi==="number"?psi.toFixed(4):esc(String(psi)))+' '+(status==="green"?"&#10003;":status==="yellow"?"&#9888;":"&#10007;")+'</span></div>';
        });
        html+='</div>';
        $("drift-status-content").innerHTML=html;
      } else {
        $("drift-status-content").innerHTML='<div class="table-empty">Drift data available</div>';
      }
    } catch(e) { $("drift-status-content").innerHTML='<div class="table-empty">Failed to load drift data</div>'; }
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
      var data = await API.get("/ledger?limit=30");
      if (data._forbidden) { $("ledger-entries").innerHTML='<div class="table-empty">Access restricted</div>';return; }
      State.ledger.entries=data&&data.records||[]; State.ledger.total=data&&data.total||0;
      this.render();
    } catch(e) { $("ledger-entries").innerHTML='<div class="table-empty">Failed to load ledger</div>'; }
  },
  render: function() {
    var entries=State.ledger.entries, container=$("ledger-entries");
    $("ledger-total-entries").textContent=fmtNum(State.ledger.total);
    if (!entries.length) { container.innerHTML='<div class="table-empty">No ledger entries</div>';return; }
    container.innerHTML=entries.map(function(e){
      return '<div class="ledger-block"><span class="ledger-idx">#'+e.index+'</span><span class="ledger-actor">'+esc(e.actor)+'</span><span style="color:var(--accent-gold);font-weight:600;font-size:12px">'+esc(e.event_type)+'</span><span class="ledger-hash">'+esc(e.entity_id||e.payload_hash||"--")+'</span><span class="ledger-time">'+fmtDate(e.created_at)+'</span></div>';
    }).join("");
  },
  verify: async function() {
    try {
      var data = await API.get("/ledger/verify");
      if (data._forbidden) { $("ledger-chain-status").textContent="Restricted";$("ledger-verify-result").textContent="--";return; }
      var valid=data&&data.valid;
      $("ledger-chain-status").textContent=valid?"VALID":"TAMPERED";
      $("ledger-chain-status").className="stat-value "+(valid?"low":"critical");
      $("ledger-verify-result").textContent=valid?"PASSED":"FAILED";
      $("ledger-verify-result").className="stat-value "+(valid?"low":"critical");
    } catch(e) { $("ledger-chain-status").textContent="Error"; }
  },
};

/* ═══ REPORTS ═══ */
var Reports = {
  initTabs: function() {
    document.querySelectorAll("#report-tabs .tab-item").forEach(function(tab){
      tab.onclick = function(){
        document.querySelectorAll("#report-tabs .tab-item").forEach(function(t){t.classList.remove("active");});
        document.querySelectorAll("#view-reports .tab-content").forEach(function(c){c.classList.remove("active");});
        tab.classList.add("active"); $(tab.dataset.tab).classList.add("active");
      };
    });
  },
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
      if (!data||!data.length) { o.innerHTML='<div class="empty-state"><div class="empty-icon">&#128293;</div><div class="empty-title">No Hotspots</div></div>';return; }
      var html='<div class="table-wrap"><table><thead><tr><th>ATM</th><th>City</th><th>District</th><th>Risk</th><th>Level</th></tr></thead><tbody>';
      data.forEach(function(h){
        html+='<tr><td class="mono">'+esc(h.atm_id)+'</td><td>'+esc(h.city)+'</td><td>'+esc(h.district)+'</td><td>'+riskChip(h.risk_score)+'</td><td><span class="chip chip-'+(h.risk_level==="CRITICAL"?"critical":h.risk_level==="HIGH"?"high":"medium")+'">'+esc(h.risk_level)+'</span></td></tr>';
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
      if (typeof data==="string") { o.innerHTML=data; }
      else { o.innerHTML='<h3>City Report: '+esc(city)+'</h3>'+Object.entries(data).map(function(p){return '<div class="drawer-kv"><span class="k">'+esc(p[0])+'</span><span class="v">'+(typeof p[1]==="object"?JSON.stringify(p[1]):esc(String(p[1])))+'</span></div>';}).join(""); }
    } catch(e) { Toast.error("Generation Failed",e.message); }
  },
};

/* ═══ SIMULATION ═══ */
var Simulation = {
  load: async function() {
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
  $("login-form").addEventListener("submit", async function(e) {
    e.preventDefault();
    var btn=$("btn-login"), err=$("login-error");
    btn.disabled=true; btn.textContent="Authenticating..."; err.textContent="";
    try { await Auth.login($("login-username").value.trim(),$("login-password").value); enterApp(); }
    catch(ex) { err.textContent=ex.message||"Authentication failed"; }
    finally { btn.disabled=false; btn.textContent="Authenticate"; }
  });

  document.querySelectorAll(".nav-item[data-view]").forEach(function(item){
    item.addEventListener("click",function(){ switchView(item.dataset.view); });
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
  $("alerts-status-filter").addEventListener("change",function(){ Alerts.load(); });

  var runAlerts = async function() {
    try {
      var r = await API.post("/alerts/run-now");
      if (r._forbidden) { Toast.warning("Access Denied","Insufficient permissions.");return; }
      Toast.success("Alert Cycle Complete","Summary: "+JSON.stringify(r.summary||{}).slice(0,100));
      Alerts.load(); updateBadge();
    } catch(e) { Toast.error("Alert Cycle Failed",e.message); }
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
      $("train-status").textContent="Retraining...";
      var r = await API.post("/train?days_back=30");
      if (r._forbidden) { Toast.warning("Access Denied","I4C_ADMIN role required.");$("train-status").textContent="";return; }
      Toast.success("Retraining Complete",r.message||"Model updated.");
      $("train-status").textContent=r.message||"Done"; ModelHealth.loadMetrics();
    } catch(e) { Toast.error("Retraining Failed",e.message);$("train-status").textContent="Failed"; }
  });

  $("btn-ledger-verify")?.addEventListener("click",function(){ Ledger.verify(); });
  $("btn-ledger-tamper")?.addEventListener("click",async function(){
    try {
      var r = await API.post("/ledger/tamper-demo");
      if (r._forbidden) { Toast.warning("Access Denied","I4C_ADMIN role required.");return; }
      Toast.warning("Tamper Demo","A ledger block has been tampered with. Click Verify to see the chain break.");
      Ledger.load();
    } catch(e) { Toast.error("Tamper Failed",e.message); }
  });
  $("btn-ledger-restore")?.addEventListener("click",async function(){
    try {
      var r = await API.post("/ledger/restore");
      if (r._forbidden) { Toast.warning("Access Denied","I4C_ADMIN role required.");return; }
      Toast.success("Restored","Ledger chain integrity restored."); Ledger.load();
    } catch(e) { Toast.error("Restore Failed",e.message); }
  });

  $("btn-sit-report")?.addEventListener("click",function(){ Reports.generateSituational(); });
  $("btn-hotspot-report")?.addEventListener("click",function(){ Reports.loadHotspots(); });
  $("btn-city-report")?.addEventListener("click",function(){ Reports.generateCity(); });
  Reports.initTabs();

  $("btn-sim-toggle")?.addEventListener("click",function(){ if(State.simulation)Simulation.exit();else Simulation.load(); });
  $("btn-sim-exit")?.addEventListener("click",function(){ Simulation.exit(); });

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
    $("user-role-text").textContent=(user.role||"").replace("_"," ");
    $("user-avatar").textContent=(user.username||"A").charAt(0).toUpperCase();
    var roleMap={"I4C_ADMIN":"I4C Admin","POLICE_STATE":"State Police","POLICE_DISTRICT":"District Police","BANK":"Bank"};
    $("topbar-role-badge").textContent=roleMap[user.role]||user.role;
  }
  // Hide nav items user cannot access
  document.querySelectorAll(".nav-item[data-view]").forEach(function(item){
    item.style.display = Auth.canAccess(item.dataset.view) ? "" : "none";
  });
  Overview.load();
  connectWS();
}

/* ── Init ──────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", function() {
  setupUI();
  if (Auth.role()) {
    // Hide nav items user cannot access
    document.querySelectorAll(".nav-item[data-view]").forEach(function(item){
      item.style.display = Auth.canAccess(item.dataset.view) ? "" : "none";
    });
  }
  if (State.token && State.user) {
    enterApp();
  }
});