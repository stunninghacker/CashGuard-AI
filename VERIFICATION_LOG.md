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



| Probe | Outcome | Evidence |
|-------|---------|----------|
| JWT tamper / expired token / forged role | **PASS** | tampered → 401; forged past-exp → 401; bank-signed I4C claim → 403 on /train and /stats |
| Report scoping | **PASS after fix** | district read of a situational report was 200 → fixed (`_report_in_scope`); retest: situational → 404, own-district hotspot → 200, foreign-bank → 404 |
| Corrupt model file | **PASS (safe failure)** | clean EOFError on load, no silent wrong predictions; DEMO_MODE unaffected; restore → 200 |
| Regression suite | **PASS** | `scripts/test_security_regression.py` — 14/14 (anon, JWT, expiry, forged role, WS, RBAC, IDOR + control, report scope, traversal, train role, demo auth) |
