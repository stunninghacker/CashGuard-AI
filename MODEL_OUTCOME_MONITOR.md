# MODEL_OUTCOME_MONITOR.md — Closed-Loop Outcome Evaluation & Runtime Drift

## The closed loop (already implemented in code)
```
prediction → human decision (acknowledge/monitor/dismiss/escalate/actioned)
          → outcome (evaluate after the horizon) → stored error → drift signal
```

- **Store**: `alerts` carry `risk_score`, `model_version`, `decision_reason`;
  `AlertOutcome` rows record `predicted_positive`, `actual_positive`,
  `outcome_status` (TRUE_POSITIVE / FALSE_POSITIVE / FALSE_NEGATIVE /
  UNKNOWN) and `evaluated_at` (endpoint `POST /alerts/outcomes/evaluate`,
  UI: Closed-Loop Outcomes panel).
- **Human decision is the middle step** — the loop is impossible without a
  human, by design; no automatic punitive action exists.
- **No feedback into features**: the model never consumes its own
  interventions or outcomes as predictors (feedback-loop audit in
  FAIRNESS_AUDIT.md); retraining is explicit and versioned.

## What the monitor computes
Per evaluation window (default 24h-aligned):
1. Outcome error = ECE of predicted probability vs confirmed outcome
   (the primary drift signal: rising outcome calibration error → drift).
2. FP/FN counts by alert band (HOLD / actionable / critical).
3. Precision/recall vs confirmed outcomes — replaces the synthetic-label
   numbers once outcomes are investigation-confirmed.
4. Alert-to-outcome lead time per ATM and jurisdiction.
5. Model disagreement (A vs B) trend per week (artifact:
   `artifacts/deep_eval/model_disagreement.json`).

## Runtime drift monitors (feature/prediction level)
| Signal | Mechanism | Action when breached |
|---|---|---|
| Feature distribution | PSI per feature vs training window | Confidence reduction + review flag |
| Prediction distribution | Score histogram shift (KS test) | Review flag |
| Geographic distribution | Alert share per jurisdiction (Gini monitor) | Ops review (never auto-action) |
| Confirmed fraud rate | Outcome ECE / fraud-rate shift vs prior window | REDUCED confidence (drift rule from MODEL_DRIFT.md) |
| Model disagreement | |A−B| > 0.20 → downgrade; > 0.35 → HOLD |
| Data freshness | `data_freshness_hours` per source | Stale → HOLD ACTION |

The system never silently continues: every breach reduces confidence, flags
the model, and requires review. This is the same REDUCED-confidence rule the
drift suite (`scripts/drift_eval.py`, 12 worlds) validates statically.

## How performance-over-time is reported
- Static evidence: `artifacts/deep_eval/operational.json` (synthetic),
  `drift.json` (12 worlds), `model_disagreement.json`.
- Runtime: the Closed-Loop Outcomes panel + `POST /alerts/outcomes/evaluate`;
  a rising outcome-ECE over consecutive windows is the trigger for the
  REAL_DATA_VALIDATION_PROTOCOL.md rollback condition.

## Honest limits
- On synthetic data, "outcomes" are generator labels — the loop's *mechanics*
  are exercised live (evaluate → FP/FN/UNKNOWN), but its *meaning* requires
  investigation-confirmed real outcomes (the pilot).
- Thresholds above are defaults; production values are set with ops in the
  pilot (REAL_DATA_VALIDATION_PROTOCOL.md §13).