# AUDIT_REPORT.md — Baseline Engineering Audit

**Method**: full-repo inspection; every claim grounded in code or artifact.
**Legend**: ✅ present · ⚠️ partial/needs work · ❌ missing (at the time of this
baseline audit; all ❌ items below were subsequently implemented and are artifact-backed).

## A. ML validity

| Check | Status |
|---|---|
| Target leakage (fraud_withdrawals_24h) | ✅ removed; `is_fraud_withdrawal` is label-only (grep-verified) |
| Temporal leakage (train/val/test) | ✅ chronological; early stopping + calibration use VALIDATION only |
| Class imbalance | ✅ handled (scale_pos_weight) + documented |
| Suspiciously powerful features | ✅ per-feature AUC reported; max 0.8447 (complaint-linked, prediction-time-safe); post-de-separation feature audit: top-1 importance 32.9% (`artifacts/deep_eval/feature_audit.json`) |
| Calibration | ✅ Platt + calibration curve + Brier 0.0472 (`artifacts/metrics.json`) |
| Metric inflation | ✅ PR-AUC, false-alert rate, alert volume, capture rate now reported (`artifacts/deep_eval/operational.json`) |
| Cold-location generalization | ✅ held-out-city evaluation: AUC 0.9237 (`cold_location.json`) |
| Ablation (feature-family value) | ✅ ablation study: financial features carry the signal (`ablation.json`) |
| Adversarial/perturbed worlds | ✅ 8 scenario worlds + 11 drift worlds (`adversarial_worlds.json`, `drift.json`) |
| Counterfactual sensitivity | ✅ complaint-surge counterfactual + per-alert WHAT-IF (`counterfactual.json`) |
| Horizon analysis | ✅ 2/6/12/24/48h with confidence bands (`horizons.json`) |
| Robustness to perturbation | ✅ ±30% grid (AUC 0.923–0.932 stable) |

## B. Architecture

- ✅ bcrypt + JWT (access/refresh); RBAC with row-level scoping in the repository layer;
  access audit on the ledger; SQLAlchemy abstraction (SQLite→PostgreSQL one-line); repository
  layer as the single data door; Dockerfile; env-driven config with `.env.example`; smoke test;
  DEMO_MODE cache.
- ✅ CORS default tightened to localhost origins.
- ✅ Rate limiting on auth/data endpoints.
- ✅ Model version carried on alerts; uncertainty metadata exposed.
- ⚠️ Auth secret default is a dev placeholder (fine for demo; must be env-forced in prod).

## C. Product

- ✅ Evidence panel (3 fields + source disclosure + feature contributions + freeze intel),
  graded response playbook, PDF reports, recovery queue + funnel, alert workflow.
- ✅ Dismiss/escalate with mandatory reason; HOLD ACTION for weak evidence; uncertainty +
  data-freshness on forecasts; evidence graph; emerging vs historical risk separation;
  closed-loop outcome tracking (predicted vs actual vs UNKNOWN).
- ✅ Intervention priority + multi-horizon confidence in the dashboard.

## D. Ethics & security

- ✅ Zero demographic features (anti-profiling); advisory-only banner; human-decision
  requirement; group fairness audit (FPR flat 0.001–0.003 across jurisdictions); ledger
  auditability; DPDP posture documented.
- ✅ Recommendation language is review-oriented ("Review recommended"), not auto-deploy.

## Known residual items (documented elsewhere, not blockers for the demo)

- SQLite concurrency is a measured demo-scale limit (see `LOAD_TEST.md`); PostgreSQL is the
  stated production path.
- Real-data validation is an external dependency (see `REAL_DATA_ONBOARDING.md` — 30-day
  shadow-mode pilot plan).
