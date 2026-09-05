# SIH-26184 Deliverable Matrix

**Date:** 2026-09-05 · This matrix maps each SIH-26184 deliverable / claim to its evidence file,
its honest status, and the honest headline value carried by that deliverable.

**Integrity note:** The corrected, forecast-safe ROC-AUC is **0.6456** (5-fold CV [0.635, 0.646]).
Any earlier 0.92x figure was invalidated by a same-day label-leakage fix and is permanently blocked.
The previous 0.6273 figure was based on a 40-day withdrawal dataset; the full 200K 180-day dataset
yields 0.6456. **Authoritative source of truth: `CURRENT_METRICS.md` + `artifacts/current_metrics.json`.**
Every headline value below is the honest (Sep 5 2026) number. All figures are on **synthetic**
single-region labels (`REAL_DATA_GAP.md`, `LABEL_VALIDITY.md`).

| Deliverable / claim | Evidence file(s) | Status | Honest headline value |
|---|---|---|---|
| **Model card** (model type, split, metrics) | `MODEL_CARD.md` | **Done** | ROC-AUC 0.6456; P@20/50/100/200/500/1000 = 0.70/0.70/0.67/0.57/0.434/0.329; XGBoost + Platt, 44 features, split_day 2026-07-14, n_test 48,600, positive_share 0.0522 |
| **Leakage audit** | `artifacts/leakage_audit.json`, `docs/FINAL_LEAKAGE_AUDIT.md`, `tests/test_temporal_leakage.py` | **Done** | Leaky 0.9275 invalid; honest 0.6456 on full 200K dataset; 9/9 automated tests pass |
| **Model benchmark** | `FINAL_MODEL_BENCHMARK.md`, `artifacts/deep_eval/baseline_war.json` | **Done** | ROC-AUC 0.6456; P@100=0.71; lift vs random 7.9x, vs historical 3.2x, vs volume 17.8x |
| **Limitation docs** | `FINAL_EXTERNAL_LIMITATIONS.md`, `LIMITATIONS.md`, `REAL_DATA_GAP.md` | **Done** | Synthetic single-region, 900 ATMs, no real per-ATM benchmark; cite final values only |
| **Security audit** | `docs/audits/FINAL_SECURITY_AUDIT.md`, `scripts/test_security_regression.py` | **Done** | RBAC row-scoping verified; JWT+bcrypt; tamper-evident ledger; path-traversal fix |
| **Responsible-use doc** | `docs/RESPONSIBLE_OPERATIONAL_USE.md` | **Done** | Guardrails: simulated-scenario invariant, human-in-the-loop, threshold guidance, RBAC scoping |
| **Metric governance** | `docs/METRIC_GOVERNANCE.md` | **Done (NEW Sep 5)** | Single source of truth hierarchy; update protocol; no 0.92x references without SUPERSEDED marker |
| **Demo** | `DEMO_SCRIPT.md`, `DEMO_VIDEO.md`, `LIVE_DEMO.md`, `run.py`, frontend | **Done** | 900-ATM single-region synthetic live demo; simulated-scenario workflow |
| **Label provenance** | `docs/LABEL_PROVENANCE_FINAL.md`, `LABEL_VALIDITY.md` | **Done** | Labels are SYNTHETIC ground truth; 0.6456 is a synthetic-label score, not real fraud |
| **Intervention value** | `INTERVENTION_VALUE_EVALUATION.md`, `artifacts/deep_eval/baseline_war.json` | **Done (illustrative only)** | P@100=0.71; 7.9x lift over random; value claim is illustrative, no real benchmark |
| **Blockchain justification** | `BLOCKCHAIN_JUSTIFICATION.md`, `BLOCKCHAIN_UPGRADE_PATH.md` | **Done** | Tamper-evident SHA-256 hash chain (demo-grade), not a public blockchain |
| **Compliance** | `docs/SIH26184_FINAL_COMPLIANCE.md` | **Done (NEW Sep 5)** | Full SIH26184 requirement mapping with evidence |
| **Judge FAQ** | `docs/JUDGE_FAQ_FINAL.md` | **Done (NEW Sep 5)** | 20 questions with honest answers |

## Honest status of remaining / partial items

1. **All headline metrics updated Sep 5 2026** on full 200K dataset (ROC-AUC 0.6456).
2. **Superseded deep-eval artifacts** still hold older values; see `artifacts/deep_eval/RECONCILIATION.md`.
3. **Still pending / gap to close:** a real, multi-jurisdiction dataset; a real per-ATM fraud benchmark;
   live traffic. These are closed only by an authorized real-data pilot per `REAL_DATA_GAP.md`.

Every quantitative claim above traces to `artifacts/metrics.json` (Sep 5 2026) and the honest re-runs.
No number is invented.
