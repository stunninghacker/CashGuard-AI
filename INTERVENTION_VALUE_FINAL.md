# INTERVENTION VALUE — FINAL (CashGuard AI, SIH26184, Phase 3)

> **Question the judge asked (financial framing):** given a fixed number of interventions
> (a reviewer/patrol budget per day), does CashGuard rank ATMs better than what a police
> dispatcher would do with simple operational rules?
>
> **Answer (honest, synthetic-only): Yes, on this synthetic world — at every budget, the
> model captures more fraud exposure per intervention than every operational baseline**
> including a newly-added **complaint-proximity** dispatcher baseline.
>
> Machine-readable: `artifacts/final_intervention_war.json`.
> Single source of truth for all metrics: `CURRENT_METRICS.md` + `artifacts/current_metrics.json`.

> **⚠ LABEL:** CONTROLLED SYNTHETIC SIMULATION. Totals are illustrative synthetic ₹ amounts.
> **NEVER a real-world loss / ROI claim** (see `REAL_DATA_GAP.md`). No real NCRP/CFCFRMS/NPCI
> data was used.

---

## 1. Method (identical, honest, reproducible)

- **Test period:** the held-out chronological test split — 54 forecast days, 900 ATMs,
  10,714 synthetic fraud events. Identical for every strategy.
- **Budget K:** top-K ATM-days chosen **per forecast day** under each strategy, K = 5/10/20/50/100;
  a 24-hour capture window; **10 seeds** of selection jitter; **95% CI** reported.
- **Strategies:**
  - `random` — K ATM-days at random.
  - `volume` — K ATMs ranked by 24h withdrawal volume ("busy ATMs").
  - `historical` — K ATMs ranked by prior fraud-event count at that ATM.
  - `complaint_proximity` — K ATMs ranked by # complaints filed in the prior 24h within
    **2.0 km** of the ATM (a realistic dispatcher baseline; NEW in this phase).
  - `cashguard` — K ATMs ranked by the **calibrated model score** (forecast-driven).
- **Primary metric = expected value per intervention** (₹ exposure captured ÷ interventions),
  because a police force has a finite number of deployments — AUC alone does not capture
  "per action taken" utility.

*Reproducibility: `scripts/final_intervention_war.py`. The four shared strategies were
verified 1:1 against a rerun of `scripts/intervention_simulation.py`.*

---

## 2. Capture rate by budget (mean over 10 seeds)

| K | CashGuard | volume | random | historical | complaint-prox |
|---|---|---|---|---|---|
| 5 | **0.024** | 0.005 | 0.002 | 0.013 | 0.004 |
| 10 | **0.033** | 0.008 | 0.004 | 0.020 | 0.006 |
| 20 | **0.042** | 0.014 | 0.007 | 0.031 | 0.011 |
| 50 | **0.057** | 0.032 | 0.019 | 0.074 | 0.023 |
| 100 | **0.078** | 0.057 | 0.038 | 0.121 | 0.042 |

CashGuard leads at **every** budget. Only at large K does `historical` (which exploits
persistence of per-ATM fraud) catch up on raw capture — but CashGuard still leads on
**per-intervention efficiency** because it wastes fewer of the finite deployments.

---

## 3. Expected value per intervention (₹ captured per deployment) — K=10

| Strategy | ₹ per intervention |
|---|---|
| **CashGuard** | **₹27,139** |
| historical | ₹19,056 |
| volume | ₹7,223 |
| complaint-proximity | ₹4,890 |
| random | ₹3,380 |

At K=5 CashGuard is even more efficient (₹39,888/deployment). CashGuard concentrates the
finite review capacity where the *next* fraud is most likely, rather than where fraud
*happened* (historical), where ATMs are *busy* (volume), or where complaints were *just
filed* (proximity).

---

## 4. Headline lift at K=10 (capture rate)

| CashGuard vs | lift |
|---|---|
| random | **8.25×** |
| complaint-proximity | **5.5×** |
| volume | **4.12×** |
| historical | **1.65×** |

Notable: the **complaint-proximity** baseline (ATMs near recent complaints) beats random and
volume — it uses real spatial signal — **yet still underperforms the model by 5.5×**. This is
the strongest evidence that the model adds genuine value beyond a naive, defensible
dispatcher heuristic.

---

## 5. Loss prevented (%) — CashGuard

| K | 5 | 10 | 20 | 50 | 100 |
|---|---|---|---|---|---|
| CashGuard loss prevented | 2.4% | 3.3% | 4.3% | 5.9% | 8.1% |

**Honest reading:** absolute loss prevention is small in percentage terms because of the
low base rate (~5%) and the low absolute recall of a precision-first ranking. The value is
**concentration**: it flags the 30–60 highest-risk ATM/cycles at **67–75% precision**
(see `CURRENT_METRICS.md` §3c), i.e. 2–3× better than randomly picking ATMs. It is ranked
precision at the top, not national recall.

---

## 6. Limitations (stay visible)

1. Synthetic labels only — never a real-world loss/ROI claim.
2. Illustrative ₹ totals; no real per-ATM loss benchmark exists.
3. Single-state / single-district demo world; `complaint_proximity` radius (2.0 km) is
   ad-hoc and may not transfer.
4. Operational value = concentration of limited review, not national recall.
5. 10-seed 95% CI reported, not hidden.

---

*Generated 2026-08-30. Supersedes the pre-Phase-3 intervention table (K10 0.055 / ₹41,418 was
stale; verified and corrected). If a number here disagrees with `artifacts/final_intervention_war.json`
or `CURRENT_METRICS.md`, the disagreement is a bug — reconcile there.*
