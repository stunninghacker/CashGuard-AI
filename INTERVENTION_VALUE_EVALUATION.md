# INTERVENTION_VALUE_EVALUATION.md — Does acting on CashGuard beat simple alternatives?

Prediction is not the objective; intervention usefulness is. This evaluation
compares three intervention strategies at the SAME daily intervention budget
(K = 5 / 10 / 20 / 50 / 100 ATMs/day) on the identical held-out test period:

- **random** — K ATMs/day chosen uniformly at random
- **volume** — K busiest ATMs/day by withdrawal volume ("busy ATMs are busy")
- **cashguard** — K ATMs/day ranked by the calibrated model

Artifact: `artifacts/deep_eval/intervention_simulation.json`
Run: `python scripts/intervention_simulation.py`
**LABEL: CONTROLLED SYNTHETIC SIMULATION — never a real-world loss claim.**

## Results (10 seeds, mean; 95% CI in artifact)

| Strategy | K | Fraud captured | Loss prevented (% exposure) | False interventions | Efficiency (₹ prevented / intervention) | Time-to-intervention |
|---|---|---|---|---|---|---|
| random | 10 | 0.4% | 0.4% | 508 | ₹3,094 | ~14h |
| volume | 10 | 0.5% | 0.5% | 531 | ₹4,271 | ~15h |
| **cashguard** | **10** | **5.5%** | **5.0%** | **242** | **₹41,418** | 14.8h |
| random | 100 | 3.6% | 3.6% | 5,075 | ₹2,988 | ~15h |
| volume | 100 | 4.7% | 4.6% | 5,094 | ₹3,803 | ~15h |
| **cashguard** | **100** | **20.7%** | **20.0%** | **3,713** | **₹16,531** | 15.4h |

## Reading the table honestly
- **CashGuard captures 11–14× more fraud than volume/random at the same K**
  (K=10: 5.5% vs 0.5%/0.4%) with **half the false interventions** (242 vs
  ~520) and **~10× the efficiency per intervention** (₹41k vs ₹3–4k).
- The gap narrows at large K (top-100 of 900 ATMs covers a big share of the
  network either way) — the model's edge is at *small, surgical* budgets,
  which is the operational regime that matters (limited officers, limited
  branch actions).
- Time-to-intervention is similar across strategies (~14–15h) because it is
  dominated by the 24h forecast window, not the ranking method.
- Efficiency declines with K for all strategies — the intervention-priority
  score is the tool that picks the operating point on this curve.

## What this does NOT claim
- No real loss was prevented; nothing here is real-world savings.
- Real-world capture depends on data latency, bank cooperation, human action,
  and the pilot (REAL_DATA_VALIDATION_PROTOCOL.md).
- The baseline strategies are deliberately naive; a real ops team would
  combine signals — which is exactly what the priority score does, now with
  measured evidence for the combination's value.