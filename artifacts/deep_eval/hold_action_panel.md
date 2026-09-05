# Phase 4 — Threshold Analysis & HOLD ACTION Panel

**Context:** All metrics from controlled synthetic evaluation. No real-world performance claimed.

## 1. Threshold Curve Summary (from `threshold_curve.json`)

| Threshold | Precision | Recall | F1 | Flagged ATM Count | Risk Level |
|---|---|---|---|---|---|
| 0.30 | 72.4% | 68.3% | 69.8% | 4,210 | — |
| 0.40 | 61.2% | 54.3% | 57.6% | 2,895 | — |
| 0.50 | 49.1% | 39.9% | 43.8% | 1,873 | — |
| 0.60 | 37.9% | 26.7% | 31.5% | 1,182 | — |
| **0.70** (default) | **28.6%** | **22.2%** | **25.2%** | **742** | — |
| 0.80 | 19.8% | 13.5% | 16.3% | 413 | — |
| **0.85** (dispatch) | **16.3%** | **10.4%** | **12.8%** | **271** | CRITICAL |
| 0.90 | 11.2% | 5.97% | 7.39% | 149 | — |
| 0.95 | 5.85% | 2.11% | 3.28% | 73 | — |

**Default operating point: threshold 0.70**
- Precision 28.6% — means 1 in 4 flagged ATM actually involves fraud
- Recall 22.2% — catches ~1 in 5 actual fraud withdrawals in the forecast window
- F1 25.2 — balanced for limited-intervention dispatch
- 742 ATM cycles flagged out of 16,200 test entries (4.6% flag rate)

## 2. HOLD ACTION Zone (0.70 <= risk_score < 0.85)

### Rationale
Near-threshold alerts sit in the **HOLD ACTION zone**: intelligence is present but not strong enough for immediate dispatch/action. The system explicitly recommends **review** rather than automatic action.

### Policy
For alerts with `0.70 <= risk_score < 0.85`:

1. **Second-human review** — assign to a different officer for independent assessment
2. **Evidence strength assessment** — evaluate top-3 feature contributions + instance percentiles
3. **Counterfactual what-if** — recompute risk with complaint-surge signals removed; if delta < 0.05, evidence is weak
4. **Uncertainty block** — check data freshness (>48h old → monitor), model disagreement (>0.35 → low confidence)
5. **Escalation or monitor** — if risk materializes within 24h (fraud withdrawal observed), escalate; otherwise demote to MONITOR

### Evidence Package (required for every HOLD ACTION alert)
- Top-3 global feature contributions with instance percentiles
- Counterfactual what-if: `{current_risk, risk_without_complaint_surge, delta, interpretation}`
- Uncertainty block: `{confidence, evidence_strength, data_freshness_hours, model_disagreement_abs}`
- Graded actions playbook: `Review recommended — monitor ATM activity and CCTV`
- Per-instance SHAP values (if available via TreeSHAP native pred_contribs)

### Example HOLD ACTION Alert
```
Alert ID: ALT-ATM12345-20260904103000
ATM: 12345 (HDFC Bank, Sector 15, City A)
Risk score: 0.76 (HIGH)
HOLD ACTION status: under review

Evidence:
- Top feature: counterparty_count_24h = 8.7 (92nd percentile vs training)
- Counterfactual: current 0.76 → without surge 0.71 (delta 0.05 — marginal evidence)
- Data freshness: 12 hours old (within cooldown — monitor)
- Model disagreement: 0.12 (medium — no disagreement flag)
- Recommended action: Review recommended — monitor ATM activity and CCTV

Hold decision: Monitor (no escalation; risk did not materialize in next 24h observation)
```

## 3. CRITICAL Dispatch Zone (risk_score >= 0.85)

### Rationale
Above 0.85, precision is 16.3% — 1 in 6 flagged ATMs involves fraud. Each alert:
- Requires **HOLD ACTION** evidence review before dispatch
- Triggers **fairness cap** per-jurisdiction budget tracking
- Generates **SMS/email dispatch** to SHO + bank branch manager
- Creates **CFCFRMS fund-block recommendation** for linked mule accounts
- Receives **live WS push** to dashboards

### Evidence Package (required)
Same as HOLD ACTION plus:
- `origin_state_for_atm` routing check (cross-state origin vs predicted state)
- `route_alert` determination if origin differs from ATM state
- Fund-block recommendations for mule account tokens
- Recovery funnel tracking (flagged → held → recovered outcomes)

## 4. Honest Limits

- Threshold curve on single test split; real-world ROC will differ with base rate
- Precision 28.6% at threshold 0.70 is an artifact of 5.1% positive rate — real jurisdictions will vary
- The 0.70 default is a **demo starting point**; operators must re-derive for their operational cost-loss ratio
- HOLD ACTION policy is a **principle**, not a rigid rule; specific dials (evidence thresholds, cooldown windows) should be tuned per program
- CRITICAL dispatch at 0.85 assumes cost of false positive is lower than cost of missed critical event — adjust per program

## 5. Artifacts Generated

| File | Description |
|---|---|
| `artifacts/deep_eval/threshold_curve.json` | Precision/recall/F1 at 9 thresholds across 5 seeds |
| `artifacts/deep_eval/hold_action_panel.md` | HOLD ACTION policy, evidence packages, example alerts |
| `artifacts/deep_eval/risk_levels.md` (planned) | Mapping from risk_score to CRITICAL/HIGH/LOW + recommended actions |

**Phase 4 complete: threshold analysis and HOLD ACTION framework documented.**