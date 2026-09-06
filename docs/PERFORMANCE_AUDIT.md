# CashGuard AI — Performance Audit

**Date:** 2026-09-06
**Auditor:** Principal Performance Engineer
**Environment:** Windows, Python 3.x, SQLite, single-worker uvicorn, localhost

---

## Executive Summary

CashGuard AI has **critical performance problems** that will cause visible lag, browser freezing, and poor user experience on any machine:

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| I4C admin full load payload | **6,398 KB** | < 500 KB | **12.8x over** |
| I4C admin sequential API time | **29.8 seconds** | < 3 seconds | **10x over** |
| Largest single payload (complaints) | **4,749 KB** | < 100 KB | **47x over** |
| Drift status response | **8.3 seconds** | < 500ms | **16x over** |
| Mule graph computation | **7.1 seconds** | < 1 second | **7x over** |
| Total frontend assets | 299 KB | < 300 KB | OK |
| DOM nodes | 358 | < 500 | OK |

**Root cause:** The frontend loads everything eagerly — all 19 API calls fire on login, including 4.7MB of complaints data and 20-second computation-heavy endpoints. There is no lazy loading, no debouncing, no pagination, and no incremental updates.

---

## 1. Frontend Asset Analysis

| File | Size | Lines | Notes |
|------|------|-------|-------|
| index.html | 24.6 KB | 451 | Single-page app shell, 9 view panels |
| style.css | 45.0 KB | 1044 | Dark theme, responsive, 133 classes |
| app.js | 70.8 KB | 1248 | Vanilla JS, all logic in one file |
| leaflet.js | 144.1 KB | — | Map library (vendor) |
| leaflet.css | 14.5 KB | — | Map styles (vendor) |
| **Total** | **299.0 KB** | — | **OK — under 300KB** |

**Assessment:** Asset sizes are acceptable. No minification needed at this stage. The JS is unminified but 70KB is reasonable. Focus should be on data loading, not asset compression.

---

## 2. DOM Analysis

- **Estimated DOM nodes:** 358
- **Assessment:** Well under the 1,500 danger threshold. DOM structure is clean.

---

## 3. API Response Times (I4C Admin Role)

### 3a. Response Times (sorted slowest first)

| Endpoint | Time | Payload | Verdict |
|----------|------|---------|---------|
| `/drift/status` | **8,333 ms** | 0.8 KB | CRITICAL — rebuilds feature matrix per request |
| `/mule-graph/terminal-nodes` | **7,115 ms** | 1.3 KB | CRITICAL — N× BFS + pure-Python PageRank |
| `/graph/mule-network` | **5,872 ms** | 342.8 KB | CRITICAL — full graph rebuild + large payload |
| `/complaints?limit=20000` | **5,878 ms** | **4,748.7 KB** | CRITICAL — 4.7MB payload, massive query |
| `/risk-scores` | 574 ms | 445.4 KB | HIGH — cached after first call, but 445KB |
| `/ledger` | 800 ms | 431.4 KB | HIGH — no pagination |
| `/stats/summary` | 249 ms | 10.4 KB | MEDIUM — 13 sequential DB queries |
| `/atms?limit=5000` | 330 ms | 235.7 KB | MEDIUM — all 900 ATMs with full fields |
| `/alerts?limit=200` | 126 ms | 85.4 KB | OK |
| `/recovery/recommendations` | 77 ms | 36.1 KB | OK |
| `/ledger/verify` | 76 ms | 0.1 KB | OK |
| `/mock-i4c-inbox` | 61 ms | 19.7 KB | OK |
| `/hotspots` | 66 ms | 9.8 KB | OK |
| `/analytics/time-granularity` | 61 ms | 2.6 KB | OK |
| `/mobile/nearby` | 54 ms | 0.1 KB | OK |
| `/alerts/handoffs/list` | 48 ms | 15.6 KB | OK |
| `/train/status` | 36 ms | 5.8 KB | OK |
| `/horizons` | 37 ms | 3.6 KB | OK |
| `/threshold-explorer` | 33 ms | 5.0 KB | OK |
| `/atms/banks` | 39 ms | 0.1 KB | OK |
| `/blockchain` | 36 ms | 0.9 KB | OK |
| `/blockchain/verify` | 33 ms | 0.2 KB | OK |
| `/i18n/locales` | 27 ms | 0.4 KB | OK |

### 3b. Total I4C Admin Full Load

- **Endpoints called:** 19
- **Total payload:** 6,398 KB (6.2 MB)
- **Sequential time:** 29,799 ms (30 seconds)
- **Estimated parallel time:** ~9 seconds (3-4 concurrent)

---

## 4. Frontend Loading Architecture (Current)

### Login → Dashboard Sequence

```
User logs in
  └→ connectWS()              — WebSocket connection
  └→ loadAll()                — THE main loader
       ├→ loadCityCoords()    — GET /atms?limit=5000 (236KB)
       ├→ loadComplaints()    — GET /complaints?limit=20000 (4.7MB) ← BOTTLENECK
       ├→ render()
       │   ├→ renderI4C()     — fires 10+ API calls:
       │   │   ├→ renderMap()             — Leaflet init + markers
       │   │   ├→ renderAlertTable()      — DOM innerHTML rebuild
       │   │   ├→ renderRecoveryView()    — 2 API calls
       │   │   ├→ renderMuleGraph()       — 1 API call (7s)
       │   │   ├→ renderDrift()           — 1 API call (8s)
       │   │   ├→ renderMuleNetwork()     — 1 API call (6s, SVG render)
       │   │   ├→ ledgerStatus()          — 2 API calls
       │   │   ├→ renderModelView()       — 1 API call
       │   │   ├→ renderInbox()           — 1 API call
       │   │   └→ renderHandoffs()        — 1 API call
       │   ├→ renderOverviewStats()
       │   └→ renderPriorityActions()
       └→ renderHorizonConfidence()
```

### Problems Identified

1. **All views render on login** — renderI4C() fires 10 API calls even for hidden panels
2. **Complaints: 4.7MB loaded eagerly** — 20,000 records fetched on every login
3. **No debouncing** — each filter change triggers loadAll() immediately
4. **WebSocket triggers full reload** — every live alert re-fetches everything
5. **No request cancellation** — stale responses can overwrite fresh data
6. **Repeated sorting** — [..state.risk].sort() called 3+ times per render

---

## 5. Backend Bottleneck Analysis

### 5a. /drift/status — 8.3 seconds

**File:** `backend/ml/drift.py` → `build_features()`

The drift endpoint rebuilds the **entire 900-ATM × 36-feature matrix** on every request when the cache is cold. This involves:
1. Loading ALL complaints, withdrawals, ATMs into pandas
2. Creating a 900 × N-day cross-join grid
3. 20+ rolling window aggregations
4. Hawkes intensity computation per city
5. 12 new Issue-1 features

This is a **batch training pipeline** being called as an API endpoint.

### 5b. /mule-graph/terminal-nodes — 7.1 seconds

**File:** `backend/ml/mule_graph.py`

Three compounding bottlenecks:
1. `build_graph()` uses `df.iterrows()` — slowest pandas iteration method
2. `pagerank()` is pure Python with 40 iterations of nested loops
3. `chain_depth_of()` runs **full BFS per node** — O(N × (N+E)) total

### 5c. /complaints?limit=20000 — 5.9 seconds, 4.7 MB

**File:** `backend/repositories.py`

Returns all 20,000 complaints with full fields. No pagination, no aggregation.

### 5d. /stats/summary — 880ms

**File:** `backend/services.py:1237-1274`

13 sequential database queries (count_complaints × 3, count_withdrawals, count_fraud, count_atms, count_alerts × 3, complaints_by_city × 2, complaints_by_type, complaints_by_city_type). Each is a separate SQL round-trip.

### 5e. /risk-scores — 445 KB

Returns all 900 ATMs with full risk data. No pagination, no sparse fields.

### 5f. /ledger — 431 KB

No pagination. Returns the entire audit log.

---

## 6. WebSocket Analysis

**Current behavior:**
- Single connection to `/ws/alerts` — good
- On `alert` event: calls `loadAll()` — bad (triggers 19 API calls)
- On `recovery`/`recovery_status` event: calls `loadAll()` — bad
- Reconnect on close after 5s with no backoff — acceptable but fragile

**Impact:** Every live alert causes a full dashboard reload (30 seconds for I4C admin).

---

## 7. Map Rendering Analysis

**Current behavior:**
- Leaflet initialized once (good)
- `renderMap()` clears all markers and recreates them on every call (bad)
- Up to 5,000 `L.circleMarker` objects created on initial load
- No marker clustering
- No debouncing on filter changes

**Impact:** Each render creates 5,000+ DOM elements via Leaflet. Filter changes trigger full marker recreation.

---

## 8. Table Rendering Analysis

**Current behavior:**
- `renderAlertTable()` rebuilds entire table via `innerHTML` on every call
- Alert table limited to 200 rows — acceptable
- Hotspot table shows all hotspots — acceptable
- Mule graph table shows terminal nodes — acceptable

**Assessment:** Tables are not the primary bottleneck. The 200-row alert table innerHTML rebuild is fast enough.

---

## 9. Memory Leak Indicators

- **WebSocket reconnect:** No max retry count — could reconnect infinitely
- **Map markers:** Cleared and recreated on each render — no accumulation
- **SVG graph:** Entire SVG rebuilt on each render — no accumulation
- **Event listeners:** Bound once in `bindEvents()` — no accumulation
- **Timers:** Only setTimeout for toast (4.5s) and WS reconnect (5s) — no leaks

**Assessment:** No critical memory leaks detected. The main concern is the 4.7MB complaints dataset held in memory.

---

## 10. Priority Fix List

### CRITICAL (Blocks user experience)

| # | Issue | Impact | Fix |
|---|-------|--------|-----|
| 1 | Complaints 4.7MB eager load | Freezes browser on load | Lazy load, reduce limit, server-side aggregation |
| 2 | renderI4C() fires 10 API calls on every loadAll() | 30s full reload | Lazy load hidden panels |
| 3 | WebSocket triggers full loadAll() | Every alert = 30s reload | Delta updates, partial refresh |
| 4 | Drift: 8.3s feature matrix rebuild | Blocks I4C dashboard | Precompute + persist feature matrix |
| 5 | Mule graph: 7.1s computation | Blocks I4C dashboard | Memoize BFS, numpy PageRank |

### HIGH (Significant performance impact)

| # | Issue | Impact | Fix |
|---|-------|--------|-----|
| 6 | No filter debouncing | Rapid changes = N reloads | Debounce 300ms |
| 7 | No pagination on ledger | 431KB payload | Add LIMIT/OFFSET |
| 8 | No pagination on risk-scores | 445KB payload | Sparse fields, pagination |
| 9 | 13 sequential DB queries in stats | 880ms | Single aggregate query |
| 10 | No request cancellation | Stale overwrites fresh | AbortController |

### MEDIUM (Improvement opportunities)

| # | Issue | Impact | Fix |
|---|-------|--------|-----|
| 11 | Map recreates all markers on filter | Unnecessary DOM work | Diff-update markers |
| 12 | Repeated risk array sorting | 3+ sorts per render | Sort once, cache |
| 13 | No GZip compression | Raw JSON transfer | Add GZipMiddleware |
| 14 | No stale-while-revalidate | Shows loading spinners | Cache + background refresh |

---

## 11. Measurement Methodology

- **API times:** PowerShell `Invoke-WebRequest` with `[System.Diagnostics.Stopwatch]`
- **Payload sizes:** `Content.Length` from HTTP responses
- **DOM nodes:** Regex tag count from index.html
- **File sizes:** `Get-Item` on frontend assets
- **Backend profiling:** Code review of query patterns and computation logic

All measurements taken from localhost (no network latency). Production deployments should add ~50-200ms for network overhead.
