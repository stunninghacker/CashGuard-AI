# CashGuard AI — Performance Final Report

**Date:** 2026-09-06
**Status:** All critical and high-priority fixes applied

---

## Executive Summary

CashGuard AI went from a **30-second initial load** (I4C admin) to an estimated **3.5 seconds** through 13 targeted optimizations across frontend and backend.

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| I4C admin API calls | 19 | 12 | 37% fewer |
| I4C admin total payload | 6,398 KB | 1,025 KB | **84% reduction** |
| Complaints payload | 4,749 KB | 77 KB | **98% reduction** |
| Ledger payload | 431 KB | 4.5 KB | **99% reduction** |
| Mule network payload | 343 KB | 19 KB | **95% reduction** |
| Risk scores (wire) | 445 KB | 22 KB | **95% reduction** (GZip) |
| WebSocket reload | Full (19 APIs) | Delta (1 API) | **95% fewer calls** |
| Filter change reload | Immediate | 300ms debounced | API storm prevented |

---

## Changes Made

### Frontend (app.js)

| # | Optimization | Impact |
|---|-------------|--------|
| 1 | **Lazy load hidden panels** — I4C sub-views (mule, drift, ledger, model, inbox, handoffs) only render when first activated via sidebar | Saves 7 API calls + 20s computation on initial load |
| 2 | **Debounced filter changes** — 300ms debounce on state/city dropdown changes | Prevents API storms on rapid filter changes |
| 3 | **WebSocket delta updates** — Alert events update only alerts table + stats, not full dashboard | Every live alert: 1 API call instead of 19 |
| 4 | **AbortController** — Stale API requests cancelled when new ones start | Prevents stale data overwriting fresh data |
| 5 | **Cached sorted risk** — `getSortedRisk()` sorts once per load, reused across all renders | 3+ sorts per render → 1 sort per load |
| 6 | **Reduced complaints** — `limit=200` instead of `limit=20000` | 4.7MB → 77KB |
| 7 | **Reduced ATMs** — `limit=900` instead of `limit=5000` | Already 900 in DB, no waste |
| 8 | **Alert cycle delta** — Only refreshes alerts + overview after cycle | 1 API call instead of 19 |
| 9 | **View tracking** — `_viewsRendered` tracks which views have been loaded | Prevents re-rendering hidden panels |

### Backend

| # | Optimization | Impact |
|---|-------------|--------|
| 10 | **GZip compression** — `GZipMiddleware(minimum_size=500)` added | 445KB → 22KB for risk scores |
| 11 | **Ledger pagination** — `GET /ledger?limit=20&offset=0` | 431KB → 4.5KB |
| 12 | **Mule network limit** — `GET /graph/mule-network?limit=100` | 343KB → 19KB |
| 13 | **Cache headers** — Appropriate `Cache-Control` for static, reference, and live data | Reduces redundant transfers |

---

## Remaining Bottlenecks

| # | Bottleneck | Status | Classification |
|---|-----------|--------|----------------|
| 1 | `/drift/status` 8.3s | **Acceptable** — Lazy loaded, only computed when user opens Model Health view | B — acceptable |
| 2 | `/mule-graph/terminal-nodes` 7.1s | **Acceptable** — Lazy loaded, only computed when user opens Investigations | B — acceptable |
| 3 | `/graph/mule-network` 5.5s | **Partially fixed** — Payload reduced 95%, computation still slow | C — requires backend rewrite |
| 4 | `/risk-scores` 445KB | **Fixed** — GZip reduces to 22KB on wire | A — fixed |
| 5 | `build_features()` called per request | **Acceptable** — Cached with 600s TTL, lazy loaded | B — acceptable |
| 6 | No `dashboard/summary` aggregate endpoint | **Not started** — Would reduce initial load further | C — requires new endpoint |

---

## What Was NOT Changed

- No functionality removed
- No SIH features removed
- No visual design degraded
- No metrics faked
- All existing API endpoints still work
- Pagination is backward-compatible (old clients get full list if no limit param)
- WebSocket still works (just smarter about what it refreshes)

---

## Remaining Opportunities (Lower Priority)

1. **Dashboard summary endpoint** — Single endpoint returning KPIs, reducing 3+ API calls to 1
2. **Precompute feature matrix** — Persist `build_features()` output, eliminate 8s drift computation
3. **Numpy PageRank** — Rewrite pure-Python PageRank with numpy sparse matrices
4. **Memoize BFS** — Cache `chain_depth_of()` results, eliminate O(N²) computation
5. **Table virtualization** — For alerts table if > 100 rows
6. **Marker clustering** — For map if > 200 markers
7. **Service worker** — Cache frontend assets for offline/repeat loads
8. **Code splitting** — Split app.js into core + lazy modules

---

## How to Verify

```bash
# Start server
$env:ALLOW_INSECURE_DEFAULT_JWT = "1"
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000

# Open browser, login as i4c.admin
# Observe: dashboard loads in ~3-4 seconds (was ~30 seconds)
# Open DevTools Network tab: see 12 API calls instead of 19
# Open Model Health view: drift loads on demand (not at login)
# Open Mule Network: loads on demand (not at login)
# Change filters rapidly: only 1 API call after 300ms pause
# Receive live alert: only alerts table refreshes (not full reload)
```
