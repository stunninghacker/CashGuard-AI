# Phase 9 — Outcome Monitoring & Closed-Loop Learning

**Phase 9** from the SIH specification — evaluates predicted vs actual outcomes for aged alerts,
writes `AlertOutcome` records, and provides a model-monitoring summary. **Never auto-retrains**.

## 9.1 Evaluating Pending Outcomes

### 9.1.1 `evaluate_pending_outcomes(db)`

One monitoring cycle that:

1. **Identifies alerts** created >24 hours ago with no outcome yet recorded
2. **Checks actual fraud outcomes** in the 24h window after alert creation
3. **Writes `AlertOutcome` records** with prediction error, FP/FN flags
4. **Returns count** of evaluated alerts

```python
def evaluate_pending_outcomes(db: Session) -> int:
    cutoff = datetime.utcnow() - timedelta(hours=24)
    alerts = repo.list_alerts(db, limit=500)
    evaluated = 0
    
    for a in alerts:
        # Only evaluate alerts older than 24h cutoff
        if a.created_at > cutoff:
            continue
        
        # Skip if outcome already recorded
        if repo.get_alert_outcome(db, a.alert_id) is not None:
            continue
        
        # Define 24h outcome window
        window = [a.created_at, a.created_at + timedelta(hours=24)]
        
        # Check actual withdrawals in the outcome window
        wds = repo.recent_withdrawals(db, atm_id=a.atm_id, since=window[0])
        fraud_now = [w for w in wds if w.timestamp <= window[1] and w.is_fraud_withdrawal]
        actual = "yes" if fraud_now else "no"
        
        # Compute prediction error
        pred = a.risk_score
        prediction_error = round(abs((1.0 if actual == "yes" else 0.0) - pred), 4)
        
        # FP/FN flags
        is_false_positive = (actual == "no" and pred >= 0.5)
        is_false_negative = (actual == "yes" and pred < 0.5)
        
        # Write Outcome record
        repo.create_alert_outcome(
            db,
            alert_id=a.alert_id,
            predicted_risk=pred,
            actual_fraud_happened=actual,
            prediction_error=prediction_error,
            is_false_positive=is_false_positive,
            is_false_negative=is_false_negative,
            evaluated_at=datetime.utcnow(),
            model_version=a.model_version or "",
        )
        evaluated += 1
    
    return evaluated
```

### 9.1.2 When to Call This
- **Automated**: via APScheduler at configurable interval (e.g., every 6 hours)
- **Manual**: `python -c "from backend.services import evaluate_pending_outcomes; db=get_session(); print(evaluate_pending_outcomes(db))"`
- **Trigger**: After any alert cycle (`run_alert_cycle`) that creates new alerts

### 9.1.3 Evaluation Honest Limits
- **24h horizon**: Outcomes are only evaluated after a full 24h window; alerts younger than 24h will not yet have outcomes
- **Synthetic labels**: `actual_fraud_happened` is determined against the synthetic withdrawal label from the withdrawal DB, not real-world fraud
- **Small samples**: Early alerts (within first 24h of system start) may have zero outcomes — this is expected, not an error
- **No auto-retraining**: The pipeline explicitly does NOT auto-retrain on whatever sample size is available
- **Base rate dependence**: FP/FN rates are calibrated to the ~5% positive rate; real-world base rates will shift all metrics

## 9.2 Outcome Monitoring Summary

### 9.2.1 `outcome_monitoring(db)`

Produces a monitoring report summarising all evaluated outcomes:

```python
def outcome_monitoring(db: Session) -> dict:
    outcomes = repo.list_alert_outcomes(db, limit=500)
    decided = [o for o in outcomes if o.actual_fraud_happened in ("yes", "no")]
    n = len(decided)
    
    if n == 0:
        return {"evaluated": 0, "note": "No outcomes evaluated yet — alerts must age past the 24h horizon."}
    
    fp = sum(1 for o in decided if o.is_false_positive)
    fn = sum(1 for o in decided if o.is_false_negative)
    tp = sum(1 for o in decided if o.actual_fraud_happened == "yes" and o.predicted_risk >= 0.5)
    tn = sum(1 for o in decided if o.actual_fraud_happened == "no" and o.predicted_risk < 0.5)
    mean_err = sum(o.prediction_error for o in decided) / n
    
    # Calibration drift: ECE over 10 probability bins
    import numpy as np
    ece = 0.0
    for lo, hi in zip(np.linspace(0, 1, 11)[:-1], np.linspace(0, 1, 11)[1:]):
        m = [o for o in decided if lo <= o.predicted_risk < hi]
        if len(m) >= 2:
            conf = sum(o.predicted_risk for o in m) / len(m)
            obs = sum(1 for o in m if o.actual_fraud_happened == "yes") / len(m)
            ece += (len(m) / n) * abs(conf - obs)
    
    return {
        "evaluated": n,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "mean_abs_error": round(mean_err, 4),
        "outcome_ece_10_bins": round(float(ece), 4),
        "note": "Outcomes evaluated against synthetic withdrawal label (CONTROLLED SYNTHETIC EVALUATION). No auto-retraining on small samples.",
    }
```

### 9.2.3 Monitoring Output Interpretation

| Metric | Good Range | Warning Range | Concern Range |
|---|---|---|---|
| `true_positives` | > 15% of evaluated | 5-15% | < 5% (many missed frauds) |
| `false_positives` | < 30% of flagged | 30-50% | > 50% (too many false alarms) |
| `false_negatives` | < 10% of actual frauds | 10-20% | > 20% (system missing frauds) |
| `mean_abs_error` | < 0.15 | 0.15-0.25 | > 0.25 (poor calibration) |
| `outcome_ece_10_bins` | < 0.10 | 0.10-0.20 | > 0.20 (significant calibration drift) |

**Note**: All ranges are indicative for the synthetic evaluation context; real-world thresholds will differ.

### 9.2.4 Monitoring Report Example
```json
{
  "evaluated": 47,
  "true_positives": 8,
  "false_positives": 12,
  "true_negatives": 21,
  "false_negatives": 6,
  "mean_abs_error": 0.11,
  "outcome_ece_10_bins": 0.04,
  "note": "Outcomes evaluated against synthetic withdrawal label (CONTROLLED SYNTHETIC EVALUATION). No auto-retraining on small samples."
}
```

This indicates:
- 47 alerts evaluated with full 24h outcome windows
- 8 correctly flagged fraud events (TP)
- 12 flagged events where no fraud occurred (FP)
- 21 correctly cleared events (TN)
- 6 missed fraud events (FN)
- Mean absolute error 0.11 — moderate calibration error
- ECE 0.04 — good calibration across 10 probability bins

## 9.3 Closed-Loop Learning — What Happens (and What Doesn't)

### 9.3.1 What Happens
- `AlertOutcome` records are written to the DB with full audit trail
- `prediction_error` = |predicted_risk - actual_outcome| (range 0 to 1)
- `is_false_positive` / `is_false_negative` flags for downstream analysis
- `outcome_monitoring()` report is generated and can be tracked over time
- Model version is captured for trend analysis (`a.model_version` or `_model_version()`)
- No changes to the model or its parameters — this is **monitoring only**, not training

### 9.3.2 What Does NOT Happen (Explicitly)
- ❌ No auto-retraining of model weights
- ❌ No parameter updates to XGBoost/Platt calibrator
- ❌ No feature additions or removals based on single-cycle outcomes
- ❌ No threshold re-calibration based on one monitoring run
- ❌ No alert suppression based solely on monitoring output

### 9.3.3 Human-in-the-Loop Decisions
If monitoring output reveals concerning patterns, a human operator should:

1. **Review the monitoring report** (ideally over a rolling weekly window, not single run)
2. **Investigate specific alert patterns** (e.g., persistent FP/FN for certain ATM clusters)
3. **Decide on model retraining** — submit a formal model-update request; don't auto-retrain
4. **Consider threshold adjustment** — if precision/recall mix is wrong for operational needs
5. **Add/remove features** — follow the same feature-engineering review process as Phase 1
6. **Update calibration** — re-fit Platt calibrator on a larger validation window if drift is detected

## 9.4 Rolling Monitoring Protocol (Recommended)

| Frequency | Action |
|---|---|
| **After each alert cycle** | Call `evaluate_pending_outcomes()` — evaluate alerts that are now >24h old |
| **Daily** | Call `outcome_monitoring()` — produce summary report; track trends |
| **Weekly** | Review FP/FN patterns by ATM cluster, day-of-week, risk-level; decide if model retraining is warranted |
| **Monthly** | Comprehensive review: ECE trend, FP/FN rate trends, base rate shifts; formal decision on model update or feature engineering |

## 9.5 Honest Limits (Phase 9)

- **Synthetic labels only**: Outcomes are against the synthetic withdrawal label; real-world performance validation requires prospective study
- **24h minimum lag**: No outcomes can be evaluated until alerts are at least 24 hours old
- **Sample size dependence**: FP/FN/ECE metrics converge slowly; weekly reports may show volatile numbers
- **Base rate sensitivity**: All rates (TP, FP, FN) depend on the 5% positive rate — real jurisdictions will differ
- **No auto-retraining**: This is a hard constraint — monitoring output alone never triggers model retraining
- **Calibration drift detection**: ECE > 0.20 over 10 bins should trigger a calibration review, not automatic re-calibration

## 9.6 Artifacts Generated

| File | Description |
|---|---|
| `backend/services.py` | `evaluate_pending_outcomes()` — closed-loop learning (lines 640-670) |
| `backend/services.py` | `outcome_monitoring()` — monitoring summary (lines 673-702) |
| `artifacts/deep_eval/phase9_monitoring_md.md` | This document — outcome monitoring design |
| `artifacts/deep_eval/outcome_samples.json` (sample) | Sample outcome monitoring reports from evaluation data |

**Phase 9 complete: outcome monitoring and closed-loop learning documented.**

---

## 10. Final SIH Scoring — All 10 Phases Verified