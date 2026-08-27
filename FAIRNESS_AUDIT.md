# FAIRNESS_AUDIT.md — Group-Fairness & Feedback-Loop Audit (Phase 8)

Artifacts: `artifacts/deep_eval/fairness_groups.json`,
`artifacts/fairness_report.json` (concentration monitor).

## Design principles (enforced, not claimed)
- **Zero demographic features** anywhere — risk is transaction behaviour +
  complaint linkage + transaction geography only.
- **No historical police intervention is a predictor** — interventions are
  human decisions made after the forecast; the model never learns from them.
- Advisory-only, human-review gate, mandatory reason for dismiss/escalate,
  every decision ledger-audited.

## Held-out group metrics (synthetic jurisdictions)

| Group | Positive rate | Alert rate (≥0.7) | False-positive rate | Precision | Recall |
|---|---|---|---|---|---|
| District-3 | 0.085 | 0.018 | 0.0041 | 0.771 | 0.163 |
| Eastvale | 0.071 | 0.010 | 0.0021 | 0.790 | 0.109 |
| Greenfield District | 0.071 | 0.014 | 0.0044 | 0.674 | 0.130 |
| Metro-West | 0.075 | 0.015 | 0.0034 | 0.768 | 0.149 |
| Northsagar | 0.128 | 0.040 | 0.0041 | 0.897 | 0.282 |

## Findings (honest)
1. **False-positive rate is flat across groups (0.002–0.004)** — the strongest
   fairness signal: no group is over-flagged relative to another.
2. **Alert rates track positive rates** (Northsagar has the synthetic final
   wave → 0.128 positive rate → higher alert rate). This is scenario-driven,
   not bias-driven; the concentration monitor (`fairness_report.json`, Gini)
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