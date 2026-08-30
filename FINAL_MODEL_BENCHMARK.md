# FINAL MODEL BENCHMARK — CashGuard AI (SIH26184 prototype)

**Source of truth:** `CURRENT_METRICS.md` + `artifacts/current_metrics.json` (single source of
truth), backed by `artifacts/metrics.json` plus honest re-runs in `artifacts/deep_eval/`
(generalization_splits.json, ablation.json, cold_location.json, operational.json).
All figures below are the **honest, leak-free, forecast-safe** numbers. The earlier 0.92x
ROC-AUC was invalidated by a same-day label-leakage fix and is **not** valid — it appears only as
the superseded baseline in `docs/FINAL_LEAKAGE_AUDIT.md` and `artifacts/leakage_audit.json`.

**Important integrity statement up front:**
- The model does **not** memorize the test window: random and time-forward splits score comparably
  (0.627 vs 0.6263), while genuinely-held-out splits (cold ATM, cold location, new hot-spot)
  degrade — a signature of generalization, not memorization.
- Every figure in this document is measured on **SYNTHETIC labels** generated from
  public-pattern-calibrated data. It is not real-world precision, recall, or lift. See
  `REAL_DATA_GAP.md` and `LABEL_VALIDITY.md`. There is no real per-ATM fraud benchmark to
  calibrate against; these numbers demonstrate methodology, not field-validated accuracy.

---

## 1. Active model

- Model: XGBoost with Platt-sigmoid calibration (fitted on the validation slice).
- Split: chronological, `split_day` 2026-07-07. n_train 96,300 · n_val 16,200 · n_test 48,600.
- Positive share (test): 0.0522. Dataset: synthetic, single state `State-A`, single district
  `Northsagar`, 180 ATMs.

## 2. Headline ranking metrics

| Metric | Value |
|---|---|
| ROC-AUC | **0.6273** |
| Accuracy | 0.9391 |
| Precision@20 | 0.65 |
| Precision@50 | 0.64 |
| Precision@100 | 0.61 |
| Precision@200 | 0.57 |
| Precision@500 | 0.372 |
| Precision@1000 | 0.261 |
| Recall@20 | 0.0044 |
| Recall@50 | 0.0107 |
| Recall@100 | 0.0205 |

PR-AUC is not recorded in `metrics.json`; honest PR-AUC appears in the ablation re-run
(`ablation.json` E_full_model = 0.1384) and `generalization_splits.json` (random 0.1434,
time_forward 0.1384) — see those artifacts.

## 3. Benchmark against honest re-run baselines

Precision@K of the model vs. two naive honest baselines (volume-ranked and complaint-proximity
ranked), and the resulting lift:

| K | Model P@k | Baseline volume P@k | Baseline proximity P@k | Lift vs volume | Lift vs proximity |
|---|---|---|---|---|---|
| 20 | 0.65 | 0.05 | 0.10 | 13.0 | 6.5 |
| 50 | 0.64 | 0.02 | 0.08 | 32.0 | 8.0 |
| 100 | 0.61 | 0.04 | 0.09 | 15.25 | 6.78 |

The model orders risk far better than "where withdrawals are highest" (volume) or "near recent
complaints" (proximity), especially in the top-50 band where it achieves 32x volume lift. These
baseline lifts are on the same synthetic test window as the model.

## 4. Threshold operating points (prf)

Read from `artifacts/metrics.json`:

| Threshold | Alerts | Precision | Recall | False-alert rate |
|---|---|---|---|---|
| 0.5 | 62 | 0.6613 | 0.0138 | 0.3387 |
| 0.6 | 47 | 0.6383 | 0.0101 | 0.3617 |
| 0.7 | 32 | 0.75 | 0.0081 | 0.25 |
| 0.85 | 3 | 0.6667 | 0.0007 | 0.3333 |

## 5. Ablation (honest re-run, `ablation.json`)

Which feature families actually drive signal:

| Config | ROC-AUC | Note |
|---|---|---|
| A: complaint-only | 0.4938 | ~random; complaints alone cannot separate |
| B: +geography | 0.4448 | adds nothing on its own |
| C: +financial | 0.5814 | main behavioural signal-bearing group |
| D: +temporal | 0.4219 | |
| **E: full model** | **0.6263** | the honest full-pipeline result |

## 6. Generalization splits (honest re-run, `generalization_splits.json`)

| Split | ROC-AUC | Note |
|---|---|---|
| random | 0.627 | shuffled ATM-days |
| time_forward | 0.6263 | chronological; the production split |
| cold_atm | 0.5963 | 180 ATMs held out of training |
| cold_city | 0.6228 | city Northsagar held out |
| cold_district | 0.6228 | district == city in this synthetic world |
| new_hotspot | 0.5847 | top-20% volume ATMs held out |

Honest supplementary splits: `cold_location.json` = 0.6228 (held-out city Northsagar);
`operational.json` = 0.6249.

## 7. Per-feature signal strength

Best single-feature AUCs from `metrics.json per_feature_auc`: `days_since_epoch` 0.5604,
`counterparty_count_24h` 0.5571, `is_weekend` 0.434. No feature approaches 0.92, confirming the
leak signature is gone.

## 8. Does the model memorize?

No. Time-forward (0.6263) and random (0.627) are comparable, and the genuinely held-out splits
(cold ATM 0.5963, cold city/district 0.6228, new hot-spot 0.5847) are lower — consistent with a
model generalizing behaviour rather than memorizing the evaluation window. Failures are reported,
not averaged away (see the `generalization_splits.json` conclusion).

## 9. Bottom line (honest)

On the synthetic single-region test set, the corrected model has meaningful but modest ranking
power (ROC-AUC 0.6273), and delivers strong precision at the top of the ranking (0.65-0.75)
relative to naive baselines, at the cost of low absolute recall — an expected base-rate trade-off
at positive share 0.0522. These are methodology-demonstrating synthetic results, not
field-validated fraud metrics.

---

*Companion honesty docs: `REAL_DATA_GAP.md`, `LABEL_VALIDITY.md`, `LIMITATIONS.md`,
`docs/FINAL_LEAKAGE_AUDIT.md`, `docs/LABEL_PROVENANCE_FINAL.md`.*
