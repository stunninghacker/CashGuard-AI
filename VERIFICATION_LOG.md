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
