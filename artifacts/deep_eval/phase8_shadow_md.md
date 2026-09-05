# Phase 8 — SHADOW_MODE & Model Monitoring (Phases 8-9)

**SHADOW_MODE** (Phase 14) and **model monitoring** (Phase 9) are sister features that
operate in complementary modes: SHADOW_MODE is a risk-free evaluation mode; model monitoring
is the closed-loop learning pipeline for production deployment hygiene.

## 8.1 SHADOW_MODE — Risk-Free Evaluation Mode

### 8.1.1 Configuration
```bash
export SHADOW_MODE="true"  # enable shadow mode
```
Or via `.env` file: `SHADOW_MODE=true`

### 8.1.2 What Happens in SHADOW_MODE
When `SHADOW_MODE=true`, the following are **suppressed** (no real-world impact):

| Component | Behaviour in SHADOW_MODE |
|---|---|
| SMS dispatch | `send_sms()` suppressed — prediction recorded only |
| Email dispatch | `send_email()` suppressed — prediction recorded only |
| Webhook dispatch | `_dispatch_webhook("dispatch", ...)` suppressed |
| Live WS push | `enqueue_broadcast("alert", ...)` suppressed |
| Alert status | All alerts created with `status="shadow"` |
| Fund-block recommendations | Still created but labelled `status="shadow"` |
| CFCFRMS webhook | Still triggered but to mock inbox only |
| Recovery funnel | Still computed but outcomes are synthetic |

### 8.1.3 What Is Still Recorded
Even in SHADOW_MODE, the following are **always recorded** for evaluation:

| Record | Purpose |
|---|---|
| Alert creation | `repo.create_alert(db, ...)` with `status="shadow"` |
| Ledger entries | `repo.append_ledger(db, ...)` — full audit trail |
| Counterfactual what-if | `_counterfactual_whatif()` still computed |
| Uncertainty block | `_uncertainty_block()` still computed |
| Evidence graph | `_evidence_graph()` still computed |
| Recovery funnel | `recovery_funnel()` still computed (synthetic outcomes) |
| Model version tracking | `_model_version()` still captures `trained_at` |

### 8.1.4 SHADOW_MODE Use Cases
| Use Case | Description |
|---|---|
| New feature deployment | Run SHADOW_MODE for 2-3 cycles before enabling real dispatch |
| A/B comparison | Compare Model A vs Model B predictions without operational impact |
| Training data validation | Verify that new data streams don't break the prediction pipeline |
| Audit & compliance | Full audit trail without any real-actions being taken |
| Demo / SIH presentation | Show the system working without any real alerts being fired |

### 8.1.5 SHADOW_MODE Inspection Commands
```python
# Check how many shadow alerts were created today
shadow_count = repo.count_alerts(db, status="shadow")

# Compare shadow vs real alert volumes
real_count = repo.count_alerts(db, status="new")
print(f"Shadow: {shadow_count}, Real: {real_count}")

# Verify all shadow alerts have evidence packages
alerts = repo.list_alerts(db, limit=100)
for a in alerts:
    if a.status == "shadow" and not a.evidence_json:
        print(f"Missing evidence for shadow alert {a.alert_id}")
```

## 8.2 Model Monitoring (Phase 9)

### 8.2.1 Closed-Loop Learning Pipeline
The monitoring pipeline evaluates past alerts against actual outcomes and writes
`AlertOutcome` records. **Never auto-retrains** — human-in-the-loop only.

### 8.2.2 Outcome Evaluation (run_pending_outcomes)
```python
def evaluate_pending_outcomes(db: Session) -> int:
    cutoff = datetime.utcnow() - timedelta(hours=24)
    alerts = repo.list_alerts(db, limit=500)
    evaluated = 0
    
    for a in alerts:
        if a.created_at < cutoff:  # older than 24h
            if repo.get_alert_outcome(db, a.alert_id) is None:
                # Check actual outcomes in next 24h
                window = [a.created_at, a.created_at + timedelta(hours=24)]
                wds = repo.recent_withdrawals(db, atm_id=a.atm_id, since=window[0])
                fraud_now = [w for w in wds if w.timestamp <= window[1] and w.is_fraud_withdrawal]
                actual = "yes" if fraud_now else "no"
                pred = a.risk_score
                
                repo.create_alert_outcome(
                    db,
                    alert_id=a.alert_id,
                    predicted_risk=pred,
                    actual_fraud_happened=actual,
                    prediction_error=round(abs((1.0 if actual == "yes" else 0.0) - pred), 4),
                    is_false_positive=(actual == "no" and pred >= 0.5),
                    is_false_negative=(actual == "yes" and pred < 0.5),
                    evaluated_at=datetime.utcnow(),
                    model_version=a.model_version or "",
                )
                evaluated += 1
    return evaluated
```

### 8.2.3 Outcome Monitoring Summary
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
    
    # Calibration drift: ECE over 10 bins
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

### 8.2.4 Monitoring Output Fields

| Field | Meaning |
|---|---|
| `evaluated` | Number of aged alerts with outcomes |
| `true_positives` | Correctly flagged fraud events |
| `false_positives` | Flagged but no fraud occurred |
| `true_negatives` | Correctly cleared (no fraud, low risk) |
| `false_negatives` | Missed fraud events (risk < 0.5 but fraud happened) |
| `mean_abs_error` | Mean absolute error between predicted risk and actual outcome |
| `outcome_ece_10_bins` | Expected Calibration Error over 10 probability bins — calibration drift indicator |
| `note` | Explicit labelling: synthetic evaluation, no auto-retraining |

### 8.2.5 Monitoring Honest Limits
- **Small samples**: Phase 9 monitoring requires >24h aging time per alert; early evaluation is unreliable
- **Synthetic labels**: Outcomes are against the synthetic withdrawal label, not real-world fraud
- **No auto-retraining**: The pipeline explicitly does NOT auto-retrain on small samples
- **Base rate dependency**: FP/FN rates depend heavily on the 5% positive rate; real-world base rates will shift all metrics
- **Calendar effects**: FP/FN rates vary by day-of-week, festival periods, salary days — monitor across multiple windows

## 8.3 SHADOW_MODE vs Model Monitoring — Comparison

| Aspect | SHADOW_MODE | Model Monitoring |
|---|---|---|
| **Purpose** | Risk-free evaluation mode | Closed-loop learning / calibration check |
| **Timing** | Real-time, per-alert cycle | Post-hoc, after 24h horizon |
| **Action suppression** | All dispatch/WS suppressed | No suppression — monitors after the fact |
| **Data used** | Current prediction pipeline | Historical alerts + actual outcomes |
| **Output** | Suppressed predictions + audit trail | Outcome metrics + calibration drift |
| **Auto-retrain** | Disabled (by design) | Disabled (by design — human-in-loop only) |
| **Typical duration** | Ongoing, per-cycle | Per evaluation window (e.g., weekly) |
| **Label source** | Synthetic (built into prediction task) | Synthetic withdrawal label from withdrawal DB |

## 8.4 Honest Limits (Both Phases)

- SHADOW_MODE: "Risk-free" only for operational actions — analysis and reporting still occur
- Model monitoring: Synthetic labels mean real-world calibration requires prospective validation
- Neither phase substitutes for prospective validation in production deployment
- SHADOW_MODE should be disabled (set to `false`) before any real LEA/bank dispatch is enabled
- Model monitoring metrics should be tracked over rolling windows (weekly/monthly), not single evaluation runs

## 8.5 Artifacts Generated

| File | Description |
|---|---|
| `backend/config.py` | `SHADOW_MODE` environment variable (line 111) |
| `backend/services.py` | `SHADOW_MODE` usage in `run_alert_cycle()` (line 260) and throughout dispatch code |
| `backend/services.py` | `evaluate_pending_outcomes()` — closed-loop learning (lines 640-670) |
| `backend/services.py` | `outcome_monitoring()` — monitoring summary (lines 673-702) |
| `artifacts/deep_eval/phase8_shadow_md.md` | This document — SHADOW_MODE specification |
| `artifacts/deep_eval/phase9_monitoring_md.md` (planned) | Model monitoring design and metrics specification |

**Phase 8 complete: SHADOW_MODE and model monitoring documented.**