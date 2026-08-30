# SIH-26184 Deliverable Matrix

**Date:** 2026-08-30 · This matrix maps each SIH-26184 deliverable / claim to its evidence file,
its honest status, and the honest headline value carried by that deliverable.

**Integrity note:** The corrected, forecast-safe ROC-AUC is **0.6273**. Any earlier 0.92x figure
was invalidated by a same-day label-leakage fix (see `artifacts/leakage_audit.json` and
`docs/FINAL_LEAKAGE_AUDIT.md`) and may appear only as the explicitly-superseded leaky baseline.
**Authoritative source of truth: `CURRENT_METRICS.md` + `artifacts/current_metrics.json`.**
Every headline value below is the honest (post-fix) number. All figures are on **synthetic**
single-region labels (`REAL_DATA_GAP.md`, `LABEL_VALIDITY.md`).

| Deliverable / claim | Evidence file(s) | Status | Honest headline value |
|---|---|---|---|
| **Model card** (model type, split, metrics) | `MODEL_CARD.md` | **Partial** — honest headline (ROC-AUC 0.6273, P@20..1000) present, but several deep-eval/robustness figures in it are still the stale leaky-era ones; cross-reference the honest ones in `FINAL_MODEL_BENCHMARK.md` | ROC-AUC 0.6273; P@20/50/100/200/500/1000 = 0.65/0.64/0.61/0.57/0.372/0.261; XGBoost + Platt, split_day 2026-07-07, n_test 48,600, positive_share 0.0522 |
| **Leakage audit** | `artifacts/leakage_audit.json`, `docs/FINAL_LEAKAGE_AUDIT.md`, `artifacts/deep_eval/RECONCILIATION.md` | **Done** | Leaky 0.9275 invalid; honest 0.6344 immediate re-run; final 0.6273 |
| **Model benchmark** | `FINAL_MODEL_BENCHMARK.md` | **Done** | ROC-AUC 0.6273; lift vs volume @20/50/100 = 13.0/32.0/15.25; vs proximity = 6.5/8.0/6.78 |
| **Limitation docs** | `FINAL_EXTERNAL_LIMITATIONS.md`, `LIMITATIONS.md`, `REAL_DATA_GAP.md` | **Done (final); `LIMITATIONS.md` partial** | Synthetic single-region, 180 ATMs, no real per-ATM benchmark; cite final values only |
| **Security audit** | `docs/audits/FINAL_SECURITY_AUDIT.md`, `docs/audits/SECURITY_AUDIT.md`, `docs/audits/AUDIT_REPORT.md` | **Done** | RBAC row-scoping verified live (district/bank/state/I4C); JWT+bcrypt; tamper-evident ledger; prototype-grade (no TLS/CSP in demo, documented) |
| **Responsible-use doc** | `docs/RESPONSIBLE_OPERATIONAL_USE.md` | **Done** | Guardrails: simulated-scenario invariant, no-alerts-on-calm-days honesty (max live risk ~0.0627), human-in-the-loop, threshold guidance, RBAC scoping verified, PoC-only |
| **PITCH** | `presentation/PITCH.md`, `SIH_CashGuard_AI_Presentation.pptx` | **Partial — ensure all quantitative AUCs cited as honest 0.6273** | Honesty-first demo pitch; synthetic-label caveat stated first |
| **Demo** | `DEMO_SCRIPT.md`, `DEMO_VIDEO.md`, `LIVE_DEMO.md`, `run.py`, frontend | **Done (demo-scale, single region)** | 180-ATM single-district synthetic live demo; simulated-scenario workflow with SIMULATED banner |
| **Label provenance** | `docs/LABEL_PROVENANCE_FINAL.md`, `LABEL_VALIDITY.md` | **Done** | Labels are SYNTHETIC ground truth from the generator; 0.6273 is a synthetic-label score, not real fraud |
| **Intervention value** | `artifacts/intervention_value_final.json`, `INTERVENTION_VALUE_EVALUATION.md` | **Done (illustrative only)** | prf@0.5/0.6/0.7/0.85 = 62/47/32/3 alerts at P 0.66/0.64/0.75/0.67; value claim is illustrative, no real benchmark |
| **Intervention priority** | `INTERVENTION_PRIORITY.md` | Done (synthetic) | Lead-time median 15.9h (p25 10.6, p75 19.7); horizon-dependent |
| **Blockchain justification** | `BLOCKCHAIN_JUSTIFICATION.md`, `BLOCKCHAIN_UPGRADE_PATH.md` | Done | Tamper-evident SHA-256 hash chain (demo-grade), not a public blockchain |

## Honest status of remaining / partial items

1. **MODEL_CARD.md is partial.** Its headline (0.6273) is correct and current, but it still embeds
   leaky-era deep-eval/robustness AUCs (e.g. lines citing ~0.92x and old P@100 0.83). Until cleaned,
   treat `FINAL_MODEL_BENCHMARK.md` as the authoritative honest benchmark.
2. **LIMITATIONS.md is partial.** It still quotes pre-fix precision figures (e.g. P@20 0.90) and a
   `-0.927` -era lead-time. The final, honest limitation statement is `FINAL_EXTERNAL_LIMITATIONS.md`.
3. **PITCH.md / PPTX** must not cite any 0.92x AUC as model performance. The correct headline is
   ROC-AUC 0.6273 on synthetic labels.
4. **Superseded deep-eval artifacts** (`adversarial_worlds.json`, `drift*.json`, `baseline_war.json`,
   `feature_audit.json`, `horizons.json`, `model_disagreement.json`, `permutation_tests.json`,
   `seed_stability.json`, `transfer_readiness.json`, `intervention_simulation.json`, `hourly_eval.json`)
   still hold leaky values and must not be cited for AUCs; see `artifacts/deep_eval/RECONCILIATION.md`.
5. **Still pending / gap to close:** a real, multi-jurisdiction (true RBAC) dataset; a real
   per-ATM fraud benchmark for calibration (none exists); live traffic. These are closed only by an
   authorized real-data pilot per `REAL_DATA_GAP.md`.

Every quantitative claim above traces to `artifacts/metrics.json` and the honest re-runs listed in
`artifacts/leakage_audit.json`. No number is invented.
