# FAIRNESS_AUDIT.md — Group-Fairness & Feedback-Loop Audit

Artifacts: `artifacts/deep_eval/fairness_groups.json` (reproducible via
`python scripts/fairness_audit.py`),
`artifacts/fairness_report.json` (concentration monitor).

## Design principles (enforced, not claimed)
- **Zero demographic features** anywhere — risk is transaction behaviour +
  complaint linkage + transaction geography only.
- **No historical police intervention is a predictor** — interventions are
  human decisions made after the forecast; the model never learns from them.
- Advisory-only, human-review gate, mandatory reason for dismiss/escalate,
  every decision ledger-audited.

## Held-out group metrics (synthetic jurisdictions, iteration-4 model)

| Group | Positive rate | Alert rate (≥0.7) | False-positive rate | Precision | Recall |
|---|---|---|---|---|---|
| all | 0.062 | 0.010 | 0.004 | 0.624 | 0.103 |
| District-3 | 0.057 | 0.010 | 0.005 | 0.516 | 0.087 |
| Eastvale | 0.057 | 0.008 | 0.003 | 0.632 | 0.087 |
| Greenfield District | 0.057 | 0.009 | 0.003 | 0.635 | 0.098 |
| Metro-West | 0.060 | 0.009 | 0.004 | 0.598 | 0.089 |
| Northsagar | 0.079 | 0.016 | 0.005 | 0.692 | 0.140 |
| complaint_area low | 0.058 | 0.008 | 0.003 | 0.614 | 0.088 |
| complaint_area mid | 0.057 | 0.010 | 0.005 | 0.516 | 0.087 |
| complaint_area high | 0.068 | 0.012 | 0.004 | 0.672 | 0.123 |
| atm_volume low | 0.056 | 0.005 | 0.002 | 0.709 | 0.067 |
| atm_volume mid | 0.069 | 0.012 | 0.004 | 0.680 | 0.117 |
| atm_volume high | 0.060 | 0.013 | 0.006 | 0.539 | 0.121 |
| atm_age low | 0.058 | 0.010 | 0.004 | 0.586 | 0.106 |
| atm_age mid | 0.062 | 0.010 | 0.004 | 0.589 | 0.098 |
| atm_age high | 0.066 | 0.010 | 0.003 | 0.700 | 0.105 |

## Findings (honest)
1. **False-positive rate is flat across groups (0.0015–0.0062)** — the strongest
   fairness signal: no group is over-flagged relative to another.
2. **Alert rates track positive rates** (Northsagar carries the synthetic final
   wave → higher alert rate and recall). This is scenario-driven, not
   bias-driven; the concentration monitor (`fairness_report.json`, Gini)
   exists precisely to watch this over time in ops review.
3. **Recall is highest where fraud concentrates** — the model is
   intervention-concentrating by design; the safeguards below bound that.

## Safeguards (in code + process)
- Minimum-evidence requirement: alerts below evidence strength 3/5 are HOLD ACTION.
- Uncertainty threshold: low-confidence forecasts never generate aggressive recommendations.
- Human review gate + mandatory reason for dismiss/escalate.
- No automatic punitive action — ever.
- Audit trail: every decision on the tamper-evident chain.
- Repeated-targeting monitor: per-district alert share + Gini tracked in
  `fairness_report.json` for ops review; a district persistently dominating
  triggers review, not automation.

## Active fairness constraint — per-jurisdiction proportional alert cap (Item 5)
- Beyond *measuring* group balance, Item 5 adds an **active scheduling
  constraint**: each state's actionable (dispatch/action) alert budget is sized
  proportional to its share of the national ATM population, so no single
  jurisdiction can monopolize the dispatch/action queue even if its intel
  volume is high.
- **Intelligence is never lost**: over-budget high-risk alerts are still created
  and recorded, but **demoted to monitor** (review-only) tier — the alert is on
  the tamper-evident ledger with a `FAIRNESS-CAPPED` reason, it just does not
  consume dispatch/action attention above that jurisdiction's fair share.
- **Real escalations are never suppressed**: dispatch-tier alerts (severe,
  evidence-backed) override the cap (`allow_override`), so the constraint cannot
  cause a genuine incident to be missed — it only rebalances *pressure*.
- Implemented in `backend/services.py` `FairnessCap`, gated by
  `FAIRNESS_ALERT_CAP` (default ON), sized from live ATM population by state.
  Config-flag means it can be A/B-tested or disabled without a code change.
- This is a **scheduling/fairness constraint, not a model change** — it does not
  alter predicted risk scores or the review-before-action rule; it only
  distributes the *actionable* alert budget proportionally across jurisdictions.
  Tested by `scripts/test_fairness_cap.py` (5/5: proportional sizing, demotion,
  override, under-budget keep, disabled-inert).
- Honest framing: this controls **alert volume fairness**, which is the lever we
  can actually enforce. It does not (and is not claimed to) change the
  *underlying* per-group false-positive rates already documented above.

## Feedback-loop audit
- The model does NOT consume its own interventions or outcomes as features
  (closed-loop outcome monitoring is separate, for calibration/drift only).
- No retraining on small samples; retraining is explicit and versioned.
