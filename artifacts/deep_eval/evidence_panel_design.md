# Phase 7 — Evidence Panels & Counterfactual What-If Analysis

**Phases 7a-7c** from the SIH specification — every forecast includes an evidence chain, 
counterfactual simulation, and uncertainty metadata clearly labelled as synthetic evaluation.

## 7a. 3-Field Evidence Panel (SIH Spec Section 5b)

Every alert includes a 3-field evidence panel composed at alert-creation time:

### Field 1: Complaint Activity
- **Content**: `"{n} complaint(s) in the last 6h within 2km of this ATM ({comp_detail})."` 
- **Linked accounts** named in these complaints are monitored for withdrawal activity
- **Source**: `repo.list_complaints(db, date_from=ref - timedelta(hours=6), limit=20000)`
- **Geofilter**: Within 2km of the flagged ATM using haversine distance
- **Disclosure**: "Linked accounts named in these complaints are monitored for withdrawal activity."

### Field 2: Withdrawal Activity
- **Content**: `"{n} withdrawal(s) from {n_accts} distinct account(s) at this ATM in the last 3h."`
- **Source**: `repo.recent_withdrawals(db, atm_id=alert.atm_id, since=ref - timedelta(hours=3))`
- **Distinct accounts**: `len({w.account_token for w in wd_3h})`

### Field 3: Context Signal + Verified/Assumed Disclosure
Three sub-signals composed from calibration config + verified patterns:

#### (a) Night-Time Weighting
```
"Forecast time is in the night window (19:00–05:00); night-time weighting 
is an {night_tag_replace_space} parameter (no India-specific public statistic)."
```
- Night hours: 19:00–05:00 (configurable via `NIGHT_HOURS`)
- Tag source status from calibration config

#### (b) Clustering Direction
```
"This ATM shows complaint-linked (mule) account activity in the {fr_hist_pct} — 
the DIRECTION of withdrawal clustering is a verified pattern (I4C Suspect Registry 
documents concentrated cash-out hubs); the exact concentration coefficients are 
{tunable_parameters}."
```
- `fr_hist_pct`: percentile label of `linked_proportion_24h` vs training reference
- Direction: "up" if `linked_proportion_24h >= 0.4`, else "flat"
- Tag source status from calibration config

#### (c) Cluster Direction Summary
Combined context_signal = night_clause + cluster_clause

## 7b. Counterfactual What-If Analysis (Phase 4)

### Protocol
Per-alert WHAT-IF: recompute the risk with complaint-surge signals set to zero at inference time.
**Valid input ablation** — not a causal claim.

### What's Removed
```python
for c in ["n_complaints_city_24h", "n_complaints_city_7d", "t_phishing_7d",
          "t_investment_fraud_7d", "t_job_fraud_7d", "t_upi_fraud_7d",
          "hours_since_last_complaint_city"]:
    counter[c] = 0.0
```

### Output Format
```json
{
  "current_risk": 0.76,             // current predicted risk score
  "risk_without_complaint_surge": 0.71,  // risk with surge signals zeroed
  "delta": 0.05,                    // current - without (positive = surge was contributing)
  "interpretation": (
    "Counterfactual simulation: complaint-surge signals removed at inference "
    "time (valid input ablation). NOT a causal claim; residual risk is carried "
    "by withdrawal/mule-behavioural signals."
  )
}
```

### Interpretation Guidelines
| Delta magnitude | Interpretation |
|---|---|
| delta >= 0.15 | Surge was major contributor — risk highly complaint-dependent |
| 0.05 <= delta < 0.15 | Surge was moderate contributor — risk partially complaint-dependent |
| delta < 0.05 | Surge was minor — risk carried by withdrawal/mule behavioural signals |

### What's Preserved (residual risk carriers)
- Withdrawal behaviour: `withdrawals_6h`, `withdrawals_24h`, `fund_velocity_24h`
- Mule indicators: `counterparty_count_24h`, `linked_proportion_24h`
- Geospatial: `dist_to_complaint_centroid_km`, `night_ratio_24h`
- Calendar: `day_of_week`, `is_weekend`, `days_to_festival`, `is_salary_day`

### Labelled Clearly
Every counterfactual output includes:
```
"synthetic_evaluation": True,
"counterfactual_note": "Valid input ablation at inference time. NOT a causal claim. "
                       "Residual risk carried by non-complaint signals."
```

## 7c. Uncertainty Block (Phase 7c)

Every alert includes an uncertainty block in the ledger and WebSocket broadcast:

```json
{
  "risk_score": 0.76,
  "confidence": "Medium",           // High/Medium/Low based on score + evidence + disagreement
  "evidence_strength": "4/5",       // 1 baseline + SHAP/global + freeze intel
  "data_freshness_hours": 12,       // hours since ref time
  "model_version": "2026-09-03",
  "model_disagreement_abs": 0.12,   // abs difference between Model A and Model B
  "prediction_timestamp": "2026-09-04T10:30:00Z",
  "prediction_horizon_hours": 24,
  "synthetic_evaluation": True,
  "insufficient_evidence": false,   // true if evidence_strength < 3 OR freshness > 48h OR disagreement > 0.35
}
```

### Confidence Determination
| Condition | Confidence |
|---|---|
| score >= 0.85 AND evidence_strength >= 4 | High |
| score >= 0.70 OR evidence_strength >= 3 | Medium |
| score < 0.70 AND evidence_strength < 3 | Low |
| disagreement > 0.35 | Low (model disagreement) |
| 0.20 < disagreement <= 0.35 | Medium (reduced — model disagreement) |

### Model Disagreement (Phase 10 feature)
Compares Model A (XGBoost + Platt) vs Model B (statistical baseline):
```python
disagreement = abs(score_A - score_B)
if disagreement > 0.35: confidence = "Low (model disagreement)"
if disagreement > 0.20: confidence = "Medium (reduced — model disagreement)"
```
Model B is loaded from `model_b.joblib` if available; disagreement is optional — absent 
`model_b.joblib`, `disagreement = None` and confidence follows score+evidence only.

### Insufficient Evidence Flag
```python
insufficient_evidence = (
    evidence_strength < 3 or 
    (freshness_h is not None and freshness_h > 48) or 
    (disagreement is not None and disagreement > 0.35)
)
```
When `insufficient_evidence=True`, the alert should sit in HOLD ACTION zone even if
risk_score >= 0.70, and a `hold_reason` field is set to `"model disagreement"` or 
`"insufficient evidence — data too stale"`.

## 7d. Evidence Graph (Phase 7d)

Visual evidence chain per alert — 5 signals with direction/source/tags:

| Signal | Value Format | Direction | Source Type | Synthetic |
|---|---|---|---|---|
| Recent complaint surge | `"{n} complaint(s) within 2km"` | up/flat | complaint_record | synthetic |
| Transaction velocity increase | `"withdrawals_6h={x}, withdrawals_24h={y}"` | up/flat | withdrawal_record | synthetic |
| Mule-account concentration | `"counterparty_count_24h={x}, linked_share={y:.2f}"` | up/flat | complaint_linkage | synthetic |
| Geographic proximity | `"dist_to_complaint_centroid_km={x:.1f}"` | near/far ( <=10km) | geography | synthetic |
| Temporal similarity (Hawkes) | `"hawkes_intensity_24h={x:.3f}"` | up/flat ( >15) | complaint_timeline | synthetic |
| Forecast risk | `"{x:.2f} (threshold >= 0.70)"` | flagged/not-flagged | model_output | synthetic |

Each graph entry includes:
- `signal`: descriptive name
- `value`: quantitative value
- `direction`: up/flat based on threshold comparisons
- `source_type`: complaint_record / withdrawal_record / geography etc.
- `observed_or_synthetic`: always "synthetic" (clearly labelled)

## 7e. Per-Instance SHAP (Optional)

Via XGBoost's native `pred_contribs`:
- Top-5 features by |SHAP| value with feature value and direction
- Labelled as "global importance + instance percentile (interpretation aid)"
- No causal claim implied
- Included in evidence package but not required for basic operation

```json
"per_instance_shap": [
  {"feature": "counterparty_count_24h", "value": 8.7, "shap": 0.15},
  {"feature": "withdrawals_24h", "value": 23.0, "shap": 0.12},
  ...
]
```

## 8. Honest Limits (All Sections)

- Every section explicitly labelled `"synthetic_evaluation": True`
- No causal claims implied — all are valid input ablations / descriptive statistics
- Real-world evidence panels require: human-reviewed complaint investigation, 
  actual withdrawal investigation, domain-expert interpretation
- SHAP values are model-local — not globally transferable; different models get different SHAP
- Counterfactual what-if is input ablation, not counterfactual causal effect
- Uncertainty block quantities (data freshness, model disagreement) depend on 
  real-time data availability; in production shard/cluster environments these must be
  instrumented from the actual prediction pipeline
- The 3-field evidence panel geofilter (2km) is a demo convention; real programs
  may use different radius based on jurisdictional practice

## 9. Artifacts Generated

| File | Description |
|---|---|
| `artifacts/deep_eval/hold_action_panel.md` | HOLD ACTION policy + evidence packages (from Phase 4) |
| `artifacts/deep_eval/evidence_panel_design.md` (planned) | 3-field evidence panel specification |
| `backend/services.py` | `build_alert_evidence()` — 3-field evidence + counterfactual + uncertainty + graph (lines 742-890) |
| `backend/services.py` | `_counterfactual_whatif()` — per-alert ablation (lines 498-532) |
| `backend/services.py` | `_uncertainty_block()` — confidence + disagreement (lines 542-587) |
| `backend/services.py` | `_evidence_graph()` — visual evidence chain (lines 590-637) |

**Phase 7 complete: evidence panels and counterfactual what-if analysis documented.**