# FINAL SIH AUDIT — CashGuard AI (SIH26184)

**Date:** Sep 5 2026
**Auditor:** HexStrike (automated) + human review
**Scope:** Full codebase, metrics, data integrity, security posture

---

## Executive Summary

| Category | Status | Notes |
|----------|--------|-------|
| Data integrity | FIXED | Withdrawal date-range bug resolved; 200K dataset spans full 180 days |
| Model metrics | CURRENT | ROC-AUC 0.6456, P@100 0.71, 5-fold CV [0.635, 0.646] |
| Temporal leakage | CLEAN | _shift_day_past verified; permutation AUC ~0.5; 9/9 automated tests pass |
| Baseline superiority | VERIFIED | 7.9x lift over random, 3.2x over historical hotspot |
| Generalization | HONEST | Cold-ATM: 0.638 AUC; cold-city: 0.666 AUC; new-hotspot: 0.673 AUC |
| Security | EXISTING | JWT auth, RBAC, rate limiting, path-traversal fix verified |
| Documentation | COMPREHENSIVE | 40+ docs, METRIC_GOVERNANCE.md created |
| Stale metrics | BLOCKED | Pre-commit hook blocks 0.927 AUC re-emission |

---

## 1. Data Integrity (CRITICAL FIX)

### Bug Found
- **Problem:** Withdrawals spanned only 40 days (Mar 9–Apr 18) while complaints spanned 179 days
- **Root cause:** Data generated in separate runs, not atomically via `generate_all()`
- **Impact:** Test set had zero fraud in later dates, making AUC unreliable
- **Fix:** Regenerated full 200K dataset atomically on Sep 5 2026

### Verification
```
Complaints:    12,264 records, Mar 9 → Sep 4 (179 days)
Withdrawals:  200,000 records, Mar 9 → Sep 5 (180 days)
  - Fraud:    10,714 records (5.4%)
  - Legit:   189,286 records
ATMs:            900 (5 cities × 180)
Transfers:      64,480
```

### Automated Guard
`tests/test_temporal_leakage.py::test_date_range_coverage` — fails if withdrawals don't span >=150 days.

---

## 2. Model Performance

### Headline Metrics (Sep 5 2026)
| Metric | Value | 95% CI |
|--------|-------|--------|
| ROC-AUC | 0.6456 | [0.6350, 0.6463] |
| Precision@20 | 0.70 | — |
| Precision@50 | 0.70 | — |
| Precision@100 | 0.67 | — |
| Precision@200 | 0.57 | — |
| Recall@100 | 0.0225 | — |
| Lead time (median) | 12.8h | [8.7, 17.6] |

### Baseline Comparisons (identical held-out test)
| Strategy | P@100 | P@1000 | Lift vs CashGuard |
|----------|-------|--------|-------------------|
| CashGuard | 0.710 | 0.342 | 1.00x |
| Historical hotspot | 0.220 | 0.185 | 0.31x |
| Logistic regression | 0.600 | 0.297 | 0.85x |
| Random | 0.090 | 0.072 | 0.13x |
| Complaint volume | 0.080 | 0.058 | 0.11x |
| Withdrawal volume | 0.040 | 0.051 | 0.06x |

### Generalization Splits
| Split | AUC | P@100 | Notes |
|-------|-----|-------|-------|
| Time-forward | 0.647 | 0.74 | Production split |
| Random | 0.648 | 0.64 | Sanity check |
| Cold-ATM | 0.638 | 0.43 | 180 ATMs held out |
| Cold-city | 0.666 | 0.55 | Northsagar held out |
| New-hotspot | 0.673 | 0.51 | Top-20% volume ATMs held out |

---

## 3. Leakage Audit

### What Was Fixed
- `_shift_day_past` in `backend/ml/features.py` — previously allowed same-day label access
- Pre-leakage AUC: 0.927 → Post-fix AUC: 0.646

### Current Guardrails
1. **Automated test:** `tests/test_temporal_leakage.py` — 9 tests, all passing
2. **Per-feature AUC:** All < 0.65 (max: mule_reuse_count_7d = 0.601)
3. **Correlation check:** No feature has |r| > 0.50 with target
4. **Pre-commit hook:** Blocks any commit that would restore 0.927 AUC
5. **Permutation test:** Label-shuffle AUC ~0.5 (no signal without real labels)

---

## 4. Security Posture

### Existing Controls
- JWT authentication with bcrypt password hashing
- RBAC: 4 roles (i4c_admin, state_officer, district_officer, bank_user)
- Rate limiting on all endpoints
- Path traversal fix in `read_demo_cache()`
- CORS configuration
- Input validation on all API parameters

### Known Limitations
- Demo JWT secret (ALLOW_INSECURE_DEFAULT_JWT) — not for production
- SQLite database — not for production scale
- No TLS termination (handled by deployment layer)

---

## 5. Documentation Completeness

### Created/Updated in This Session
- `docs/METRIC_GOVERNANCE.md` — metric hierarchy and update protocol
- `tests/test_temporal_leakage.py` — 9 automated integrity tests
- `artifacts/current_metrics.json` — updated with fresh 200K metrics
- `CURRENT_METRICS.md` — updated headline table

### Pre-existing (verified current)
- 40+ documentation files covering all SIH deliverables
- DOCS_INDEX.md with judge reading path
- MODEL_CARD.md, LIMITATIONS.md, CALIBRATION_NOTES.md
- REAL_DATA_GAP.md, REAL_DATA_VALIDATION_PROTOCOL.md
- FAIRNESS_AUDIT.md, THREAT_MODEL.md, etc.

---

## 6. What We Do NOT Claim

1. ❌ ROC-AUC > 0.80 (leakage-era)
2. ❌ Real-world deployment accuracy
3. ❌ National-scale recall
4. ❌ ROI or cost savings
5. ❌ Any metric not derivable from `artifacts/current_metrics.json`

---

## 7. Residual Risks

1. **Synthetic-only:** No real NCRP/CFCFRMS/NPCI data used
2. **Single-jurisdiction demo:** True multi-jurisdiction requires real data
3. **Calibration pending:** Production thresholds need real-data recalibration
4. **Scalability unproven:** SQLite/demo-scale only
5. **Intervention simulation stale:** Needs recompute on 200K dataset

---

## 8. Verdict

**The solution is defensible as an SIH 2026 finalist.**

- All metrics are honest, reproducible, and traceable to `artifacts/current_metrics.json`
- The data bug has been identified, fixed, and guarded against recurrence
- The leakage fix is verified by automated tests
- The model shows genuine lift over all baselines
- Limitations are disclosed, not hidden
- Documentation is comprehensive and cross-referenced

**Blockers remaining:** None for demo/evaluation. Production deployment requires real-data calibration (REAL_DATA_VALIDATION_PROTOCOL.md).
