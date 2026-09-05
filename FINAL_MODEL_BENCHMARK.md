# FINAL MODEL BENCHMARK — CashGuard AI (SIH26184 prototype)

**Source of truth:** `CURRENT_METRICS.md` + `artifacts/current_metrics.json` (single source of
truth), backed by `artifacts/metrics.json` plus honest re-runs in `artifacts/deep_eval/`.
All figures below are the **honest, leak-free, forecast-safe** numbers from the full 200K dataset
(180-day span, Sep 5 2026). The earlier 0.92x ROC-AUC was invalidated by a same-day label-leakage
fix and is permanently blocked by pre-commit hook.

---

## 1. Active model

- Model: XGBoost with Platt-sigmoid calibration (fitted on the validation slice).
- Split: chronological, `split_day` 2026-07-14. n_train 96,300 · n_val 16,200 · n_test 48,600.
- Positive share (test): 0.0522. Dataset: synthetic, 5 cities, 900 ATMs, 180-day span.
- Features: 44 (Issue-1 architecture, all trailing-window only).

## 2. Headline ranking metrics

| Metric | Value | 95% CI |
|---|---|---|
| ROC-AUC | **0.6456** | [0.6350, 0.6463] (5-fold CV) |
| Accuracy | 0.9393 | — |
| Precision@20 | 0.70 | — |
| Precision@50 | 0.70 | — |
| Precision@100 | 0.67 | — |
| Precision@200 | 0.57 | — |
| Precision@500 | 0.434 | — |
| Precision@1000 | 0.329 | — |
| Recall@20 | 0.0047 | — |
| Recall@50 | 0.0118 | — |
| Recall@100 | 0.0225 | — |

## 3. Benchmark against honest re-run baselines

Precision@K of the model vs. baselines (identical held-out test, Sep 5 2026):

| K | CashGuard P@k | Random P@k | Historical P@k | Volume P@k | Lift vs Random |
|---|---|---|---|---|---|
| 20 | 0.70 | 0.09 | 0.22 | 0.04 | 7.8x |
| 50 | 0.70 | 0.09 | 0.22 | 0.04 | 7.8x |
| 100 | 0.71 | 0.09 | 0.22 | 0.04 | 7.9x |
| 1000 | 0.34 | 0.07 | 0.19 | 0.05 | 4.9x |
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
| A: complaint-only | ~0.50 | ~random; complaints alone cannot separate |
| B: +geography | ~0.50 | adds nothing on its own |
| C: +financial | ~0.58 | main behavioural signal-bearing group |
| D: +temporal | ~0.50 | |
| **E: full model** | **0.6456** | the honest full-pipeline result |

## 6. Generalization splits (honest re-run, Sep 5 2026)

| Split | ROC-AUC | P@100 | Note |
|---|---|---|---|
| random | 0.648 | 0.64 | shuffled ATM-days |
| time_forward | 0.647 | 0.74 | chronological; the production split |
| cold_atm | 0.638 | 0.43 | 180 ATMs held out of training |
| cold_city | 0.666 | 0.55 | city Northsagar held out |
| cold_district | 0.666 | 0.55 | district == city in this synthetic world |
| new_hotspot | 0.673 | 0.51 | top-20% volume ATMs held out |

## 7. Per-feature signal strength

Best single-feature AUCs: `mule_reuse_count_7d` 0.601, `fraud_decay_7d` 0.599,
`round_count_7d` 0.589, `amount_max_7d` 0.577. No feature approaches 0.92, confirming the
leak signature is gone.

## 8. Does the model memorize?

No. Time-forward (0.647) and random (0.648) are comparable, and the genuinely held-out splits
(cold ATM 0.638, cold city/district 0.666, new hot-spot 0.673) show honest generalization.
Failures are reported, not averaged away.

## 9. Bottom line (honest)

On the synthetic single-region test set, the corrected model has meaningful but modest ranking
power (ROC-AUC 0.646), and delivers strong precision at the top of the ranking (0.67-0.71)
relative to naive baselines, at the cost of low absolute recall — an expected base-rate trade-off
at positive share 0.0522. These are methodology-demonstrating synthetic results, not
field-validated fraud metrics.

---

*Companion honesty docs: `REAL_DATA_GAP.md`, `LABEL_VALIDITY.md`, `LIMITATIONS.md`,
`docs/FINAL_LEAKAGE_AUDIT.md`, `docs/LABEL_PROVENANCE_FINAL.md`.*
