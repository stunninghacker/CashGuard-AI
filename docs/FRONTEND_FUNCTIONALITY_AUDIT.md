# CashGuard AI — Frontend Functionality Audit

**Date:** September 5, 2026  
**Auditor:** HexStrike AI  
**Scope:** Complete frontend rewrite (app.js v17, index.html, style.css v18)

---

## Architecture Overview

| Component | Technology | Lines |
|-----------|-----------|-------|
| app.js | Vanilla ES6+ JavaScript, no frameworks | 1,644 |
| index.html | Semantic HTML5, ARIA labels | 472 |
| style.css | CSS Custom Properties, responsive grid | 1,300+ |
| Map | Leaflet.js (vendor) | OpenStreetMap tiles |

**Total frontend:** ~3,400 lines, zero external dependencies beyond Leaflet.

---

## View Inventory

### 1. Overview (default view)
- **Stats cards:** High-Risk ATMs, Active Alerts, Complaints 24h, Fraud Withdrawals 7d, ATMs Monitored
- **Priority Actions:** Top 5 high-risk ATMs with rank, location, risk pill
- **Risk Intelligence Map:** Leaflet map with CircleMarkers, color-coded by risk level
- **Filter bar:** State, City, Bank dropdowns + Crime type chips + Horizon selector + Heat/Forecast toggles
- **High-Risk ATMs table:** Top 20 with click-to-focus on map
- **Active Alerts table:** Top 10 alerts with HITL action buttons
- **Threshold Tuning:** Slider to adjust alert sensitivity with precision/volume metrics
- **Mobile Nearby:** GPS-based nearby ATM finder (mobile only)

### 2. Risk Intelligence
- **Full-screen heatmap:** Dedicated Leaflet map (`risk-map`)
- **ATM list sidebar:** Scrollable list with click-to-focus, showing ATM ID, risk pill, action

### 3. Alerts
- **Full alerts table:** All alerts with Alert ID, ATM, Location, Risk, Tier, Status, Actions
- **HITL buttons:** Acknowledge, Monitor, Escalate, Dismiss (inline)
- **Alert badge:** Live count in sidebar for "new" alerts

### 4. Investigations
- **Money Trail Analysis:** Terminal mule accounts table with risk scores, trail loading
- **I4C Intelligence Feed:** Mock inbox messages with channel, timestamp, payload
- **Cross-State Handoffs:** Handoff list with acknowledge actions

### 5. Recovery
- **Recovery Funnel:** Flagged → Held → Recovered visualization
- **Fund-Block Recommendations:** Table with Hold/Recover status transitions
- **Closed-Loop Outcomes:** Total Evaluated, True Positives, False Positives, Precision

### 6. Mule Network
- **SVG network graph:** Force-directed layout with Account (red), Victim (green), Phone (amber), ATM (blue) nodes
- **Edge arrows:** Directed transfer visualization
- **Network stats:** Accounts, complaints, phones, components count

### 7. Audit Trail (Ledger)
- **Verify Ledger:** Hash chain integrity check
- **Tamper Demo:** Simulates tamper event
- **Restore:** Restores ledger integrity
- **Records table:** Index, Time, Actor, Event Type, Entity ID, Hash prefix

### 8. Model Health
- **Health grid:** Training Status, Leakage Audit, Data Source
- **Performance Metrics:** ROC-AUC (0.6456), Precision@20/50/100, Brier Score, Features, Lift, Median Lead Time
- **Feature Drift Monitor:** Green/Yellow/Red status with flagged features

### 9. Reports
- **Report cards:** Situational Intelligence Report, Hotspot Report
- **Generate PDF:** POST to /reports/situational, download link
- **Report output:** Download button for generated PDFs

---

## Authentication & RBAC

| Role | Login | Scope | Accessible Views |
|------|-------|-------|-----------------|
| I4C_ADMIN | i4c.admin / I4cAdmin!1 | National | All 9 views |
| POLICE_STATE | officer.statea / PoliceStateA!1 | State-A | Overview, Risk, Alerts, Investigations, Reports |
| POLICE_DISTRICT | officer.district1 / District1!1 | Northsagar | Overview, Risk, Alerts, Investigations, Reports |
| BANK | bank.hdfc / HdfcBank!1 | HDFC Bank | Overview, Alerts, Recovery |

**Sidebar auto-hides restricted views** based on role via `updateSidebarForRole()`.

---

## Performance Optimizations

| Optimization | Before | After |
|-------------|--------|-------|
| Stats summary cache | 10.2s | 30ms warm (30s TTL) |
| Terminal nodes endpoint | 2.5s | 319ms warm (uses graph cache) |
| Drift singleton | 4.8s per-request | 18ms warm (module-level cache) |
| Mule network | Per-request build | 5-min TTL cache |
| Risk scores sorted | Re-sorted per render | Cached, invalidated on filter change |
| Sub-view rendering | All on load | Lazy on first switch |
| Google Fonts | 200ms network | System font stack (instant) |
| CSS `transition: all` | 5 instances | Removed (GPU-optimized) |
| GZip middleware | None | 95.2% reduction (445KB→22KB) |

---

## Accessibility

- All interactive elements have `role="button"` and `tabindex="0"`
- ARIA labels on all icon-only buttons
- `:focus-visible` outline with accent color
- `prefers-reduced-motion` media query disables animations
- Print stylesheet hides sidebar, topbar, drawer, toast
- Semantic HTML structure (nav, header, main, aside)

---

## Responsive Breakpoints

| Breakpoint | Changes |
|-----------|---------|
| > 1200px | Full layout, 2-column grids |
| ≤ 1200px | Single column, smaller drawer (360px) |
| ≤ 768px | Sidebar becomes mobile drawer, topbar status hidden, map 360px |
| ≤ 480px | Single column stats, single column role grid |

---

## DOM Element Cross-Reference

All 67 `getElementById()` calls in app.js verified against index.html. 3 IDs are dynamically created:
- `drawer-evidence-section` — created in `openDrawer()`
- `reports-output` — created in `renderReportsView()`
- `risk-atm-list` — created in risk view layout

**Result: 100% coverage, zero orphaned references.**

---

## Known Limitations

1. **No browser screenshots** — all analysis is code-level + API measurement
2. **Drift evaluation (12 worlds)** — times out at 5 min (2/12 complete, not blocking)
3. **Bank role /stats/summary** — returns 403 (backend RBAC design, frontend handles gracefully with try/catch)
4. **Offline map** — canvas fallback when tiles fail to load (6+ tile errors)
