# FINAL LEAKAGE AUDIT — CashGuard AI (SIH26184 prototype)

**Date:** 2026-08-30 · **Status:** CLOSED · **Source of truth:** `artifacts/metrics.json` and `artifacts/deep_eval/RECONCILIATION.md`

This document is the honest walkthrough of the label-leakage defect that briefly inflated the
reported ROC-AUC to ~0.92x, what was caught, how it was fixed, and what the honest forecast-safe
numbers are now.

---

## 1. What leaked

The prediction task is: *for every ATM and every day, predict P(any fraud withdrawal at this ATM
in the next 24 hours)*. The label is the ATM-day aggregation of `is_fraud_withdrawal` on the
`withdrawals` table: "any fraud withdrawal during `[day, day+24h)`".

The defect was in how rolling-window **features** were constructed in `backend/ml/features.py`.
Several day-keyed aggregates (complaint counts, complaint-type shares, complaint centroid,
distinct-account counts, counterparty count) were computed at day `d` whose rolling window
**included day `d`'s own complaints/withdrawals** — i.e. the very window being predicted. That
made the features a function of the target, so a held-out "prediction" was partially a
look-up of the answer. This is temporal / target-window leakage (CWE-200 style), not a modelling
error.

The withdrawal-hourly features already used the hour bucket immediately before each day start and
were not the leak; the leak lived in the day-keyed rolling aggregates.

## 2. How it was caught

The tell was the shape of the scores rather than a single number: held-out ROC-AUC around 0.9x
with top-K precision near 1.0 is implausible for a low-base-rate (positive share 0.0522) forecast
built from complaint and withdrawal features. A leak audit of the feature builder + a re-run of
the per-feature AUC surfaced that the aggregates were not shifted before being merged to the day
grid. The audit confirmed the defect, applied the fix, and re-ran every headline evaluation on the
corrected pipeline.

## 3. The fix

In `_shift_day_past`, each day-keyed aggregate frame is now shifted forward by one day so that a
row keyed `day == d` carries **only** data observed strictly before the start of day `d`
(`<= d-1`):

```
frame["day"] = frame["day"] + pd.Timedelta(days=1)
```

This is applied to all day-keyed complaint and account/counterparty aggregates. After the fix,
rolling windows no longer contain the target day. The withdrawal hourly features were already
forecast-safe (they read the hour before the day boundary).

## 4. Before / after numbers

| Metric | Leaky (INVALID) | Honest (forecast-safe) |
|---|---|---|
| Held-out ROC-AUC (immediate re-run) | ~0.9275 | **0.6344** |
| Final consolidated ROC-AUC | — | **0.6273** |
| Accuracy | — | 0.9391 |
| Positive share (test) | — | 0.0522 |
| n_test | — | 48,600 |

The drop from 0.9275 to 0.6344 is the proof of the leak: removing the target-window contamination
removed most of the apparent signal. **Any earlier "0.92x" figure — including 0.927 / 0.9275 — is
the explicitly-invalidated leaky baseline and must never be reported as valid model performance.**
It appears in this document and the audit JSON only as the superseded baseline.

The final honest numbers, read from `artifacts/metrics.json`, are:

- ROC-AUC **0.6456**, accuracy 0.9393
- Precision@20/50/100/200/500/1000 = 0.70 / 0.70 / 0.67 / 0.57 / 0.434 / 0.329
- Recall@20/50/100 = 0.0044 / 0.0107 / 0.0205
- prf@0.5: 62 alerts, P 0.6613, R 0.0138, FAR 0.3387
- prf@0.6: 47 alerts, P 0.6383, R 0.0101, FAR 0.3617
- prf@0.7: 32 alerts, P 0.75, R 0.0081, FAR 0.25
- prf@0.85: 3 alerts, P 0.6667, R 0.0007, FAR 0.3333
- Best single-feature AUC: `days_since_epoch` 0.5604, `counterparty_count_24h` 0.5571,
  `is_weekend` 0.434 (no feature approaches 0.92 — no leak signature remains)
- Baseline volume P@20/50/100 = 0.05 / 0.02 / 0.04; baseline proximity = 0.10 / 0.08 / 0.09
- Lift vs volume @20/50/100 = 13.0 / 32.0 / 17.8; lift vs proximity = 6.5 / 8.0 / 6.78

## 5. Which artifacts were re-run honestly

The following headline artifacts were regenerated on the corrected pipeline (see
`artifacts/deep_eval/RECONCILIATION.md`):

| Artifact | Honest value |
|---|---|
| `generalization_splits.json` | random 0.627 · time_forward 0.6263 · cold_atm 0.5963 · cold_city/cold_district 0.6228 · new_hotspot 0.5847 |
| `ablation.json` | A 0.4938 · B 0.4448 · C 0.5814 · D 0.4219 · **E_full_model 0.6263** |
| `cold_location.json` | 0.6228 (held-out city Northsagar) |
| `operational.json` | 0.6249 |

## 6. Which artifacts remain superseded

These files still hold leaky-era ~0.92x values and are invalid until re-run. They are retained
only for provenance and must not be cited for their AUCs. Full list and honest superseding values
are in `artifacts/deep_eval/RECONCILIATION.md`; the short list is:

- `adversarial_worlds.json` (leaky 0.8038–0.897; honest re-run of completed worlds 0.6321 / 0.6386)
- `drift.json`, `drift_summary.json` (0.9203–0.9349)
- `baseline_war.json`, `feature_audit.json`, `model_disagreement.json`, `permutation_tests.json`,
  `seed_stability.json`, `transfer_readiness.json`, `horizons.json`
- `intervention_simulation.json`, `hourly_eval.json` (illustrative / stale references)

## 7. Residual risks

1. All honest numbers remain scores on **synthetic labels** from a single-region, demo-scale world
   (180 ATMs, single state `State-A`, single district `Northsagar`, split_day 2026-07-07). The
   0.6273 is not a real-world fraud score; see `REAL_DATA_GAP.md` and `LABEL_VALIDITY.md`.
2. Cold-city / cold-district (0.6228) and new-hotspot (0.5847) are the largest honest drops and
   mark the true generalization ceiling of this synthetic world; "district == city" in this data,
   so true multi-jurisdiction RBAC data is not yet exercised.
3. Several deep-eval artifacts remain superseded (section 6) — re-running them on the corrected
   pipeline is straightforward but slow; the headline artifacts are authoritative.
4. Low base rate (0.0522) means precision is strong only at the top K / high thresholds; recall in
   absolute terms is low (e.g. 0.0081 at prf@0.7).

---

*This audit supersedes any earlier audit that reported 0.92x as valid model performance.*
