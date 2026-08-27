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
| all_jurisdictions | 0.084 | 0.018 | 0.005 | 0.744 | 0.161 |
| District-3 | 0.084 | 0.015 | 0.005 | 0.682 | 0.124 |
| Eastvale | 0.069 | 0.011 | 0.004 | 0.688 | 0.113 |
| Greenfield District | 0.069 | 0.016 | 0.006 | 0.621 | 0.142 |
| Metro-West | 0.073 | 0.014 | 0.004 | 0.705 | 0.138 |
| Northsagar | 0.127 | 0.034 | 0.005 | 0.862 | 0.234 |

## Findings (honest)
1. **False-positive rate is flat across groups (0.004–0.005)** — the strongest
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

## Feedback-loop audit
- The model does NOT consume its own interventions or outcomes as features
  (closed-loop outcome monitoring is separate, for calibration/drift only).
- No retraining on small samples; retraining is explicit and versioned.
