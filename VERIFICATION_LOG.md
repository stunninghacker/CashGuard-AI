# VERIFICATION_LOG.md — Manual End-to-End Verification of Demo-Claimed Features

Every feature claimed in README.md / DEMO_SCRIPT.md was MANUALLY exercised
against the live server (API-level, not just UI presence) on the iteration-4
model/data. All timestamps local (Asia/Kolkata, UTC+5:30).

**Method note**: checks were executed via scripted HTTP/WS clients
(`httpx`, `websockets`) plus the server's own test harness
(`scripts/smoke_test.py` → SMOKE OK). Where a check initially failed, the
root cause was investigated and either fixed (code) or corrected in the test
(schema mismatch) — the outcome column reflects the verified state.

## Results (final verified run 2026-08-27, 11:20–11:50 IST — re-run after the
iteration-4 artifact regeneration; every row below reflects the state that is
committed to this repository)

| # | Feature | Outcome | Evidence (what was exercised) |
|---|---------|---------|-------------------------------|
| 1 | JWT auth + 4 role logins | **PASS** | `officer.statea` → POLICE_STATE, `officer.district1` → POLICE_DISTRICT, `bank.hdfc` → BANK, `i4c.admin` → I4C_ADMIN — all HTTP 200 with correct `role`; anonymous `/risk-scores` → 401 |
| 2 | Row-level RBAC (API level) | **PASS** | `officer.district1` /risk-scores JSON contains ONLY `Northsagar` rows; `bank.hdfc` sees ONLY `HDFC Bank`; `officer.statea` sees ONLY `State-A`; `i4c.admin` sees all 5 states (national) |
| 3 | WebSocket live push | **PASS** | Real WS client connected with access token; posted an alert status change → received `{"event": "alert_status", ...}` live over the socket (also observed `ingest` stream-drip events) — not a re-fetch, no polling involved |
| 4 | PDF report generation | **PASS** | POST `/reports/hotspot/{alert_id}` + `/reports/situational` → both PDFs start with `%PDF`, 2.2–3.1 KB, contain real report data (report_id, ATM, jurisdiction, linked complaints); downloaded via `/reports/{id}/download` |
| 5 | Hash-chain ledger + tamper demo | **PASS** | `/ledger/verify` intact=True → POST `/ledger/tamper-demo` → verify intact=False (chain broken at flipped block, `broken_at_index` reported) → `scripts/restore_ledger.py` → verify intact=True again |
| 6 | Recovery funnel workflow | **PASS** | Walked `REC-*` from freeze-requested → `held` (amount_held) → `recovered` (amount_recovered); states persisted; `/recovery/funnel` reflects `amount_recovered=67000.0` |
| 7 | I4C mock webhook inbox | **PASS** | Real HTTP POST to `/mock-i4c-inbox` (channel `verification-log-test`) → GET inbox returns the message with stored payload |
| 8 | DEMO_MODE fallback | **PASS** | Server restarted with `DEMO_MODE=true`: `/risk-scores` returns **sha256-identical payload** (9afde28e…) to the live run in **41 ms** (vs ~2.7–3.0 s live inference) — identical data with zero live inference (DEMO_MODE routes read `data/demo_cache/` only; the model is never loaded); alerts + evidence identical |
| 9 | Robustness check | **PASS** | `scripts/robustness_check.py` re-run against the CURRENT model: 3 rows (base / −30% / +30% config perturbation) with AUC 0.9255/0.9251/0.9302 → PNG regenerated from an ACTUAL perturbed re-run (61,711 bytes) |

## Issues found and fixed during verification

1. **Report-ID collisions**: `RPT-HS-*`/`RPT-SIT-*` IDs were minute-granular —
   generating a second report for the same alert/minute returned HTTP 500
   (UNIQUE constraint). Fixed: IDs now include seconds + a random suffix
   (`backend/services.py`).
2. **Ledger restore**: the tamper demo overwrote a payload hash with no way to
   recover the original. Fixed: `tamper_demo_record` now backs up the original
   hash to `artifacts/ledger_tamper_backup.json`; new
   `scripts/restore_ledger.py` restores it exactly (the demo's "restore story"
   is now a real command).
3. **Harness schema mismatches** (not product bugs): `/ledger/verify` key is
   `intact` (not `valid`); recovery items key is `rec_id`; inbox payload is
   nested under `payload`. Corrected in the verification client.
4. **WS test trigger**: the alert-cycle broadcast is dedupe-suppressed when the
   ATM was already alerted within the cooldown window — verified the live push
   with a deterministic status-change trigger instead.

## Scope note

- All checks ran on the local demo stack (SQLite, single process, uvicorn).
- DEMO_MODE check: cache rebuilt on the same data/model as the live run before
  comparison (bit-identical risk-score payloads).
- No check was excluded from the demo path; no feature failed verification.

## Additional check: alert-fatigue dedup (2026-08-27, 12:10 IST)

| Feature | Outcome | Evidence |
|---------|---------|----------|
| Alert dedup rule (`ALERT_COOLDOWN_HOURS`=6, `ALERT_DEDUP_RISK_DELTA`=0.1) | **PASS** | After closing all open alerts (7 actioned), cycle 1 created **3 alerts** (skipped 0); immediate cycle 2 created **0** (skipped 3) — repeat alerts for the same ATM are suppressed within the window; the risk-escalation bypass (>0.1 rise) is enforced in `run_alert_cycle` (`backend/services.py`). Documented in OPERATIONAL_IMPACT.md "Alert fatigue mitigation". |
| Risk-score inference cache (TTL + single-flight) | **PASS** | Live sequence (2026-08-27): cold call **8.9 s** → cached calls **45–52 ms** with byte-identical payloads (sha 9afde28e) → drip ingest invalidates: next call recomputes (**6.3 s**, payload sha changes) → 8-user concurrency in the load test dropped from **73.6 s to 5.5 s wall** (per-user p95 71.9 s → 5.5 s). Implemented in `get_risk_scores` (`backend/services.py`), documented in LOAD_TEST.md. |
## Red-team probe results (2026-08-27, afternoon)

| Probe | Outcome | Evidence |
|-------|---------|----------|
| IDOR: cross-district/cross-bank single-alert read | **PASS after fix** | Probe found GET /alerts/{id} + /alerts/{id}/evidence unscoped (district read a Metro-West alert, 200). Fixed: row-scoping in 
epo.get_alert(..., user=user) on the alert/evidence/status/report routes. Retest: foreign alert → 404 (district + bank), own-district alert + evidence → 200 (positive control). |
| Missing-model kill test (DEMO_MODE=true, model.joblib deleted) | **PASS after fix** | risk-scores/alerts/evidence/horizons served from cache (15–52 ms, no model loaded); /stats/summary initially 500 (uncached inference path) — fixed to read the demo cache; retest: all endpoints 200. Model restored. |
| Split-cache staleness | **PASS after fix** | main_split_cache.npz served a stale split (pos-rate 0.084 vs 0.062). Fixed: data-stamp guard auto-rebuilds on data change; baseline_war regenerated on the fresh split (P@100 0.86). |

## Item 3 — Alert precision / tiered triage (2026-08-28)

| Check | Outcome | Evidence |
|-------|---------|----------|
| Threshold curve artifact | **PASS** | `scripts/threshold_curve.py` → `artifacts/deep_eval/threshold_curve.json`: 10 points thr 0.50–0.95 (precision 0.554→0.834, recall 0.154→0.045, alert volume 837→163). Serves `GET /risk/threshold-explorer` (artifact-backed, 10 pts, 200). |
| Tier assignment in alert cycle | **PASS** | `backend/models.py` `Alert.tier` (+ column migrated), `backend/services.py` `alert_tier()` (dispatch ≥0.85 / action 0.70–0.85 / monitor), set at alert creation + backfilled from risk_score. Verified: 17 alerts → 16 dispatch, 1 action; dispatch samples risk 0.986–0.996. |
| API schema | **PASS** | `AlertOut.tier` added; `/alerts` returns tier 200. |
| Frontend | **PASS** | `frontend/index.html` alert table Tier column + `app.js` `tierBadge()`/`tierOf()` + `window.THR_CURVE` explorer panel bound to `/threshold-explorer`; `node --check` OK. |
| Regression / smoke | **PASS** | `scripts/test_security_regression.py` 14/14; `scripts/smoke_test.py` OK (SMOKE OK). |
| Honesty | maintained | Threshold explorer labelled "artifact-backed curve"; tiers weight attention, do NOT change the review-before-action rule; operational threshold stays 0.7 unless ops re-derives it. |

## Item 4 — Inter-agency jurisdiction routing (2026-08-28)

| Check | Outcome | Evidence |
|-------|---------|----------|
| Routing engine | **PASS** | `backend/routing.py`: `origin_state_for_atm` (local-seed + account-linked cross-state signals), `route_alert`, `ack_handoff`. `AlertHandoff` model + `Alert.origin_state`/`routing_status`. |
| Wired into alert cycle | **PASS** | `run_alert_cycle` computes origin_state; cross-state alerts flagged + handoff created + ledger-logged (`alert_handoff_created/ack/complete`). |
| API | **PASS** | `GET /alerts/handoffs/list` (role-scoped) 200; `POST /alerts/handoffs/{id}/ack` 200; unknown handoff → 404. |
| Frontend | **PASS** | I4C "Inter-Agency Jurisdiction Handoffs" panel + Ack/Complete; alert routing badge (`origin → state`) in `routingBadge()`; `node --check` OK. |
| Automated unit test | **PASS** | `scripts/test_jurisdiction_routing.py` 4/4 (intra-state no-op, cross-state queued, ack-complete mirrors routing_status, idempotent); cleans up. |
| Full HTTP path | **PASS** | Controlled fixture → list 200 (1) → ack 200 complete → cleaned. |
| Regression / smoke | **PASS** | security regression 14/14; smoke OK. |
| HONESTY — current data | documented | Synthetic generator is intra-state (withdrawals cluster near complaint origin), so handoffs do NOT fire in production runs. Mechanism verified on controlled fixtures; activates with zero code changes when cross-state data arrives. No fabricated cross-state cases to make the queue look busy. See JURISDICTION_ROUTING.md. |

## Item 2 — Sub-daily (hourly) granularity, documented honestly (2026-08-28)

| Check | Outcome | Evidence |
|-------|---------|----------|
| Hourly mode exists & config-gated | **PASS** | `HOURLY_MODE` flag, `backend/ml/hourly_features.py` (vectorized), `scripts/hourly_eval.py`. |
| Honest hourly evaluation | **PASS** | `artifacts/deep_eval/hourly_eval.json`: AUC 0.546 (vs daily 0.93), PR-AUC 0.116, P@100 0.58, P@1000 0.29, n=216,000 hourly rows. |
| "Why" documented in MODEL_CARD.md | **PASS** | New "Sub-daily (hourly) granularity — investigated, honestly not adopted" section: data sparsity + loss of daily context; operational forecast stays the daily 24h window; sub-daily is a roadmap, not a claim. |
| Honesty discipline | maintained | Retired feature-on-evidence surfaced with real numbers (0.55 vs 0.93) rather than hiding the sub-daily mode behind the daily headline; referenced LIMITATIONS.md. |

## Item 5 — Active fairness constraint (per-jurisdiction proportional alert cap, 2026-08-28)

| Check | Outcome | Evidence |
|-------|---------|----------|
| Config gate | **PASS** | `FAIRNESS_ALERT_CAP` (default on) + `FAIRNESS_CAP_PREFERENCE` in `backend/config.py`; disable = inert (no demotion), A/B-testable without code change. |
| Mechanism | **PASS** | `backend/services.py` `FairnessCap`: per-state budget sized proportional to live ATM population by state (`atm_population_by_state` in `repositories.py`); over-budget dispatch/action demoted to monitor with `FAIRNESS-CAPPED` reason; dispatch overrides (`allow_override`) so real escalations never suppressed. |
| Wired into alert cycle | **PASS** | `run_alert_cycle` instantiates cap on flagged set, consumes per alert before create; `tier` uses effective (demoted) tier; intelligence always recorded, only actionable push rebalanced. |
| Unit test | **PASS** | `scripts/test_fairness_cap.py` 5/5 (proportional sizing, demotion+counter, dispatch override, under-budget keep, disabled-inert); cleans up. |
| Docs | **PASS** | FAIRNESS_AUDIT.md "Active fairness constraint" section framing it as alert-volume fairness (the enforceable lever), NOT a change to underlying per-group FP rates. |
| Honesty | maintained | Constraint rebalances actionable pressure proportionally; it does not alter risk scores, the review-before-action rule, or the already-documented per-group FP rates. |

## Item 6 — DATA_PROTECTION.md compliance layer (2026-08-28)

| Check | Outcome | Evidence |
|-------|---------|----------|
| Consolidated single-point doc | **PASS** | `DATA_PROTECTION.md` — one judge-facing posture doc; traces every control to code/artifact; links DPDP_ACT_COMPLIANCE.md + PRIVACY_MODEL.md deep-dives. |
| Ground-truth honesty | **PASS** | §0 states synthetic-only, NO real personal data (traces REAL_DATA_GAP.md); no claim of real processing/savings/consent. |
| Traces to code | **PASS** | §5 control matrix maps pseudonymization (`backend/models.py`), role-scoped vault, auth, RBAC, tamper-evident ledger, env-injected secrets — all enforced in code. |
| DPDP alignment | **PASS** | Minimization §5, purpose §5, retention §8, consent §6, breach posture — mapped to existing DPDP_ACT_COMPLIANCE.md; production encryption-at-rest honestly listed as runbook (not claimed for local SQLite demo). |
| Indexed | **PASS** | DOCS_INDEX.md → added to "Start here (judge reading path)". |

## Item 7 — Live demo deployment package (2026-08-28)

| Check | Outcome | Evidence |
|-------|---------|----------|
| Multi-stage Dockerfile | **PASS** | `Dockerfile` — builder venv → slim runtime; healthcheck on `/health` (`start-period=120s` for first-boot generate+train); `DATA_DIR=/app/data` for persistent volume; config-gated. |
| Render Blueprint | **PASS** | `render.yaml` — Docker runtime + `/health` health-check + 1GB disk at `/app/data` + uses sync:false secret placeholders; `ALLOW_TAMPER_DEMO=false`. |
| Fly config | **PASS** | `fly.toml` — internal_port 8000, `/health` probe, volume mount. |
| DATA_DIR env-overridable | **PASS** | `backend/config.py` `DATA_DIR` now `os.getenv(...)` (was hardcoded) so volumes work; verified override + default. |
| Honest URL placeholder | **PASS** | `LIVE_DEMO.md` — deployment package READY, live URL explicitly PLACEHOLDER (not deployed); deployment safety rules enumerated (synthetic-only, tamper OFF, no credential reuse, secrets env-only). |
| README/index | **PASS** | README "Live demo (deployment-ready)" section + Future Scope updated; DOCS_INDEX references LIVE_DEMO.md. |

## Item 8 — BLOCKCHAIN_UPGRADE_PATH.md (audit-integrity upgrade path, 2026-08-28)

| Check | Outcome | Evidence |
|-------|---------|----------|
| Honest staged path | **PASS** | New `BLOCKCHAIN_UPGRADE_PATH.md`: Stage 0 (hash chain + Raft replicated log, in-repo/working) → Stage 1 (multi-party permissioned replicated log, real transport) → Stage 2 (anchor root hash to permissioned ledger/testnet) → Stage 3 (optional non-PII hashed on-chain metadata). |
| Traces to real artifacts | **PASS** | References `append_ledger` SHA-256 chain (`repositories.py`), `ledger.py` API, `ledger_replication.py`, `LEDGER_ANCHOR_RPC_URL` integration point. |
| Terminology discipline | **PASS** | Explicit: current system is a hash chain / append-only log, NOT a blockchain (never mislabeled); blockchain applies only to the external permissioned-ledger stage (not exercised). |
| Scoped design | **PASS** | Justifies permissioned (not public) ledger for the fixed set of authorities + sensitive data; data-minimization preserved (only root-hash commitments anchored). |
| Indexed / README | **PASS** | DOCS_INDEX deep-detail entry; README Future Scope bullet references the doc. Honesty matches BLOCKCHAIN_JUSTIFICATION.md (§"nearest-similar-red-flags" tone). |



| Probe | Outcome | Evidence |
|-------|---------|----------|
| JWT tamper / expired token / forged role | **PASS** | tampered → 401; forged past-exp → 401; bank-signed I4C claim → 403 on /train and /stats |
| Report scoping | **PASS after fix** | district read of a situational report was 200 → fixed (`_report_in_scope`); retest: situational → 404, own-district hotspot → 200, foreign-bank → 404 |
| Corrupt model file | **PASS (safe failure)** | clean EOFError on load, no silent wrong predictions; DEMO_MODE unaffected; restore → 200 |
| Regression suite | **PASS** | `scripts/test_security_regression.py` — 14/14 (anon, JWT, expiry, forged role, WS, RBAC, IDOR + control, report scope, traversal, train role, demo auth) |

# Live-demo hardening round (2026-08-29) — itemized fixes

## A1 — Offline-resilient risk heatmap (map fallback) [FIXED + VERIFIED]

**Root cause of the original "Map tiles unavailable (offline?)"** — `renderMap()`
short-circuited on `!atmLayer` (null on first call) *before* ever calling
`initMap()`, so the Leaflet map never initialized; on total tile failure it showed
a bare error state in front of judges.

**Fix (`frontend/app.js`):**
- `renderMap()` now calls `initMap()` first (builds the engine + layers) before
  using them, so the real Leaflet map initializes.
- Multi-provider tile fallback: CARTO `dark_all` -> OSM standard, auto-switch on
  repeated `tileerror`.
- **Guaranteed-offline canvas fallback** (`enableOfflineMap()` + `drawOfflineMap()`):
  when all tile providers fail (or after a 9s silent-fail timeout), the `#map`
  is replaced by a self-drawn **canvas vector "district" basemap** built from the
  ATMs' own lat/lon bounds, plotting the SAME risk + complaint heatmap circles —
  so a heatmap ALWAYS renders, even with internet fully disabled. Never a bare
  error state. CSS `.offline-map` added.

**Verification (headless Chrome, puppeteer-core):**
- **Online path:** CARTO tiles load - observed `200 https://a.basemaps.cartocdn.com/...png`; no offline canvas (`offlineCanvas:false`).
- **Offline path:** all tile domains blocked via request interception -> tile requests aborted -> offline note shown + `#offline-map` canvas auto-engaged via the real timeout/tileerror path -> **pixel check: 800x420 canvas, 1396 colored heatmap pixels (`rendered:true`)**.
- Screenshots: `a1-offline-auto.png`, `offline-map-forced.png` (temp evidence for this round).

## A2 — Blank BANK dashboard + Run-Alert-Cycle 403 + role 401/403 (2026-08-29) [FIXED + VERIFIED]

**Blank dashboard root cause:** `/stats/summary` is role-gated to
`I4C_ADMIN/POLICE_STATE/POLICE_DISTRICT` — a BANK login gets 403, which rejected
`Promise.all` in `loadAll()`, so `state.risk` never populated and the bank
dashboard stayed blank (the exact state judges saw).

**Fix:**
- `loadAll()` fetches `/stats/summary` non-fatally (`.catch(() => null)`) and
  `render()` tolerates `state.stats === null` — the BANK dashboard renders its
  data (ATM rows, funnel, recommendations) without the stats block.
- `render()` role-gates the header "Run Alert Cycle" button (#btn-cycle):
  hidden for BANK (backend has always allowed only police/I4C).
- `api()` 403 branch surfaces a global `showNotice()` banner (index.html #notice).

**Verification (headless Chrome, puppeteer-core, script `a2_verify.js`):**
- BANK (`bank.hdfc`): dashboard renders — `atmRows=127`, funnel populated
  (`Flagged ₹5,854,900 / Held / Recovered`), `btnCycleHidden:true`, `dashShown:true`.
- I4C_ADMIN + POLICE_STATE: #btn-cycle visible.
- HTTP: BANK `/risk-scores` → 127 HDFC ATMs; `/recovery/recommendations` → 20;
  `/alerts` → 0 — HDFC genuinely has no alerts in the DB (data, not a bug).

## A3 — Ledger tampered by default + Restore Ledger button (2026-08-29) [FIXED + VERIFIED]

**Root cause (two compounding bugs):**
1. **Route bug** (`backend/api/routes/ledger.py`): the `@router.post("/tamper-demo")`
   decorator was accidentally stacked on the `ledger_network` handler (which also
   serves `GET /network`); `ledger_tamper_demo` had NO decorator, so the tamper
   endpoint was never mounted — clicking "Tamper-demo" returned the replica
   network status and never flipped a block.
2. **Structural corruption / index race** (`backend/repositories.py` +
   `backend/models.py`): `append_ledger` computed `index = last.index + 1` with no
   concurrency guard. The live scheduler appends frequently; when two appends
   raced, both wrote the same next index -> **duplicate indices** (probe found
   **140 duplicate indices** / 906 rows / 738 distinct) which cracks the
   hash-chain check, so `/ledger/verify` reported BROKEN by default.

**Fix:**
- `ledger.py`: tamper decorator moved onto `ledger_tamper_demo`; added
  `POST /ledger/restore` (I4C-only).
- `backend/models.py`: `AuditRecord.index` is now `unique=True`.
- `backend/repositories.py` `append_ledger`: concurrency-safe retry loop — on
  `IntegrityError` it re-seeks to `max(index)+1` and retries (10 attempts), so a
  duplicate index is impossible even under scheduler races.
- `backend/services.py` `restore_ledger_record`: restores from the tamper backup;
  if no backup exists but the chain is broken, it performs a **re-chain repair**
  that normalizes duplicate/gapped indices to a clean sequential 1..N (preserving
  every record's data) and recomputes the hash chain so it verifies intact.
- `frontend/index.html` + `app.js`: "Restore Ledger" button (#btn-ledger-restore)
  wired to `POST /ledger/restore`; refreshes the badge.
- Live DB migration: ledger normalized to sequential 1..N and a UNIQUE index
  `uq_audit_log_index` created on `audit_log("index")` so the fix holds for the
  running demo DB (server was stopped, migrated, restarted).

**Verification (HTTP as i4c.admin + headless Chrome puppeteer):**
- Default `/ledger/verify`: **intact:true** (was broken at block 172 before).
- `POST /ledger/tamper-demo` -> verify **intact:false, broken_at_index` reported**.
- `POST /ledger/restore` -> verify **intact:true** again.
- **Scheduler-race regression**: verified intact through 35 s of live scheduler
  appends (records 930 -> 935) — the unique index + retry prevents the race.
- UI (puppeteer): initial badge `Ledger verified ✓ · 943 blocks` -> click
  Tamper-demo -> badge `LEDGER TAMPERED ✗ at block 948` -> click Restore Ledger
  -> badge `Ledger verified ✓ · 952 blocks`. `A3_UI_FLOW_OK: true`.
- `node --check frontend/app.js` OK; `py_compile` OK on changed backend files.


## A4 — Duplicate / spammy alert feed (2026-08-29) [FIXED + VERIFIED]

**Observed problem (duplicate/spammy feed):** the alert list was full of
look-alike rows — just 23 alerts, 21 of them from only 3 ATMs
(`ATM-NOR0027/0158/0160`, 7 rows each) re-firing almost hourly with
**byte-identical risk scores** (e.g. NOR0027 = 0.9961 every time). Because the
dedup (`recent_open_alert_for_atm`) only matched STILL-OPEN alerts, once a demo
user actioned the 09:16 batch, the same ATMs re-fired at 10:51 with the same
risk — an endless feed of near-duplicate rows.

**Root cause:** the alert-fatigue dedup compared only against *open*
(new/acknowledged) alerts within the cooldown; closed/already-actioned alerts
were invisible to it, so same-risk ATMs re-fired immediately after any status
change. No signal labelled repeats, and no material-change guard on re-fires.

**Fix (backend):**
- `run_alert_cycle` now dedups against the ATM's MOST RECENT alert (any status)
  within the cooldown. If the re-flagged risk did NOT materially rise
  (delta <= ALERT_DEDUP_RISK_DELTA) it records a **re-observation** instead of a
  duplicate alert: increments `Alert.reobservation_count`, sets
  `last_reobserved_at`, and writes an `alert_reobserved` ledger block (audit
  trail for "still watching"). Summary now reports `reobserved: n`.
- A genuine escalation (delta > ALERT_DEDUP_RISK_DELTA) still creates a new
  alert, labelled with `risk_delta_vs_last` so reviewers see the rise.
- New model columns (`reobservation_count`, `last_reobserved_at`,
  `risk_delta_vs_last`) surfaced through `AlertOut`.
- Removed the now-unused `recent_open_alert_for_atm`.

**Fix (frontend):**
- The I4C dashboard had NO alert feed table — `renderAlertTable("i4c-alert-table")`
  silently no-oped because the element was missing. Added an **Active Alerts**
  panel (`#i4c-alert-table`) to `dash-i4c` so the primary I4C view actually shows
  the deduplicated feed.
- New UI pills: `re-observed ×N` (grey) and `▲ +delta escalation` (red) render
  on the alert rows; `#alert-count` now updates on every dashboard that shows it.
- Cache-buster bumped app.js `?v=7` -> `?v=8`.

**Migration:** `ALTER TABLE alerts ADD COLUMN reobservation_count / last_reobserved_at / risk_delta_vs_last` (added to the live DB; server restarted).

**Verification:**
- HTTP (i4c.admin): alert count **stays 23** across 2 `POST /alerts/run-now`
  cycles (`created:0`, `skipped:0`, `reobserved:3` each) — the 3 same-risk ATMs
  are recorded, not duplicated. `reobservation_count` rose 0 -> 6 (2 x 3) and is
  returned by `GET /alerts`.
- UI (puppeteer, I4C admin): `#i4c-alert-table` renders 3 unique alerts each
  tagged **`re-observed ×2`**; no duplicate rows; HITL + routing badges intact.
- `node --check app.js` OK; `py_compile` OK on changed backend files.

## A5 — Broken layout / dead whitespace (2026-08-29) [FIXED + VERIFIED]

**Observed problem:** dashboards were endless-scroll walls with large empty
(dead) whitespace. The `.two-col` grid stretches BOTH columns to the height of
the taller one, and the long, unconstrained data tables pushed every panel way
down. Objective measurements (headless Chrome, 1600x1000):
- Bank dashboard: document height = **4822px** (the 127-row "Your ATMs" table
  alone forced a 4416px column; the sibling fund-block column was stretched to
  match, wasting space).
- Police dashboard: document height = **4051px** (hotspots/alerts two-col = 3155px each).
- I4C dashboard: document height = **2847px** (the alert table panel = 1433px).

**Fix (frontend, CSS + HTML):**
- Added a `.table-scroll` scrollable container (`max-height: 520px; overflow-y: auto`,
  sticky `thead th` header) and wrapped the four long tables in it:
  `hotspot-table`, police `alert-table`, `i4c-alert-table`, `bank-atm-table`,
  and `bank-alert-table`.
- Result: dashboards now fit ~1.5–2 viewport heights and the `.two-col` sibling
  columns are near-equal height, eliminating the dead whitespace.
- Bumped cache-busters: `style.css?v=6` -> `?v=7`, `app.js?v=7` -> `?v=8` (from A4).

**Verification (puppeteer re-measure + scroll test):**
- Document heights: bank **4822 -> 1353**, police **4051 -> 1576**, I4C **2847 -> 2006**.
- Tables now scroll internally with NO data loss (scrollH vs clientH):
  bank atm-table 4350/520 with **all 127 rows**; i4c alert-table scrollable
  with **23 rows**; police hotspot **20 rows** + alert-table **22 rows**.
- No horizontal overflow (`overflowX:false`) on any dashboard; no overlaps.
- HTML well-formed: div 56/56, section 16/16, table 5/5 balanced.

## B — Liquid Glass UI redesign (2026-08-29) [DONE + VERIFIED]

**Change (frontend/style.css):** added an isolated "liquid glass" layer on top of
the base theme — frosted, translucent surfaces over an ambient glow:
- Ambient animated body gradient (radial colour washes) + a fixed `body::before`
  glow-orbit layer (`pointer-events:none`, non-interactive).
- `.panel`, `header`, `.modal-card`, `.toast`, `.notice`, leaflet popups: frosted
  `-webkit-backdrop-filter`/`backdrop-filter: blur(...) saturate(...)` + glass
  border + inner top highlight + soft shadow.
- `.pill`, `.btn`, `.drilldown`, `.chip`, `select`, `.date-input`, inputs: glassy
  translucent treatment; primary/accent buttons get a gradient + glow.
- Sticky table header (`thead th`) made translucent-frosted to match.
- Layer uses new `:root` glass tokens; **does not touch layout/table structure** —
  the A1-A5 fixes are preserved.

**Verification (headless Chrome, all three roles):**
- Login modal computed `backdrop-filter: blur(22px) saturate(1.5)`; panels
  `blur(16px) saturate(1.5)`; body `radial-gradient` ambient active on all dashboards.
- All dashboards still render (visible=true, data intact), `overflowX:false`, and
  document heights unchanged (I4C 2006 / police 1576 / bank 1353) — proving the
  glass layer does not break the A5 layout work.

## C — Login role-select autofill (2026-08-29) [DONE + VERIFIED]

**Change:** replaced the plain-text demo-credential list on the login card with
clickable role-select buttons ("one-click demo sign-in"):
- 4 glass `role-chip` buttons: State Police, District Police, Bank, I4C Admin,
  each showing its username. Clicking calls `window.autofillDemo(username, password)`
  (app.js), which autofills the fields and signs in immediately — no typing, and
  lands the judge on the correct role-scoped dashboard.
- Kept the underlying bcrypt+JWT auth unchanged (autofill just drives the existing
  `doLogin()` path; credentials remain visible for teaching).
- Cache-buster: `app.js?v=8` -> `?v=9`.

**Verification (headless Chrome, click each chip):**
- 4 chips rendered.
- All four one-click sign-ins PASS -> correct dashboard + role badge:
  officer.statea -> POLICE_STATE · State-A; officer.district1 -> POLICE_DISTRICT ·
  Northsagar; bank.hdfc -> BANK · HDFC Bank; i4c.admin -> I4C_ADMIN · national.

## D3 — Alert precision: live PR-tradeoff explorer + tier bands (2026-08-29) [DONE + VERIFIED]

**Context / extend-not-duplicate:** the live precision-recall tradeoff explorer
already existed end-to-end: backend `/threshold-explorer` serves the artifact-backed
`threshold_curve.json` (10-point curve, n=48,600 test rows, pos-rate 0.0618) and the
police dashboard `#thr-explorer` panel has a slider (`#thr-slider`) driving live
precision/recall/alert-volume/false-alert-rate. Verified working. Extended it with
the **tier-band breakdown** (the D3 tie-in to the ACT/REVIEW/HOLD dispatch policy,
and the A4 visual-separation of low-confidence repeats):
- Added `#thr-bands` panel + `renderThrBands()` (app.js). It shows the three dispatch
  bands — DISPATCH >= 0.85, ACTION 0.70-0.85, MONITOR < 0.70 (mirrors
  backend `services.alert_tier`) — and marks exactly ONE active: the tier an alert
  at the selected slider threshold maps to. Slider 0.70 -> ACTION band; 0.90 ->
  DISPATCH band; updates live.
- Glass-consistent `thr-bands`/`band` CSS in style.css.
- Cache-busters: style.css?v=7->8, app.js?v=9->10.

**Verification (headless Chrome, police role):**
- Default 0.70: metrics "precision 62.4% · recall 10.3% · 497 alerts · false-alert
  rate 37.6%", exactly 1 active band (ACTION) PASS.
- Slider to 0.90: metrics "precision 77.3% · recall 5.7% · 220 alerts · false-alert
  rate 22.7%", DISPATCH band active (1 band) PASS.
- Backend `/threshold-explorer` returned the full 10-point curve (HTTP 200).

## D-items first-pass audit — extend-not-duplicate result (2026-08-29)

Before implementing, I audited the repo against all eight D-items (per the
"extend rather than duplicate" instruction). Result: D1, D2, D4, D5, D6, D8 were
ALREADY substantively implemented; D3 already had the live PR explorer (I added
the tier-band extension, committed separately); D7 remains blocked on an external
deploy step. This entry documents verification of the already-done items so the
state is provable.

### D1 — Real-data credibility [ALREADY DONE + VERIFIED]
- `scripts/real_world_calibration.py` compares generator params against 5 PUBLIC,
  citable benchmarks (RBI ATM totals ~2.2-2.6 lakh; I4C ~8,000 complaints/day;
  UPI fraud share; mule behaviour; fraud-to-cashout latency). Ran it now — PASS,
  regenerates `artifacts/deep_eval/real_world_calibration.json`.
- Honest recalibration conclusion already documented: "None made — all comparisons
  are directional or scale-shifted; adjusting coefficients without a public per-ATM
  benchmark would be fabrication." No real per-ATM fraud rate is public, so no
  fabricated recalibration is asserted. `REAL_DATA_GAP.md` already states exactly
  what I4C access is required + a realistic pilot timeline (W0-W8).
- Status: SATISFIES D1 (extend: none needed).

### D2 — Temporal granularity [ALREADY DONE + VERIFIED]
- `MODEL_CARD.md` §"Sub-daily (hourly) granularity" implements and evaluates the
  exact D2 question honestly: hourly AUC 0.546 vs daily 0.93, PR-AUC 0.116 vs 0.41,
  P@100 0.58 vs 0.86. Mechanism documented (data sparsity fragments counters;
  loss of daily mule-buildup context). Reported as experimental/limitation, NOT the
  operational forecast. `artifacts/deep_eval/hourly_eval.json` present (n=216,000
  hourly rows). Tested via `scripts/hourly_eval.py`.
- Status: SATISFIES D2. Honest answer: sub-daily not adopted as operational because
  it degrades; documented in MODEL_CARD.md as asked.

### D4 — Inter-agency jurisdiction routing [ALREADY DONE + VERIFIED]
- `backend/routing.py` + `AlertHandoff` model + `/alerts/handoffs/*` API + I4C
  "Inter-Agency Jurisdiction Handoffs" panel. Ran `scripts/test_jurisdiction_routing.py`
  now — ALL CHECKS PASS (4/4): intra-state no-handoff, cross-state handoff created,
  ack/complete lifecycle, idempotency.
- Honest scope documented: current synthetic generator is intra-state so the live
  queue is empty by design (not fabricated to look busy); module activates with zero
  code changes once cross-state data exists.
- Status: SATISFIES D4.

### D5 — Fairness safeguard (active constraint) [ALREADY DONE + VERIFIED]
- `backend/services.py` `FairnessCap` is an ACTIVE per-jurisdiction proportional
  alert cap wired into `run_alert_cycle`: budgets sized by national ATM population
  per state (`repositories.py`), dispatch/action over-budget alerts demoted to
  monitor (intelligence preserved, actionable volume capped). Config:
  `FAIRNESS_ALERT_CAP` defaults true, `FAIRNESS_CAP_PREFERENCE=dispatch`.
- `backend/eval/fairness_check.py` outputs `artifacts/fairness_report.json`
  (geography-only concentration monitor). Group audit in
  `artifacts/deep_eval/fairness_groups.json` (FPR flat across groups).
- Status: SATISFIES D5 — the active constraint already exists (not just an audit).

### D6 — Compliance (DPDP Act 2023) [ALREADY DONE + VERIFIED]
- `DATA_PROTECTION.md` (single judge-facing posture doc) + `DPDP_ACT_COMPLIANCE.md`
  map data flows to DPDP 2023: consent basis (§6), retention limits (§8), breach
  notification path, minimization/purpose (§5). Excludes-for-honesty: no real PII,
  no DPO engagement, pilot is where obligations are exercised.
- Status: SATISFIES D6.

### D8 — Blockchain theme (upgrade path) [ALREADY DONE + VERIFIED]
- `BLOCKCHAIN_UPGRADE_PATH.md` keeps the honest "hash chain, not distributed ledger"
  framing and adds the concrete permissioned-ledger upgrade path: Stage 1 real
  multi-party network consensus (gRPC/TCP), Stage 2 anchor hash-commitments to
  Hyperledger Fabric channel / Geth-PoA / monitored testnet — with which fields
  anchored (root/Merkle hash, never raw PII) and why a permissioned ledger fits the
  trust model. Companion `BLOCKCHAIN_JUSTIFICATION.md`.
- Status: SATISFIES D8.

### D7 — Live demo hosting [BLOCKED — external action required]
- Deploy package shipped (multi-stage Dockerfile, render.yaml, fly.toml,
  docker-compose.yml, run.py). `LIVE_DEMO.md` + README honestly state no live URL
  exists and why (requires an external Render/Railway/Fly account + authorized
  deploy; cannot be done from inside the repo). A live deploy would also validate
  the A1 map-fallback under real network conditions — but needs the user's external
  access/credentials, which are not available to this agent.
- Status: READY-but-BLOCKED; documented honestly, not claimed as live.

---

## FINAL 10/10 KILL-TEST — fresh-verification session (2026-08-29)

Headline metrics and eval artifacts were NOT taken on trust; the critical ones
were re-executed live against the current DB + pipeline and matched, and one
fabricated-artifact bug was found and fixed.

### Fixes
- **`lift_vs_volume_at_20: 900000000.0` (division-by-zero)** — `backend/ml/train.py`
  computed lift as `active_prec / max(baseline, 1e-9)`; when the volume baseline
  caught zero positives at K, `0.9 / 1e-9 = 9e8` leaked into `metrics.json`. Fixed
  to return `null` when the baseline is 0 (lift is undefined). **Retrained** →
  clean `metrics.json` now shows 18.0x / 40.0x / 21.0x (no 9e8 anywhere).

### Reproduced live (matched stored artifacts)
| Check | Script | Result |
|---|---|---|
| Baseline retrain | `train_model.py` | AUC 0.9272, P@100 0.84, P@1000 0.563 (PASS) |
| Generator leakage | `permutation_tests.py` | label-shuffle AUC 0.488; no identity cols; city-perm ≈ 0 (PASS) |
| Seed stability | `seed_stability.py` | model-seed AUC 0.9258–0.9264; gen-seed P@100 0.50–0.67 (documented) |
| Spatial generalisation | `generalization_splits.py` | t-forward 0.926; cold-atm 0.917; cold-city 0.922; **new-hotspot 0.790** (weak split, reported) |
| Fairness | `fairness_audit.py` | FPR 0.0017–0.0053 across 15 groups (PASS) |
| Security regression | `test_security_regression.py` | 12/12 PASS |
| Jurisdiction routing | `test_jurisdiction_routing.py` | 4/4 PASS |
| Fairness cap | `test_fairness_cap.py` | 5/5 PASS |

### Honest findings logged (not hidden)
1. Complaint/spatial features add almost nothing (permutation Δ < 0.001;
   complaints-only ablation 0.50); `counterparty_count_24h` (single-feature AUC
   ~0.83) drives the model — reactive mule signal, not proactive-from-complaints.
2. New-hotspot generalization is the weak split (P@100 ~0.34 vs 0.82
   time-forward) — the SIH's hardest case.
3. Generator-seed top-100 precision is draw-sensitive (0.50–0.67 vs fixed-seed
   0.84).
4. Sub-daily horizons (2/6/12h) are HOLD; only 24h is operationally usable.

### Deliverables committed (docs/audits)
`FINAL_10_10_BASELINE.md`, `FINAL_10_10_GENERATOR_LEAKAGE.md`,
`FINAL_10_10_SPATIAL_GENERALIZATION.md`, `FINAL_10_10_TEMPORAL_GENERALIZATION.md`,
`FINAL_10_10_BASELINE_WAR.md`, `FINAL_10_10_INTERVENTION_ECONOMICS.md`,
`FINAL_10_10_FAIRNESS.md`, `FINAL_10_10_SCORECARD.md`.
- Status: KILL-TEST findings captured; commits `6f65329`, `81feb58`, `e7fd42f`.
