# FINAL SIH JUDGE SCORECARD — CashGuard AI (SIH26184)

**Date:** Sep 5 2026
**Status:** READY FOR JUDGING

---

## Scorecard Summary

| Criterion | Score | Evidence | Status |
|-----------|-------|----------|--------|
| Problem relevance | HIGH | 8,000+ daily NCRP complaints, zero recovery | OK |
| Technical approach | HIGH | XGBoost + Platt + Hawkes + 44 features | OK |
| Innovation | MEDIUM | Predictive (not reactive) ATM risk scoring | OK |
| Feasibility | HIGH | Working demo, Docker, deployed locally | OK |
| Impact | HIGH | 7.9x lift over random, 12.8h lead time | OK |
| Ethics & fairness | HIGH | FPR flat across groups, DPDP compliance | OK |
| Documentation | HIGH | 40+ docs, METRIC_GOVERNANCE, audit trail | OK |
| Honesty | HIGH | Leakage fixed, 0.927 blocked, limitations disclosed | OK |

---

## Critical Metrics (Sep 5 2026)

| Metric | Value | Context |
|--------|-------|---------|
| ROC-AUC | 0.6456 | Test set, chronological split |
| 5-fold CV | [0.635, 0.646] | Stratified, 200K dataset |
| P@100 | 0.71 | Top-100 ATM-days per test day |
| P@1000 | 0.34 | Top-1000 ATM-days |
| Lift vs random | 7.9x | At P@100 |
| Lift vs historical | 3.2x | At P@100 |
| Lead time | 12.8h median | [8.7, 17.6] IQR |
| Features | 44 | Issue-1 architecture |
| Generalization | 0.638-0.673 AUC | Cold-ATM to new-hotspot |

---

## Blocker Elimination

| Blocker | Status | Resolution |
|---------|--------|------------|
| 0.927 leakage AUC | ELIMINATED | Pre-commit hook blocks re-emission |
| 40-day withdrawal span | FIXED | Regenerated 200K dataset atomically |
| Stale metrics | FIXED | current_metrics.json updated Sep 5 |
| Missing METRIC_GOVERNANCE | CREATED | docs/METRIC_GOVERNANCE.md |
| Missing temporal tests | CREATED | tests/test_temporal_leakage.py (9/9 pass) |
| Missing FINAL_AUDIT | CREATED | docs/FINAL_SIH_AUDIT.md |

---

## Adversarial Review

### What a hostile judge might attack:
1. **"AUC is low (0.65)"** → Response: Honest for detuned synthetic task; 0.82+ requires leakage or real data. Lift over baselines (7.9x) is the operational metric.
2. **"Synthetic data is meaningless"** → Response: Calibrated, source-tagged, every parameter cited. Real-data validation protocol exists (REAL_DATA_VALIDATION_PROTOCOL.md).
3. **"No real deployment"** → Response: Honest. Docker ready, 30-day shadow pilot planned. Demo-quality prototype, not production.
4. **"Low recall"** → Response: By design. System concentrates finite reviewer attention on 50-100 ATM-days at 67-71% precision. NOT national recall.
5. **"Feature count changed (24→44)"** → Response: Issue-1 upgrade documented in current_metrics.json. All features trailing-window only, permutation-verified.

### What we disclose proactively:
- Leakage history (0.927 → 0.646)
- Data bug (40-day → 180-day span)
- Synthetic-only (no real data)
- Cold-ATM generalization gap (0.638 vs 0.647 time-forward)
- Low absolute recall at dispatch thresholds
- Single-jurisdiction demo scope

---

## Documentation Index (all current, Sep 5 2026)

| File | Purpose |
|------|---------|
| CURRENT_METRICS.md | Headline metrics (ROC-AUC 0.6456) |
| docs/METRIC_GOVERNANCE.md | Metric hierarchy and update protocol |
| docs/FINAL_SIH_AUDIT.md | Comprehensive audit report |
| MODEL_CARD.md | Model facts (44 features, XGBoost) |
| JUDGE_BRIEF.md | 2-page judge brief (updated) |
| DOCS_INDEX.md | Where-to-look map |
| LIMITATIONS.md | Honest limitations |
| CALIBRATION_NOTES.md | Every parameter source-tagged |
| REAL_DATA_GAP.md | What real data would change |
| FAIRNESS_AUDIT.md | Group FPR analysis |
| THREAT_MODEL.md | Security posture |

---

## Verdict

**CashGuard AI is defensible as an SIH 2026 finalist.**

- All metrics honest, reproducible, traceable to `artifacts/current_metrics.json`
- Data bug identified, fixed, guarded against recurrence
- Leakage fix verified by 9 automated tests
- Model shows genuine 7.9x lift over random baseline
- Limitations disclosed, not hidden
- Documentation comprehensive and cross-referenced
- No blockers remaining for demo/evaluation
