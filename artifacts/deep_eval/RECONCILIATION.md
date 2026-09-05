# Deep-Evaluation Integrity Reconciliation

**Date:** Sep 5, 2026 (updated with 200K atomic dataset)  
**Scope:** `artifacts/deep_eval/*.json`  
**Status:** **PASS** — all honest metrics confirmed, no anomalies or leaks detected

---

## Current honest metrics (Sep 5, 2026)

| Metric | Value | Source |
|---|---|---|
| Headline ROC-AUC | **0.6456** | `artifacts/metrics.json` |
| 5-fold CV 95% CI | [0.6350, 0.6463] | `scripts/cross_val_auc_ci.py` |
| P@20/50/100/200/500/1000 | 0.70/0.70/0.67/0.57/0.434/0.329 | `artifacts/metrics.json` |
| Threshold(>=0.5) precision | 0.70 | `artifacts/metrics.json` |
| Generalization splits | 0.638–0.673 | `artifacts/deep_eval/generalization_splits.json` |
| Baseline war P@100 lift | 7.9× random, 3.2× historical, 17.8× volume | `artifacts/deep_eval/baseline_war.json` |
| Median lead time | 12.8h (P25 8.7h, P75 17.6h) | `scripts/generalization_splits.py` |

---

## Previously superseded (leakage-era figures)

These are retained for provenance only. All 0.92x AUC figures were invalidated by
same-day label leakage in `_shift_day_past`, now fixed. The pre-commit hook blocks
re-emission permanently.

| Artifact | Old (leaky) | Current (honest) |
|---|---|---|
| `generalization_splits.json` | ~0.9274 | 0.638–0.673 |
| `ablation.json` | 0.9265 (E_full_model) | ~0.50–0.58 (ablation groups) |
| `baseline_war.json` | 0.9261–0.9276 | P@100 0.71 (CashGuard) |
| `seed_stability.json` | 0.9178–0.9266 | Model seed spread 0.0025 AUC |
| `permutation_tests.json` | baseline 0.9259 | Baseline 0.6471; label permutation 0.4828 |

---

## Action plan for the panel

1. Cite **only** the honest reference values above.
2. Any `0.92x` figure in an older doc/artifact is the leaky baseline and **is not** the model result.
3. All scripts have been re-run on the corrected pipeline with the 200K atomic dataset.
