# JUDGE FAQ — CashGuard AI (SIH26184)

**Date:** Sep 5 2026
**Source of truth:** `artifacts/current_metrics.json`

---

## Q1: What is the headline ROC-AUC?

**0.6456** on the held-out test set (chronological split). 5-fold CV 95% CI: [0.6350, 0.6463].

This is the honest, leak-free number on the full 200K synthetic dataset (180-day span).

---

## Q2: Why was the earlier 0.927 AUC retracted?

Same-day label leakage in `_shift_day_past` (backend/ml/features.py). Rolling-window features
included the target day itself, inflating AUC from ~0.65 to ~0.93. Fixed. Pre-commit hook
blocks 0.927 AUC re-emission permanently.

---

## Q3: What is the model's operational value?

The model concentrates finite reviewer attention on 50-100 ATM-days per cycle at 67-71% precision.
This is a triage accelerator, NOT a standalone detection system. Lead time: median 12.8 hours.

---

## Q4: How does CashGuard compare to baselines?

| Strategy | P@100 | Lift vs CashGuard |
|----------|-------|-------------------|
| CashGuard | 0.710 | 1.00x |
| Historical hotspot | 0.220 | 0.31x |
| Logistic regression | 0.600 | 0.85x |
| Random | 0.090 | 0.13x |
| Complaint volume | 0.080 | 0.11x |
| Withdrawal volume | 0.040 | 0.06x |

CashGuard achieves 7.9x lift over random and 3.2x over historical hotspot at P@100.

---

## Q5: Is this real data?

No. All data is synthetic, calibrated, and source-tagged (CALIBRATION_NOTES.md). No real
NCRP/CFCFRMS/NPCI data was used. REAL_DATA_GAP.md explains what real data would change.

---

## Q6: What are the main limitations?

1. Synthetic-only: no real-world field performance claimed
2. Single-jurisdiction demo: true multi-jurisdiction requires real data
3. Low absolute recall: by design, the system prioritizes precision over recall
4. Cold-ATM generalization gap: 0.638 AUC vs 0.647 time-forward
5. Scalability unproven: SQLite/demo-scale only

---

## Q7: How many features does the model use?

44 features across 8 groups: complaint signals (8), ATM context (6), behavioural (4),
Hawkes temporal (1), geospatial (2), calendar (3), architectural Issue-1 (12), amount (8).

---

## Q8: What is the prediction horizon?

24 hours. The model predicts P(fraud at ATM in next 24h). Multi-horizon confidence
(2/6/12/24/48/72h) is available in the dashboard but the primary model is 24h.

---

## Q9: What is the false alert rate?

~30% at the primary operating point (threshold 0.50, 70 alerts, P=0.70).
At threshold 0.60: 27% false alert rate, 33 alerts, P=0.73.

---

## Q10: How was the model calibrated?

Platt sigmoid calibration fitted on the validation slice. Production thresholds remain
synthetic-calibrated until real-data recalibration (CALIBRATION_NOTES.md).

---

## Q11: What is the lead time?

Median 12.8 hours (P25 8.7h, P75 17.6h). This is the advance warning before fraud
cash-out occurs. Horizon-dependent: shorter horizons have less lead time.

---

## Q12: Can the model be gamed?

The model uses behavioural features (velocity, counterparty, frequency) that are difficult
to game without disrupting normal banking activity. The Hawkes temporal intensity captures
self-exciting fraud patterns. Fairness audit shows flat FPR across demographic groups.

---

## Q13: What happens on calm days with no fraud?

The model scores every ATM low (max ~0.06) and produces no alerts. This is honest behavior.
Any populated high-risk alert view in the demo is served via the "Load Simulated Scenario"
button and is clearly labeled as scripted.

---

## Q14: How does the alert cycle work?

ATM risk scores → threshold-based alert generation → dedup + escalation bypass →
role-based dispatch (district officer / bank / I4C) → investigation → outcome logging.
WebSocket live push for real-time updates.

---

## Q15: What is the FairnessCap?

A runtime cap that limits false-positive rate disparity across demographic groups.
Currently flat at 0.0015-0.0062 FPR across 15 groups (FAIRNESS_AUDIT.md).

---

## Q16: Is there an audit trail?

Yes. Tamper-evident SHA-256 hash chain with 3-node replication. Every alert, investigation,
and outcome is logged with timestamps and actor identity. Blockchain justification documented.

---

## Q17: What would change with real data?

1. Calibration would be real (not synthetic)
2. Feature importance would reflect real fraud patterns
3. Generalization splits would be meaningful
4. Production thresholds would be data-driven
5. Lead time would be operationally validated

See REAL_DATA_VALIDATION_PROTOCOL.md for the 14-step path.

---

## Q18: How do I reproduce the results?

```bash
cd "CashGuard AI"
python scripts/generate_data.py --complaints 12000 --withdrawals 200000 --months 6
python scripts/train_model.py
python -m pytest tests/test_temporal_leakage.py -v
```

---

## Q19: What is the intervention simulation?

A controlled simulation comparing CashGuard's forecast-driven intervention to random,
volume-based, and historical hotspot strategies on the identical held-out test period.
CashGuard captures 7.9x more fraud per intervention than random selection.

---

## Q20: Where is the source of truth for all metrics?

`artifacts/current_metrics.json` — the single source of truth for all headline metrics.
Every document in this repository must cite this file. See docs/METRIC_GOVERNANCE.md.
