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

## Results (regenerated on the de-separated iteration-4 generator)

| Strategy | Fraud events captured | Loss prevented (% of exposure) | 95% CI | False interventions | Missed events | Efficiency (₹ / intervention) | Time-to-intervention (median) |
|---|---|---|---|---|---|---|---|
| Baseline (do nothing) | 0% | 0% | — | 0 | all | 0 | — |
| Top-5 / day | 3.7% | 3.2% | [3.1, 3.3] | 92 | 10280 | ₹53,273 | 13.9 h |
| **Top-10 / day** | 5.5% | 5.0% | [4.9, 5.1] | 242 | 10087 | ₹41,418 | 14.8 h |
| Top-20 / day | 8.1% | 7.4% | [7.4, 7.4] | 580 | 9807 | ₹30,530 | 15.4 h |

(Exact values in the artifact; exposure total = simulated test-period fraud
amount ₹455M.)

## Honest interpretation
- Under the simulated assumptions, **top-K intervention captures ~3.7–8.1% of
  fraud exposure with ~5–20 daily actions** — better than doing nothing, and
  the gain is bounded by how concentrated fraud is. Note the capture rates are
  LOWER than the previous (pre-de-separation) simulation: the iteration-4
  generator removed the artificially clean separability, so the simulation now
  measures the model's honest edge. The intervention priority score is the
  lever that trades K against efficiency.
- Efficiency declines with K (more interventions per rupee prevented) — this is
  the trade-off the Intervention Priority score is designed to optimize.
- **What this does NOT claim**: no real loss was prevented; real-world capture
  depends on complaint/withdrawal data latency, bank cooperation, and human
  action — all pilot questions.

## Alert fatigue mitigation

The alert cycle deduplicates repeat alerts for the same ATM: if an ATM
already has an open (unacknowledged or recently-actioned) alert, no new alert
fires for that ATM within the cooldown window (`ALERT_COOLDOWN_HOURS`, default
6 hours) — **unless** the risk score has risen meaningfully since the last
alert (delta > `ALERT_DEDUP_RISK_DELTA`, default 0.1), so a genuine escalation
still gets through. This is a scheduling rule, not a model change. It must be
read alongside the honest headline number: the threshold-0.7 false-alert rate
is **38%** and this system does not hide that — the dedup reduces noise, but
the system is decision support, not an autonomous trigger. Every alert still
requires human review before any action, which is exactly what the evidence
panel is for: it is designed to **prioritize investigator attention, not to
replace it**.

## Why this matters for SIH
It converts "the model ranks well" into the operational question the problem
statement cares about: **"if you act on the top-K, what share of the fraud
exposure do you touch, and what does it cost in interventions?"** — answered
with a reproducible, labelled simulation rather than a promise.