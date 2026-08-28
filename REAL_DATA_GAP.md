# REAL_DATA_GAP.md — What It Would Take to Validate on Live NCRP/Bank Data (One Page)

## The gap, stated precisely
Every metric in this repository is measured on synthetic labels generated from
public-pattern-calibrated data (see `scripts/real_world_calibration.py` and
`artifacts/deep_eval/real_world_calibration.json`). The single claim the repo
does **not** make — and the single thing that would close the gap — is
evaluation against **authorized real NCRP/CFCFRMS/bank data**. Public analogs
(ATM counts, complaint volumes, fraud-share direction) confirm the *shape* of
the synthetic world but cannot substitute for per-ATM ground truth.

## What the team would need from I4C (the ask)
1. **MoU / data-access agreement** for a sandbox dataset — two weeks of
   historical NCRP complaints (anonymized/tokenized) + one week of
   investigation-confirmed withdrawal outcomes for a pilot district.
2. **Sandbox environment** (the I4C or state-CERT sandbox) with the
   schema-validated extracts per the contract in REAL_DATA_READINESS.md
   (4 tables: complaints, atms, withdrawals, accounts).
3. **Data dictionary sign-off** and a DPDP/DPO review of the processing
   (DPDP_ACT_COMPLIANCE.md is the starting posture).
4. **One designated liaison** for outcome confirmation (the label requires
   investigation-confirmed fraud withdrawals — only I4C/banks can create it).

## Realistic pilot plan (dates are placeholders; weeks count from agreement)

| Step | Duration | Deliverable |
|---|---|---|
| MoU + sandbox + data dictionary | W0 | Signed access; schema-validated extract |
| Week 1 | W1 | Data-quality scorecards + quarantine review (protocol §2, §4) |
| Week 2 | W2 | **Shadow mode** (`SHADOW_MODE=true`): predictions recorded, nothing dispatched |
| Week 3 | W3 | Silent prediction: scores vs confirmed outcomes; per-feature AUC leak audit re-run |
| Week 4 | W4 | Human-reviewed intervention evaluation on the pilot district; threshold re-derived; fairness/drift baselines set |
| W6–W8 | W6–W8 | Review gate with I4C ops; go/no-go on pre-registered KPIs (protocol §13); rollback conditions armed (protocol §14) |

## What changes in the pipeline (short list — no rewrites)
Platt recalibration on real outcomes · threshold re-derivation · per-feature
AUC re-audit · PSI drift baselines · model versioning + outcome store (already
in place). Architecture, features, splits, and the HOLD engine are unchanged —
they were built for this contract.

## What does NOT change the gap
Public datasets, simulations, transfer-readiness runs, or the calibration
pass — all useful, none substitute for the authorized pilot. Nothing in this
repository claims otherwise.