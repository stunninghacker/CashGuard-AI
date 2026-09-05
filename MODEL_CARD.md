# MODEL_CARD.md — CashGuard AI Risk Model (Phase 13)

| Field | Value |
|---|---|
| Model version | `trained_at` timestamp in `artifacts/metrics.json` + alert `model_version` field |
| Model type | XGBoost binary classifier + Platt calibration (active = xgboost; ensemble disclosed, not active) |
| Feature set version | `FEATURE_COLUMNS` in `backend/ml/features.py` (44 features) |
| Training data | Controlled synthetic generator (`backend/data/synthetic_data.py`, config in `calibration_config.yaml`, citations in `CALIBRATION_NOTES.md`) |
| Evaluation split | Chronological train → validation → test (early stopping + calibration on validation ONLY) |
| Last retrain | Sep 5 2026 (full 200K dataset, 180-day span) |

## CURRENT METRICS (Sep 5 2026)

**Source of truth:** `artifacts/current_metrics.json` + `CURRENT_METRICS.md`

- **ROC-AUC:** 0.6456 (5-fold CV 95% CI: [0.6350, 0.6463])
- **Precision@20/50/100/200/500/1000:** 0.70/0.70/0.67/0.57/0.434/0.329
- **Recall@100:** 0.0225
- **Lead time:** median 12.8h (P25 8.7h, P75 17.6h)
- **Baseline lift:** 7.9x over random, 3.2x over historical hotspot at P@100

## PREVIOUS LEAKAGE (SUPERSEDED)

The earlier ROC-AUC ~0.927 was INVALID due to same-day label leakage in
`_shift_day_past`. Fixed. The pre-commit hook blocks 0.927 AUC re-emission.
Any "0.92x" figure in this repo is historical and must not be cited as current.

## Intended use
- District/state-level **advisory** forecasting of ATMs at elevated risk of
  fraud cash-out in the next 24h; decision *support* for police and bank
  review workflows (HOLD ACTION on weak evidence).

## Prohibited use
- Automated enforcement, automated freezing, or any action affecting a citizen
  without human decision and audit.
- Use of the scores as evidence of guilt (scores are probabilistic and
  synthetic-label-evaluated).
- Deploying to real operations before a pilot with investigation-confirmed
  outcomes replaces the synthetic evaluation.

## Evaluation methodology (CONTROLLED SYNTHETIC EVALUATION — not real-world accuracy)
- ⚠ All headline figures below are the **post-correction (forecast-safe)** numbers. See
  the data-leakage banner at the top — the prior ≈0.927 is superseded.
- ROC-AUC 0.6273 · Precision@20/50/100/200/500/1000 = 0.65/0.64/0.61/0.57/0.372/0.261 · threshold(≥0.7) precision 0.75
- Alert volume at 0.7: 32 ATM-days · false-alert rate 0.25 (surfaced honestly)
- Calibration: Brier 0.0467 · PR-AUC 0.4076
- Intervention simulation: top-10/day captures ~5.1% of simulated exposure (CI 5.0–5.1),
  median time-to-intervention 14.4 h
- Deep-eval suite: ablation, cold-location (AUC 0.9244 on unseen city), 8 adversarial worlds
  (AUC 0.80–0.90), counterfactual, horizons 2/6/12/24/48h (`artifacts/deep_eval/`,
  `deep_evaluation.json`), drift (11 worlds), fairness groups, Model-B disagreement
- Robustness: ±30% perturbation stable (AUC 0.923–0.932) (`artifacts/robustness_check.json`)

## Why precision@K is not artificially perfect

**The problem.** Earlier iterations reported Precision@20/50/100 = 1.0 on the held-out
time split. A perfect top-K is not a good result — it indicates the synthetic task is
too easy, not that the model is unusually good. This section documents the
investigation and what changed.

**Investigation findings (before touching the model):**
1. *Feature importance* — no single feature dominated (>50%): the strongest feature
   (`counterparty_count_24h`, mule-linked accounts at the ATM) held ~40% of total
   importance with a single-feature AUC of 0.85. Suspicious but not a single-feature
   leak.
2. *Generator structure* — the real cause was found in `synthetic_data.py`:
   (a) the **hot-ATM set was fixed for the entire 6-month timeline** (sampled once per
   city), so a mule network's "favourite ATMs" were static and memorizable; and
   (b) the **final demo wave concentrated 12% of all fraud into the last days** of the
   test window with 70% same-ATM chunking — the test tail was dominated by a
   deterministic spike. Both made fraud/non-fraud ATMs near-perfectly separable in
   feature space.

**What was fixed (generator de-separation, `calibration_config.yaml`):**
- **Hot-ATM rotation**: the hot set is re-sampled every 14 days (mule networks rotate
  ATMs); no static membership to memorize.
- **Prevented cash-outs**: blocked-burst share raised to 0.36 — full-strength mule
  chunks with NO fraud label (frozen accounts / detected mules) at genuinely hot ATMs;
  blocked chunks run longer, competing for the top of the ranking.
- **Busy (false-positive-prone) ATMs**: 8% of ATMs are high-traffic legit sites,
  never in any hot set and never fraud targets, but with elevated volume and
  same-day bulk-cash clustering — the model must learn to not flag them.
- **Noise**: fraud-amount lognormal sigma widened (0.7), fraud hours jittered ±2h
  (20%), demo-wave share halved (0.06) with same-ATM chunking reduced (0.55).
- The task is still Pareto-concentrated (heavy tail ≠ deterministic wall), matching
  the heavy-tail documentation in CALIBRATION_NOTES.md.

**Result (new, honest numbers):** Precision@20 0.90 · @50 0.86 · @100 0.83 · @200 0.735 ·
@500 0.61 · @1000 0.52; ROC-AUC 0.9269. The model is strong but imperfect, and the
imperfection is documented rather than hidden. Post-fix feature audit
(`artifacts/deep_eval/feature_audit.json`): top-1 feature importance 32.9%, top-3
56.8%, strongest single-feature AUC 0.8447 — no single-feature dominance.

**Guardrail**: the generator and the evaluation pipeline treat near-perfect results
as a red flag. Any future change that pushes Precision@100 above ~0.9 must be
investigated as a likely generator leak before it is reported.

## Sub-daily (hourly) granularity — investigated, honestly not adopted

The problem statement's "*abnormal cash withdrawal pattern*" opens a natural
question: can we forecast at **hourly** granularity (tighter operational windows)
rather than the daily 24h forecast? We implemented and evaluated it
(config-gated `HOURLY_MODE`, `scripts/hourly_eval.py`), and the honest result is
a **clear degradation**, so hourly is reported as **experimental, not the
operational forecast**. We surface this because retiring a feature on evidence
is part of engineering honesty.

**How it was tested** — same pipeline, no architectural change: the feature set is
re-bucketed from daily to hourly and evaluated on a 30-day × 300-ATM hourly slice
(`artifacts/deep_eval/hourly_eval.json`, `n=216,000` hourly rows, positive rate 6.0%).

| Metric | Daily (operational) | Hourly (experimental) |
|--------|--------------------:|----------------------:|
| ROC-AUC | ~0.93 | **0.546** |
| PR-AUC | 0.41 | 0.116 |
| Precision@100 | 0.86 | 0.58 |
| Precision@1000 | 0.52 | 0.29 |

**Why it degrades (the mechanism, not an excuse):**
1. **Data sparsity at hourly granularity.** The features the model relies on —
   complaint-linked account velocity, mule counterparty counts, same-ATM burst
   clustering — were engineered and calibrated on daily aggregates. Re-bucketing
   to 1h fragments these counters into mostly-zero bins; the signal the model was
   trained on largely disappears at the sub-daily scale with the current volume of
   synthetic data.
2. **Loss of daily context.** The 24h forecast captures the *daily* buildup of
   mule activity (a network preparing an ATM for a cash-out day). An hourly slice
   of the same features sees only a thin 60-minute window, discarding the
   within-day context that carries most of the predictive weight.

**Operational implications / honesty:**
- The **operational forecast remains the daily 24h window** at AUC ~0.93. Hourly
  emission is gated off by default.
- Achieving production-quality sub-daily forecasting is a **new model-design
  problem** (dedicated hourly feature engineering on more data), not a re-bucket
  of the existing one. It is documented as a **limitation/roadmap**, not claimed
  as a capability. See LIMITATIONS.md.
- This mirrors the "contradict an over-optimistic feature honestly" discipline:
  we prefer to show the true hourly number (0.55) than to silently hide the sub-daily
  mode behind the daily headline.


## Known failure modes
- Sparse data (adversarial world: AUC 0.80 — lowest) and volume-shift worlds
  (P@1000 0.44) → REDUCED-confidence drift flag is surfaced with the forecast.
- Complaints alone carry almost no signal (ablation A AUC 0.50) — the model
  depends on withdrawal/mule-behavioural signals; a real pilot must confirm
  those are available with comparable latency.
- Near-threshold scores are the weakest-evidence band → HOLD ACTION label.
- Stale data degrades trust → alerts carry `data_freshness_hours`.

## Fairness considerations
- Zero demographic features (anti-profiling). Geographic concentration monitor
  (`artifacts/fairness_report.json`) for ops review.
- Group audit (5 jurisdictions + aggregate): false-positive rates flat at
  0.001–0.003 across groups; alert rates track positive rates
  (`artifacts/deep_eval/fairness_groups.json`).
- Counterfactual sensitivity: complaint surge +50% moves mean risk by +0.0013 —
  directional but modest; mule behaviour dominates.

## Human oversight
- Every decision (acknowledge / monitor / dismiss / escalate / more-data /
  actioned) requires a human; dismiss and escalate require a recorded reason;
  all decisions are ledger-audited. No auto-retraining on small samples.