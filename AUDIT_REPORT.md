# AUDIT_REPORT.md — Baseline Audit (SIH26184)

**Date**: 2026 · **Auditor role**: lead architect / ML / security / product / QA
**Method**: full-repo inspection; every claim below is grounded in code or artifact, not assertion.
**Legend**: ✅ present · ⚠️ partial/needs work · ❌ missing

---

## Overall score: **7.2 / 10**

A genuinely strong, honest prototype with a real evaluation spine (time-split, baselines, lead-time,
leak controls, tamper-evident ledger). It is NOT yet a finalist-level *evidence-first* system: the
evaluation is single-world, the dashboard is informative but not decision-first, uncertainty is not
surfaced, human-in-the-loop statuses are coarse, and several operational metrics are missing.

## A. Problem alignment — 8/10 ✅

- All four deliverables (predictive engine, GIS heatmap + drill-downs, secure LEA interface +
  reports, alert/notification system) are live.
- Recovery/CFCFRMS loop and "proactive" positioning match SIH26184 directly.
- ⚠️ Lead-time is evaluated but not surfaced *per horizon*; "proactive" is not yet the UI's core story.

## B. ML validity — 7/10

| Check | Status |
|---|---|
| Target leakage (fraud_withdrawals_24h) | ✅ removed; `is_fraud_withdrawal` is label-only (grep-verified) |
| Temporal leakage (train/val/test) | ✅ chronological; early stopping + calibration use VALIDATION only |
| Class imbalance | ✅ handled (scale_pos_weight) + documented; positive share 6.9% |
| Suspiciously powerful features | ✅ per-feature AUC reported; max 0.8466 (complaint-linked, prediction-time-safe) |
| Calibration | ⚠️ Platt + calibration curve exist; **Brier/ECE/reliability curve not measured** |
| Metric inflation | ⚠️ ROC-AUC still the headline; **PR-AUC, false-alert rate, alert volume, capture rate missing** |
| Cold-location generalization | ❌ no held-out-ATM evaluation |
| Ablation (feature-family value) | ❌ no ablation study |
| Adversarial/perturbed worlds | ⚠️ only ±30% parameter perturbation exists; no scenario worlds (geographic/temporal/delay/drift/sparse) |
| Counterfactual sensitivity | ❌ none |
| Horizon analysis (6/12/24/48h) | ❌ none |
| Robustness to perturbation | ✅ ±30% grid (P@K stable) |

## C. Architecture — 8/10 ✅

- ✅ bcrypt + JWT (access/refresh); RBAC with row-level scoping in the repository layer; access
  audit on the ledger; SQLAlchemy abstraction (SQLite→PostgreSQL one-line); repository layer as the
  single data door; Dockerfile; env-driven config with `.env.example`; smoke test; DEMO_MODE cache.
- ⚠️ **CORS default `*`** — should default to the demo origin.
- ⚠️ **No rate limiting** on auth/data endpoints (demo-scale, but a hardening item).
- ⚠️ Model versioning is a timestamp only; alerts don't carry the model version.
- ⚠️ Auth secret default is a dev placeholder (fine for demo; must be env-forced in prod).

## D. Product — 6/10 ⚠️

- ✅ Evidence panel (3 fields + disclosure + SHAP + freeze intel), graded response playbook,
  PDF reports, recovery queue + funnel, alert ack/actioned workflow.
- ⚠️ Alert statuses are only `new/acknowledged/actioned` — **no dismiss / escalate / monitor /
  request-more-data with mandatory reason**.
- ⚠️ **No "insufficient evidence — hold action" state.**
- ⚠️ **No uncertainty/confidence/data-freshness shown on forecasts.**
- ⚠️ **No evidence graph** (visual causal-ish chain per alert).
- ⚠️ **No emerging vs historical risk separation**; dashboard is informative, not decision-first.
- ❌ **No closed-loop outcome tracking** (predicted vs actual vs UNKNOWN).

## E. Ethics — 8/10 ✅

- ✅ Zero demographic features (anti-profiling enforced); advisory-only banner; human-decision
  requirement; fairness/concentration monitor (Gini); ledger auditability; DPDP posture documented.
- ⚠️ Recommendation language still includes "Deploy patrol team" for CRITICAL — should be
  **review-oriented** ("Review recommended"), per the human-in-the-loop principle.

---

## Critical blockers (must fix)

1. **Operational metrics absent** (PR-AUC, false-alert rate, alert volume, capture rate) — the
   metrics a real I4C ops review needs.
2. **No uncertainty surfaced** — judges and officers must never read a bare 82% as certainty.

## Major weaknesses

3. No cold-location evaluation (a genuinely important generalization check).
4. No ablation study (feature-family value unproven).
5. No horizon analysis (6/12/24/48h) — "proactive" is unquantified.
6. No closed-loop outcome store (learning loop unproven).
7. No adversarial scenario worlds beyond parameter perturbation.

## Moderate weaknesses

8. Human-in-the-loop statuses coarse; no mandatory reason for dismiss/escalate.
9. No "insufficient evidence — hold action" state.
10. CORS default `*`; no rate limiting.
11. Model version not carried on alerts; uncertainty metadata absent.

## Minor improvements

12. Dashboard could answer the 7 decision questions on first screen.
13. Demo script could be tightened to the 16-step evidence-first scenario.
14. Emerging-risk vs historical-risk separation.
15. Counterfactual sensitivity demo.

## Recommended implementation order (matches the mandate phases)

1. Phase 2: evaluation depth — operational metrics, ablation, cold-location, adversarial worlds,
   counterfactuals, calibration quality (all as static, artifact-backed evaluations).
2. Phase 3: horizon analysis (6/12/24/48h).
3. Phases 4–5: uncertainty block + evidence graph (backend + UI).
4. Phases 6–7: human-in-the-loop statuses + HOLD-ACTION.
5. Phase 8: emerging risk. 6. Phase 9: closed-loop outcomes.
7. Phase 10: security defaults. 8. Phases 11–18: governance docs + scorecards.
9. Phase 19: iterate on the weakest category until ≥ 9/10.