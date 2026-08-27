# MODEL_CARD.md — CashGuard AI Risk Model (Phase 13)

| Field | Value |
|---|---|
| Model version | `trained_at` timestamp in `artifacts/metrics.json` + alert `model_version` field |
| Model type | XGBoost binary classifier + Platt calibration (active = xgboost; ensemble disclosed, not active) |
| Feature set version | `FEATURE_COLUMNS` in `backend/ml/features.py` (24 features) |
| Training data | Controlled synthetic generator (`backend/data/synthetic_data.py`, config in `calibration_config.yaml`, citations in `CALIBRATION_NOTES.md`) |
| Evaluation split | Chronological train → validation → test (early stopping + calibration on validation ONLY) |

## Intended use
- District/state-level **advisory** forecasting of ATMs at elevated risk of
  fraud cash-out in the next 24h; decision *support* for police and bank
  review workflows (HOLD ACTION on weak evidence).

## Prohibited use
- Automated enforcement, automated freezing, or any action affecting a citizen
  without human decision and audit.
- Use of the scores as evidence of guilt (scores are probabilistic and
  synthetic-label-evaluated).
- Deploying to real operations before a pilot with investigation-confirmed
  outcomes replaces the synthetic evaluation.

## Evaluation methodology (CONTROLLED SYNTHETIC EVALUATION — not real-world accuracy)
- ROC-AUC 0.9366 · Precision@20/50/100/1000 = 1.0/1.0/1.0/0.8 · threshold(≥0.7) 0.8116
- Median lead time 13.5 h (IQR 8.1–19.9) — horizon-dependent
- Lift vs volume 1.111–2.041× · lift vs proximity >=50 (baseline ~0.00-0.02)×
- Calibration: Brier + ECE 0.0158 (10 bins) + reliability curve
- Deep-eval suite: ablation, cold-location, 8 adversarial worlds,
  counterfactual, horizons 6/12/24/48h (`artifacts/deep_eval/`, `deep_evaluation.json`)
- Robustness: ±30% perturbation stable (`artifacts/robustness_check.json`)

## Known failure modes
- Sparse data (adversarial world: AUC 0.81 — lowest).
- Complaints alone carry almost no signal (ablation A AUC 0.49) — the model
  depends on withdrawal/mule-behavioural signals; a real pilot must confirm
  those are available with comparable latency.
- Near-threshold scores are the weakest-evidence band → HOLD ACTION label.
- Stale data degrades trust → alerts carry `data_freshness_hours`.

## Fairness considerations
- Zero demographic features (anti-profiling). Geographic concentration monitor
  (`artifacts/fairness_report.json`) for ops review.
- Counterfactual sensitivity: complaint surge +50% moves mean risk by +0.0096 —
  directional but modest; mule behaviour dominates.

## Human oversight
- Every decision (acknowledge / monitor / dismiss / escalate / more-data /
  actioned) requires a human; dismiss and escalate require a recorded reason;
  all decisions are ledger-audited. No auto-retraining on small samples.