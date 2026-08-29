# FINAL_10_10_GENERATOR_LEAKAGE.md — Leakage war, verified fresh


> **WARNING: DATA-LEAKAGE CORRECTION (2026-08-29)** - This document's reported ROC-AUC figures (~0.92x) came from a SAME-DAY LABEL-LEAKAGE bug in feature engineering (backend/ml/features.py, `_shift_day_past`), now fixed. The honest forecast-safe ROC-AUC is **0.6273** (leaky 0.9275 -> corrected 0.6344 in the proof). On calm days the live model scores every ATM low (max ~0.11) and produces **no alerts**; any populated high-risk alert view is the opt-in, clearly-labelled **"Load Simulated Scenario"** mode (SCRIPTED, not live model output). Treat all 0.92x figures in this doc as superseded. Full detail: MODEL_CARD.md, VERIFICATION_LOG.md (P1.5).
Red-team question: does CashGuard's performance merely echo the generator's
construction rules (a "leak") rather than a transferable signal?

**This run re-executed the leakage checks live** (`permutation_tests.py`,
`seed_stability.py`, `generalization_splits.py`) and cross-checked the stored
artifacts. Findings below are from live output, not taken on trust.

## 1. Target leakage — NONE found (permutation tests, live)
- **Label permutation**: AUC → **0.488** (chance ~0.5). The pipeline cannot
  memorize arbitrary target labels; performance requires real feature→target
  signal.
- **Identity memorisation**: NO ATM/city/district identity columns exist in
  `FEATURES` (identity lives in meta only); row-order shuffle → AUC unchanged
  (0.926 vs 0.926). No order/identity memorisation.
- **City-feature permutation**: AUC 0.925 vs 0.926 baseline → **<0.001 drop**.
  Shuffling the complaint/geo features changes almost nothing.

## 2. The honest finding the leakage war exposes
Permutation + ablation agree: **the model's power is carried by withdrawal /
mule-account behavioural features, NOT by complaints or geography.**
- Live `per_feature_auc`: `counterparty_count_24h` = **0.8265**; every
  complaint/spatial feature ≤ 0.55 (`n_complaints_city_24h` 0.516,
  `dist_to_complaint_centroid_km` 0.504, `hawkes_intensity_24h` 0.509).
- Ablation (stored `adversarial_worlds.json`): complaints-only 0.50 →
  +geography 0.55 → +financial **0.93**.

Two very different readings, both must be stated:
- **Good (no leak):** `counterparty_count_24h` is legitimate — it counts
  complaint-linked mule accounts withdrawing at that ATM in the trailing 24h
  (window ends before forecast; label is next-24h fraud). It is prediction-time
  safe and beats "busy ATM" baselines, so it is not the trivial generator leak.
- **Bad (judge critique):** the SIH problem is *complaint-driven prediction of
  cash-out BEFORE it happens*. Our strongest signal (0.83 AUC) is the mule
  account that is ALREADY withdrawing — more "early detection of ongoing mule
  cash-out" than "forecast of a future hotspot from complaints". Because the
  synthetic generator *defines* fraud cash-out to follow complaint-linked mule
  activity, the model learns exactly that coupling — which the real NCRP data
  does not guarantee at the same strength.

Conclusion: the leakage war shows NO target rediscovery, but it cannot falsify
the deeper structural critique — **the "proactive-from-complaints" promise is
the weakest claim and depends on real-data validation**, not on more
synthetic tuning. This is documented, not averaged away.

## 3. Seed fragility (live)
- Model seeds (same data): AUC 0.9258–0.9264, P@100 0.84–0.86 — deterministic.
- **Generator seeds (fresh draws): P@100 0.50–0.67, P@1000 0.321–0.382.**
  ROC-AUC is stable, but top-of-ranking precision is draw-sensitive. Reported
  honestly; headline numbers should cite the range, not the fixed-seed peak.

## 4. Distribution shift (`drift.json`, existing artifact, consistent)
Threshold precision 0.55–0.83 across adversarial worlds; system flags REDUCED
confidence instead of overclaiming.

## Verdict
No target-rediscovery leak. Residual risk is the honest one: synthetic
complaint→mule→cash-out coupling transfers to the real world only if real data
shows the same strength — validate via the pilot on authorized data
(`REAL_DATA_VALIDATION_PROTOCOL.md`).
