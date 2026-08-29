# LABEL PROVENANCE — FINAL (CashGuard AI, SIH26184 prototype)

**Date:** 2026-08-30 · Companion: `LABEL_VALIDITY.md`, `REAL_DATA_GAP.md`,
`docs/FINAL_LEAKAGE_AUDIT.md`, `artifacts/leakage_audit.json`.

## 1. What the labels are

The labels are **SYNTHETIC**. There is no real NCRP/CFCFRMS or bank data in this repository
(`REAL_DATA_GAP.md`). The label is `is_fraud_withdrawal` on the `withdrawals` table — a boolean the
data generator (`backend/data/synthetic_data.py`) marks at transaction creation time on every
withdrawal it creates (mule cash-out chunk vs normal). It is aggregated to the ATM-day target
`build_target(...)`: **"any fraud withdrawal at this ATM during `[day, day+24h)`"**. In this sense
the label is the generator's own ground truth of the simulation, not a report, a model output, or a
human investigation outcome.

## 2. How the labels are built

1. The generator produces withdrawal records and tags each with `is_fraud_withdrawal` at creation
   time; values are immutable from generation.
2. `build_target(wd, atms, days)` groups fraud withdrawals by `(atm_id, day)` and sets the target to
   1 if any fraud withdrawal occurred at that ATM in the 24h window starting that day.
3. `FEATURE_COLUMNS` in `backend/ml/features.py` never includes `is_fraud_withdrawal` as a feature;
   it appears in the feature module only as the target `y` (grep-verified per `LABEL_VALIDITY.md`).
4. Split is chronological from `split_day` `2026-07-07`; n_train 96,300, n_val 16,200,
   n_test 48,600, positive share 0.0522.

## 3. Validity

The label is internally valid for the synthetic world: "confirmed fraud" equals the generator's
ground truth, and `LABEL_VALIDITY.md` documents three independent checks that `is_fraud_withdrawal`
cannot leak into the features. The honest point is that this validates the *methodology* (temporal
splitting, precision@K, baseline lifts), not real-world fraud. For a real pilot the outcome ladder
must separate **reported / suspected / confirmed / recovered / unknown** and pre-register which rung
is the label before looking at real data (`LABEL_VALIDITY.md` section "Label taxonomy",
`REAL_DATA_VALIDATION_PROTOCOL.md`).

## 4. Verification that label-steering introduces no feature-label leakage after the fix

The leakage audit (`artifacts/leakage_audit.json`, `docs/FINAL_LEAKAGE_AUDIT.md`) confirmed the root
cause was same-day **feature/label construction** in `backend/ml/features.py` `_shift_day_past`
(rolling-window features computed at day `d` included day `d`'s own records — the very window being
predicted). The fix shifts every day-keyed aggregate forward by one day so features use only
`<= d-1`.

Evidence the steering introduces no leakage after the fix:
- Honest held-out ROC-AUC drops from the leaky 0.9275 to **0.6273** (0.6344 immediate re-run) — the
  inflated signal is gone.
- The strongest single-feature AUC is now `days_since_epoch` 0.5604, followed by
  `counterparty_count_24h` 0.5571; no feature approaches 0.92 (see `metrics.json per_feature_auc`),
  so no leak signature remains.
- Random (0.627) and time-forward (0.6263) splits agree, and genuinely held-out splits (cold ATM
  0.5963, cold city/district 0.6228, new hot-spot 0.5847) degrade — consistent with generalization,
  not memorization (`generalization_splits.json`).
- The old leak feature `fraud_withdrawals_24h` was removed; the 1.0-style single-feature-dominance
  pattern it produced is now treated as a red flag by the per-feature-AUC audit.

## 5. The honest implication

The **0.6273 ROC-AUC is a score on synthetic labels, not a real-world fraud score.** It is the
honest, leak-free measure of separability within this simulated world. There is no real per-ATM fraud
benchmark to compare against, and no calibration against a real baseline has been or can be performed
on synthetic data (`REAL_DATA_GAP.md`, `FINAL_EXTERNAL_LIMITATIONS.md`). All precision@K, lift, and
lead-time figures carry the same caveat. Any presentation must lead with this limitation rather than
implying field-validated performance.

---

*This document supersedes any label-provenance claim that presented the leaky ~0.92x score as valid.*
