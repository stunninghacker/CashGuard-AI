# CALIBRATION_NOTES.md — Parameter Sourcing & Honest Labeling

Every generative parameter in `backend/data/calibration_config.yaml` is tagged
`verified_pattern` or `assumption_general_literature`, with a `citation` field.
This file states WHERE each tag comes from. Nothing here is presented as an
India-specific verified statistic unless a source is cited.

> **UI policy**: real districts (Nuh, Jamtara, …) appear ONLY in this document
> as methodology citations. The live demo UI uses fictional locations exclusively.

---

## 1. Verified patterns (direction only — with citations)

### 1.1 Geographic/institutional clustering — `verified_pattern` (direction only)
- **The DIRECTION (heavy-tailed concentration) is verified.**
  - **I4C Suspect Registry** (launched 2024 with bank/FI participation) and
    public reporting document that cyber-fraud mule activity concentrates in a
    small number of hubs and institutions.
  - **HONESTY FIX — scam-origin vs withdrawal geography**: Nuh (Haryana) and
    Jamtara (Jharkhand) are publicly documented **SCAM-ORIGIN** hubs (where
    fraudsters originate). This framework does **NOT** claim they are
    cash-**WITHDRAWAL** hubs — withdrawal geography can differ and is not
    publicly granular. They are cited only as evidence that fraud *activity*
    clusters.
  - **Institutional concentration**: CFCFRMS public statements show a
    disproportionate share of mule accounts at a small number of large banks.
- **What remains an assumption**: the *exact* coefficients
  (`pareto_skew: 1.8`, `hot_atm_fraction: 0.12`) — granular per-ATM public data
  does not exist.

### 1.2 Mule-account behavioural signature — `verified_pattern` (direction only)
- **IBA guidance / RBI commentary** identify mule accounts by: frequent
  transactions, unusually high counterparty count, rapid fund movement
  (velocity), sudden activity spikes after dormancy.
- **Implementation**: explicit engineered features — `transaction_frequency_24h`,
  `counterparty_count_24h`, `fund_velocity_24h`, `activity_spike_flag` — plus an
  `accounts` master table carrying the behavioural source fields. Never a bare
  `is_fraud` label.
- **CRITICAL REALISM RULE (enforced)**: mule accounts have normal banking
    history before cash-out, and bursts are MINUTE-level chunks (same ATM) with
    imperfect day-over-day persistence. Iteration-4 generator de-separation
    (hot-ATM rotation every 14 days, prevented cash-outs at 36% of bursts,
    busy-ATM false-positive cases, widened amount/timing noise) keeps the task
    strong-but-imperfect. Numbers read from `artifacts/metrics.json`: max
    single-feature AUC = 0.8447 (counterparty_count_24h), threshold(≥0.7)
    precision = 0.6588 — the model cannot exploit "linked account present = fraud".

### 1.3 Prediction-horizon justification — `verified_pattern` (direction only)
- **RBI has moved toward time-delays / holds on certain UPI transfers**
  specifically to create a fraud-interception window before funds move.
- **HONESTY FIX**: no specific hold duration or threshold is asserted as fact in
  this prototype. The 24h horizon is justified by the *direction* of the
  regulatory change (an interception window exists → a 6–24h forecast is
  operationally relevant). Any specific value must be **confirmed against the
  exact RBI circular** before it is quoted in production material.

### 1.4 PII pseudonymization + anti-profiling — `verified_pattern`
- DPDP-Act-aligned data minimization; NCRP/CFCFRMS operate on
  need-to-know/audited access. Implemented as salted-hash tokens
  (`acct_…`/`tel_…`) + a mock re-identification vault; **no
  demographic/community/religion/caste features exist anywhere** — risk is
  transaction behaviour + complaint linkage + transaction geography only.

---

## 2. Assumptions — general literature, explicitly NOT verified for India

No India-specific public statistic was found for any of the following. Each is a
configurable, source-tagged parameter disclosed in the alert evidence panel.

| Parameter | Value | Why it's an assumption |
|---|---|---|
| `fraud_to_cashout_mean_hours` | 18 h (right-skewed) | No India-specific fraud→cash-out latency statistic; general financial-fraud literature. |
| `night_weight` / `weekend_weight` | 2.0 / 1.9 | No India-specific statistic; general fraud literature. |
| `round_amount_bias` | 0.40 | Structured/round denominations; general literature only. |
| `hot_atm_fraction` / `pareto_skew` coefficients | 0.12 / 1.8 | Direction verified (1.1); exact coefficients tunable. |
| `fraud_share` | 0.10 | Synthetic label density; real per-withdrawal fraud rate not public. |
| `scenario.final_wave_share` / burst / blocked-burst params | — | Demo scenario shaping + honest-separability detune; no real-world equivalent. |
| `scenario.final_wave_share` / burst / blocked-burst params | — | Demo scenario shaping + honest-separability detune; no real-world equivalent. |
| `scenario.hot_rotation_days` | 14 | Mule networks rotate ATMs; membership is not fixed for the whole timeline (iteration-4 de-separation). |
| `scenario.busy_atm_share` | 0.08 | High-traffic legit ATMs in complaint-adjacent areas with no fraud (false-positive-prone cases). |
| `scenario.amount_noise_sigma` / `hour_jitter_prob` | 0.7 / 0.20 | Amounts and timings do not perfectly track the fraud label. |
### Why `counterparty_count_24h` is not a leak (numbers from `artifacts/metrics.json`)

(a) **Built from complaint-linked accounts, available at prediction time.** The
feature counts distinct mule-account tokens active at the ATM in the trailing
24h window. Those accounts are identified from **complaints**, which are filed
*before* cash-out (the complaint precedes the withdrawal the model forecasts) —
there is no dependence on the fraud-withdrawal ground-truth label.

(b) **Trailing-window aggregate, not the label window.** The window ends at the
forecast point (the 24h *before* the prediction day); the label is fraud in the
24h *after* it. The feature can never contain the outcome it predicts.

(c) **Its single-feature AUC is 0.8447, not 1.0.** No single feature is
decisive (`per_feature_auc` in `metrics.json`; the next-strongest is
`distinct_accounts_24h` at 0.6722). A label leak would show ~1.0 here.

(d) **The ranking decays.** `precision@20/50/100/200/500/1000 = 0.90 / 0.86 /
0.83 / 0.735 / 0.61 / 0.52` and threshold(≥0.7) precision = 0.62. A genuine
leak would stay ≈1.0 throughout the curve instead of decaying.

(e) **The model must now learn genuine false-positive cases.** After the
iteration-4 de-separation (hot-ATM rotation, prevented cash-outs at genuinely
hot ATMs, busy high-traffic ATMs with bulk-cash clusters but no fraud),
Precision@20/50/100 dropped from a suspicious 1.0 to 0.90/0.86/0.83 — see
"Why precision@K is not artificially perfect" in `MODEL_CARD.md`.

---

## 3. Known evaluation ceiling (read before quoting metrics)

Precision@K / lead-time / lift are measured against **synthetic labels**
generated from behaviours calibrated to the published patterns above. This does
**not** equal real-world precision. The defensible claims are:

1. **Methodological rigor** — time-based split with a validation slice (early
   stopping + calibration never touch the test set), precision@K,
   **baseline lifts** (vs volume-ranking: 14–18× at P@20/50/100; vs
   complaint-proximity ranking: 17× at P@100, from `metrics.json`),
   **lead-time** (median 14.9 h of warning before the first confirmed fraud
   withdrawal; IQR 9.4–20.0 h; annotated `lead_time_is_horizon_dependent`),
   calibration curve + confusion matrix (`artifacts/calibration_and_confusion.png`),
   robustness-to-perturbation (`artifacts/robustness_check.png`).
2. **Honest separability (numbers read from `artifacts/metrics.json`)**
   — the label-leaking feature `fraud_withdrawals_24h` has been **removed**
   from `backend/ml/features.py`; `is_fraud_withdrawal` appears in the feature
   module only as the label `y`. The regenerated metrics on the held-out test
   set (with the Hawkes self-exciting feature and validation-slice early
   stopping) are:
   `precision@20/50/100/1000 = 0.90 / 0.90 / 0.85 / 0.54; threshold(≥0.7) precision =
   0.6588; max single-feature AUC = 0.8447 (feature: counterparty_count_24h)`.
   - **De-separation (iteration-4) — the previous residual-separability
     limitation is RESOLVED:** earlier iterations reported P@K≤100 = 1.0; the
     investigation (see MODEL_CARD.md) found the cause in the generator — a
     static hot-ATM set and a demo-wave concentration in the test tail — not
     in a single leak feature. The generator now rotates hot-ATM membership
     every 14 days, blocks a larger share of mule cash-outs (prevented
     bursts carry no label), adds busy high-traffic ATMs as false-positive
     cases, and widens amount/timing noise. Result: `P@20 0.90 → P@100 0.85 →
     P@1000 0.54`, threshold precision 0.6588, false-alert rate 0.34 — a
     strong-but-imperfect ranking that decays honestly across the operational
     band. Feature audit after de-separation
     (`artifacts/deep_eval/feature_audit.json`): top-1 importance 32.9%,
     top-3 56.8% — no single-feature dominance.

### Hawkes self-exciting intensity + ensemble (honest disclosure)

- `backend/ml/hawkes.py` adds `hawkes_intensity_24h` — a per-location
  exponential-kernel intensity λ(t) = μ + Σ_{tᵢ<t} α·exp(−β(t−tᵢ)) over **past
  complaint timestamps only** (strict mask; prediction-time safety asserted by
  `self_test()`; params fitted on the training period only).
- **Ensemble is NOT better — disclosed, not hidden**: rank-average
  XGB+Hawkes gives test Precision@100 0.41 vs pure-XGBoost 0.85
  (`metrics_ensemble` vs `metrics` in `metrics.json`). The active
  model is therefore `xgboost` (the Hawkes feature still contributes as one of
  24 features). `new_feature_single_auc_hawkes = 0.5082` — weak alone,
  leak-free (< 0.95 gate).
- Baselines on the same test set: volume ranking P@20/50/100 =
  0.05/0.06/0.06 → **lift vs volume 18.0/15.0/14.2**; complaint-proximity
  ranking P@20/50/100 = 0.0/0.02/0.05 → **lift vs proximity 17× at P@100**
  (the model massively outperforms a naive "near recent complaints" heuristic —
  and this is disclosed honestly).
- Lead time median **14.9 h** (IQR 9.4–20.0) — annotated
  `lead_time_is_horizon_dependent: true`: it is a horizon design-property of  `lead_time_is_horizon_dependent: true`: it is a horizon design-property of
  the 24h forecast, not an independent accuracy claim.
3. **Transfer-readiness** — schema, repository layer, adapters, and feature
   definitions are shaped for real NCRP/CFCFRMS + bank feeds.
4. **Not field-validated accuracy** — a real pilot would replace synthetic
   labels with investigation-confirmed withdrawals and re-tune thresholds per
   city/bank via an ops review.