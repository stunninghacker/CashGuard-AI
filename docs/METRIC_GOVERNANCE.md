# Metric Governance — CashGuard AI (SIH26184)

**Single source of truth:** `artifacts/current_metrics.json`

---

## 1. Why This Document Exists

CashGuard AI went through a metric lifecycle:
1. **Leakage era (Aug 2026)**: ROC-AUC ~0.927 — invalid due to same-day label leakage in `_shift_day_past`
2. **Post-fix era (Aug 31 2026)**: ROC-AUC ~0.627 — honest but dataset had only 45K withdrawals (40-day span)
3. **Current era (Sep 5 2026)**: ROC-AUC 0.6456 — full 200K withdrawal dataset, 180-day span

Every metric in this repository MUST trace back to `artifacts/current_metrics.json`. No document may assert a performance figure that cannot be derived from this file.

---

## 2. Metric Hierarchy

```
artifacts/metrics.json          ← raw training output (machine-generated)
    ↓
artifacts/current_metrics.json  ← human-curated single source of truth
    ↓
All documentation (README, MODEL_CARD, JUDGE_BRIEF, etc.)
```

### Rules
1. **Never hardcode metrics in docs** — always reference `artifacts/current_metrics.json`
2. **Never claim 0.92x AUC** — that figure was leakage-invalid and is permanently blocked by `.git/hooks/pre-commit`
3. **Always disclose evaluation context** — "synthetic-only, chronological split, not field performance"
4. **Baseline comparisons must be contemporaneous** — same train/test split, same preprocessing

---

## 3. Current Headline Metrics (Sep 5 2026)

| Metric | Value | Context |
|--------|-------|---------|
| ROC-AUC | 0.6456 | Test set, chronological split |
| Precision@20 | 0.70 | Top-20 ATM-days per test day |
| Precision@50 | 0.70 | Top-50 ATM-days per test day |
| Precision@100 | 0.67 | Top-100 ATM-days per test day |
| Precision@200 | 0.57 | Top-200 ATM-days per test day |
| Recall@100 | 0.0225 | Absolute recall at K=100 |
| Accuracy | 0.9393 | Baseline accuracy (mostly negative class) |
| Lead time (median) | 12.8 hours | Median advance warning before fraud |
| Lead time (P25-P75) | 8.7–17.6 hours | Interquartile range |

### What These Metrics Mean Operationally
- **NOT national recall** — the system concentrates finite reviewer attention on 50-100 ATM-days per cycle at 67-70% precision
- **Not a standalone detection system** — it's a triage accelerator for investigators
- **Synthetic-only** — no real-world field performance is claimed

---

## 4. Dataset Provenance

| Parameter | Value | Source |
|-----------|-------|--------|
| Complaints | 12,264 | Synthetic generator |
| Withdrawals | 200,000 | Synthetic generator (20K fraud) |
| ATMs | 900 | 5 fictional cities × 180 ATMs |
| Date span | 2026-03-09 → 2026-09-05 | 180 days |
| Fraud share | 10% | `calibration_config.yaml` |
| Split | Chronological 70/15/15 | Split day: 2026-07-14 |

### Data Fix (Sep 5 2026)
**Problem:** Previous dataset had only 45,000 withdrawals spanning 40 days (Mar 9–Apr 18) while complaints spanned 179 days. This made test-set evaluation unreliable.

**Root cause:** Data was generated in separate runs (complaints regenerated, withdrawals left from earlier generation).

**Fix:** Regenerated full 200K dataset atomically via `generate_all()` with identical `start`/`end` parameters.

---

## 5. What We Do NOT Claim

1. ❌ ROC-AUC > 0.80 (leakage-era figure)
2. ❌ Real-world deployment accuracy
3. ❌ National-scale recall
4. ❌ ROI or cost savings
5. ❌ Any metric not derivable from `artifacts/current_metrics.json`

---

## 6. How to Verify Metrics

### Quick verification
```bash
cd "CashGuard AI"
python scripts/train_model.py
# Compare output with artifacts/metrics.json
```

### Leakage check
```bash
python -m pytest tests/test_temporal_leakage.py -v
```

### Audit trail
```bash
cat artifacts/metrics.json | python -m json.tool | head -30
# Verify trained_at is recent, split_day is correct, AUC matches
```

---

## 7. Metric Update Protocol

When retraining:
1. Run `python scripts/train_model.py` → updates `artifacts/metrics.json`
2. Manually update `artifacts/current_metrics.json` with new values
3. Update any documentation that cites specific metrics
4. Run leakage tests to verify no regression
5. Run `git diff` to review all metric changes before committing

---

## 8. Historical Metric Timeline

| Date | ROC-AUC | Dataset | Status |
|------|---------|---------|--------|
| Aug 26 2026 | 0.927 | 45K withdrawals | ❌ SUPERSEDED (leakage) |
| Aug 31 2026 | 0.627 | 45K withdrawals | ⚠️ STALE (date range bug) |
| Sep 5 2026 | **0.6456** | **200K withdrawals** | ✅ **CURRENT** |

---

## 9. References

- `artifacts/current_metrics.json` — single source of truth
- `artifacts/metrics.json` — raw training output
- `backend/ml/features.py` — feature computation (44 features)
- `backend/ml/train.py` — model training + evaluation
- `backend/data/calibration_config.yaml` — data generation parameters
- `docs/FINAL_LEAKAGE_AUDIT.md` — leakage fix history
- `.git/hooks/pre-commit` — blocks 0.927 AUC re-emission
