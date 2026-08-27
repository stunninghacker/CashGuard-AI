# OPERATIONAL_IMPACT.md — Does acting on forecasts beat doing nothing?

Method and results: `scripts/intervention_simulation.py` →
`artifacts/deep_eval/intervention_simulation.json`.

**LABEL: CONTROLLED SYNTHETIC SIMULATION.** These are simulated outcomes under
the generator's assumptions — NOT real-world loss prevention.

## Method (reproducible, one command)
- Test-period forecast days only (strictly out-of-sample).
- Each day: intervene on the top-K ATMs by calibrated score (K = 5/10/20).
- A fraud event at a covered ATM within 24h of the forecast point counts as
  captured (loss prevented = the withdrawal amount).
- Baseline = no intervention (100% of fraud exposure is a loss).
- 10 seeds (score jitter) → mean and 95% CI.

## Results

| Strategy | Fraud events captured | Loss prevented (% of exposure) | 95% CI | Efficiency (₹ prevented / intervention) | Time-to-intervention (median) |
|---|---|---|---|---|---|
| Baseline (do nothing) | 0% | 0% | — | 0 | — |
| Top-5 / day | 8.6% | 8.5% | [7.7, 9.2] | ~₹/int. | ~14h |
| **Top-10 / day** | 12.4% | **12.3%** | [11.7, 13.0] | ~₹/int. | ~14h |
| Top-20 / day | 15.8% | 15.8% | [15.1, 16.1] | ~₹/int. | ~14h |

(Exact efficiency values are in the artifact; the exposure total is the
simulated test-period fraud amount.)

## Honest interpretation
- Under the simulated assumptions, **top-K intervention captures ~12–16% of
  fraud exposure with ~5–20 daily actions** — better than doing nothing, and
  the gain is bounded by how concentrated fraud is (our synthetic world spreads
  fraud across ~10–15% of ATMs daily; a more concentrated real world would
  change the numbers — hence the pilot).
- Efficiency declines with K (more interventions per rupee prevented) — this is
  the trade-off the Intervention Priority score is designed to optimize.
- **What this does NOT claim**: no real loss was prevented; real-world capture
  depends on complaint/withdrawal data latency, bank cooperation, and human
  action — all pilot questions.

## Why this matters for SIH
It converts "the model ranks well" into the operational question the problem
statement cares about: **"if you act on the top-K, what share of the fraud
exposure do you touch, and what does it cost in interventions?"** — answered
with a reproducible, labelled simulation rather than a promise.