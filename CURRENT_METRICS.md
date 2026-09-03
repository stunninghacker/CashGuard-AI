# CURRENT METRICS — CashGuard AI (SIH26184)

> **This is the SINGLE SOURCE OF TRUTH for all CURRENT model metrics.**
> Machine-readable form: [`artifacts/current_metrics.json`](artifacts/current_metrics.json).
> Every current-facing document in this repository must report metrics derivable from this
> file. Any other number is either **SUPERSEDED** (pre-leakage / historical) or a
> controlled synthetic-evaluation detail, and must be labelled as such.

**Evaluation kind:** CONTROLLED SYNTHETIC EVALUATION — **no real-world field performance is
claimed.** All labels are synthetic (see `REAL_DATA_GAP.md`, `LABEL_PROVENANCE_FINAL.md`).
No real NCRP / CFCFRMS / NPCI data was used or claimed.

---

## 1. Leakage fix (why the old 0.92x is gone — and permanently)

The previously headline ROC-AUC of **~0.927** was **invalid** because of a same-day
label-leakage bug in feature engineering (`backend/ml/features.py`, `_shift_day_past`).
It has been fixed. The honest, leak-free headline is:

| Metric | CURRENT value |
|---|---|
| **ROC-AUC** | **0.6273** |
| Precision@20 | 0.65 |
| Precision@50 | 0.64 |
| Precision@100 | 0.61 |
| Precision@200 | 0.57 |
| Precision@500 | 0.372 |
| Precision@1000 | 0.261 |
| Recall@20 / @50 / @100 | 0.0044 / 0.0107 / 0.0205 |
| Accuracy | 0.9391 |
| Positive share (test) | 0.0522 |
| Lead time median (h) | 15.9 (p25 10.6, p75 19.7) |

*Source: `artifacts/metrics.json`.*

**The 0.92x figures are SUPERSEDED and MUST NOT be restored or reported as current.**
The leakage history is preserved for honesty but is never presented as valid
(see §4 and the repo-wide `METRICS_AUDIT.md`).

---

## 1b. Issue-1 model upgrade (honest, same 60-day controlled split; 2026-08-31)

**Objective was `AUC ≥ 0.82`. Honest result: NOT reachable without label leakage.**
We improved the leak-free baseline meaningfully, but 0.82 is out of reach on the
detuned synthetic world (`synthetic_data.py` is explicitly detuned so volume/mule
features do **not** trivially equal fraud; the 0.92x was only possible via the
same-day label-leak — see §1).

**Apples-to-apples controlled comparison — identical chronological 60-day split,
held-out test (n=16200, positive share ~5.1%):**

| Configuration | Test ROC-AUC | Note |
|---|---|---|
| Baseline (24 features) | **0.6548** | pre-Issue-1 |
| + 12 architectural features | 0.6657 | surge velocity, decay, latency, etc. |
| + amount behavioural (rolling) | 0.6717 | mean/max/round/large/heavy |
| **+ fraud recency-decay ← FINAL** | **0.6801** | `fraud_decay_7d` (best single lever) |
| Stacked XGB+LGB+SMOTE-Tomek | 0.6212 | **rejected** (worse than plain XGB) |
| 6-hour-window model | 0.6463 | no gain over daily |

- **Final active model: plain XGBoost, 44 features**, `roc_auc = 0.6801`
  (seed-42 point estimate; seed spread 0.664–0.680). Precision@20 = 0.80,
  P@50 = 0.62, P@100 = 0.61.
- **Best new lever:** `fraud_decay_7d` (exponentially decayed past-fraud-withdrawal
  count at the ATM, ~2-day half-life) — single-variable AUC **0.615**, directly
  models the generator's hot-ATM rotation.
- **Verified dead-ends (do NOT re-chase):** per-ATM spatial complaint proximity
  (~0.50 AUC — generator does not spatially co-locate complaints & fraud ATMs);
  6h windows; stacking/SMOTE.
- **Leak-safety re-verified:** every new feature is trailing-window only and
  `_shift_day_past`-shifted; permutation label-shuffle would still give AUC ≈ 0.5.
- Artifact: `artifacts/model.joblib` (active_model=xgboost, stack_available=True
  but deprioritised), metrics in `artifacts/metrics.json` (`metrics_stacked_smote`,
  `auc_before_xgb`, `auc_after_stack_raw`, `val_auc_*`).

**Honest bottom line:** 0.82 is the leakage-era (invalid) number; the genuine
ceiling for this detuned synthetic task is **~0.68**. Higher AUC here would require
real field data (see `REAL_DATA_GAP.md`) or would be dishonest.

---

## 2. Generalization (leak-free)

| Split | ROC-AUC | PR-AUC | P@100 | P@1000 | ECE | Note |
|---|---|---|---|---|---|---|
| time_forward (production) | **0.6263** | 0.1384 | 0.66 | 0.281 | 0.012 | chronological |
| cold_atm | **0.5963** | 0.1228 | 0.35 | 0.113 | 0.009 | 180 ATMs unseen in training |
| cold_city | **0.6228** | 0.1831 | 0.55 | 0.189 | 0.0355 | city Northsagar held out |
| cold_district | **0.6228** | 0.1831 | 0.55 | — | 0.0355 | == cold_city (single-district world) |
| new_hotspot | **0.5847** | 0.1052 | 0.27 | 0.094 | 0.0042 | top-20% volume ATMs held out |

*Source: `artifacts/deep_eval/generalization_splits.json`.*

**Honest reading:** time-forward and random are comparable (no memorization of the test
window); cold-ATM degrades modestly; **cold-city/district and new-hotspot generalize worst
(~0.58–0.62 AUC)**. This is the honest generalization ceiling on this synthetic world and
is reported, not omitted. Novel-hotspot discovery is unreliable — the system uses
**LOW-CONFIDENCE / HOLD** rather than over-claiming.

---

## 3. Baseline superiority & intervention value

### 3a. Baseline war (leak-free, identical held-out split)

CashGuard vs simple baselines — **precision@100 lift** (only honest rows; the 0.92x
cashguard rows in `baseline_war.json` are SUPERSEDED):

| CashGuard vs | P@100 lift |
|---|---|
| Complaint volume | 86.0× |
| Withdrawal volume | 15.25× |
| Random | 12.29× |
| Proximity | 6.778× |
| Historical hotspot | 3.44× |

*Source: `artifacts/metrics.json`, `artifacts/deep_eval/baseline_war.json`.*

### 3b. Intervention budget war — expected value per intervention (K=5..100)

Identical held-out synthetic test period; top-K per day per strategy; **10 seeds**;
5 strategies **including complaint-proximity** (added). Recomputed authoritatively
2026-08-30 → supersedes the earlier (stale) war table.
**The primary operational metric is expected value per intervention, NOT AUC.**

| K | CashGuard capture | volume | random | historical | complaint-prox | lift vs volume |
|---|---|---|---|---|---|---|
| 5 | 0.024 | 0.005 | 0.002 | 0.013 | 0.004 | 4.8× |
| 10 | **0.033** | 0.008 | 0.004 | 0.020 | 0.006 | **4.12×** |
| 20 | 0.042 | 0.014 | 0.007 | 0.031 | 0.011 | 3.0× |
| 50 | 0.057 | 0.032 | 0.019 | 0.074 | 0.023 | 1.8× |
| 100 | 0.078 | 0.057 | 0.038 | 0.121 | 0.042 | 1.37× |

**Efficiency (₹ exposure prevented per intervention) at K=10:**
CashGuard **₹27,139** vs volume ₹7,223 vs random ₹3,380 vs historical ₹19,056 vs
complaint-proximity ₹4,890.

**CashGuard loss prevented (%) at K:** 2.4% (K5) → 3.3% (K10) → 4.3% (K20) → 5.9% (K50)
→ 8.1% (K100).

**Lift at K=10 (capture rate):** CashGuard **5.5× complaint-proximity**, 4.12× volume,
8.25× random, 1.65× historical. Even the complaint-proximity dispatcher baseline (ATMs
near recent complaints) underperforms the model — the model adds value beyond naive
proximity dispatch.

*Source: `artifacts/final_intervention_war.json` (authoritative; verified 1:1 against a
rerun of `scripts/intervention_simulation.py` for the shared strategies).*
**Disclaimer:** totals are illustrative synthetic ₹ amounts; no real-world per-ATM loss
benchmark exists. The honest value frame is *concentrating finite reviewer attention on the
30–60 highest-risk ATM/cycles at 67–75% precision* rather than a national-recall claim.

### 3c. Dispatch operating point (threshold 0.70 — DEFAULT)

- 32 alerts, **precision 0.75, recall 0.0081**, false-alert rate 0.25.
- This is the **low-recall reality** — disclosed by design: ranked-precision utility at
  limited intervention capacity, not national recall (base rate ~5%).
- Full PRF table: `artifacts/metrics.json`.

---

## 4. SUPERSEDED history (preserved for honesty — NOT current)

The following carry the **pre-leakage 0.92x** figures. They are intentionally NOT deleted
(leakage history is kept) but must be read as **historical / invalid as current
performance**:

`artifacts/deep_eval/baseline_war.json` (cashguard/xgb rows), `artifacts/deep_eval/seed_stability.json`
(0.9258–0.9264 model / 0.9178–0.9266 generator), `artifacts/deep_evaluation.json`,
plus 0.92x passages in `MODEL_CARD.md`, `README.md`, `FINAL_MODEL_BENCHMARK.md`,
`JUDGE_BRIEF.md`, `PITCH.md`, `ONE_SLIDE_EXECUTIVE_SUMMARY.md`, `LIMITATIONS.md`,
`SIH26184_DELIVERABLE_MATRIX.md`, and the raw JSON eval artifacts.

**Marker:** `SUPERSEDED — PRE-LEAKAGE / HISTORICAL — NOT CURRENT PERFORMANCE`.

The complete per-file disposition is in **`docs/audits/METRICS_AUDIT.md`**.

---

## 5. Honest limitations (stay visible)

1. **Low absolute recall** at dispatch thresholds (~0.8–2% recall at 0.65–0.75 precision).
   This is ranked-precision utility, not national recall.
2. **Synthetic-only dataset** — field accuracy is never claimed; real
   NCRP/CFCFRMS/NPCI data is unavailable (external blocker, see
   `FINAL_10_10_BLOCKERS.md`).
3. **Cold-city / cold-district / new-hotspot generalize worst** — reported; HOLD is used on
   low confidence.
4. **Single-state / single-district demo world** — true multi-jurisdiction requires
   genuinely independent jurisdictions.
5. **National-scale production not proven** — SQLite/demo-scale only; PostgreSQL/Kafka/Redis
   are adapters, not load-validated.

---

*Generated 2026-08-30. If a number in this repo disagrees, the disagreement is a bug —
report it and reconcile against `artifacts/current_metrics.json`.*
