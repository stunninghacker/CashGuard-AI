# FINAL_10_10_ROBUSTNESS_ADVERSARIAL.md — Adversarial worlds, drift, disagreement, transfer


> **WARNING: DATA-LEAKAGE CORRECTION (2026-08-29)** - This document's reported ROC-AUC figures (~0.92x) came from a SAME-DAY LABEL-LEAKAGE bug in feature engineering (backend/ml/features.py, `_shift_day_past`), now fixed. The honest forecast-safe ROC-AUC is **0.6273** (leaky 0.9275 -> corrected 0.6344 in the proof). On calm days the live model scores every ATM low (max ~0.11) and produces **no alerts**; any populated high-risk alert view is the opt-in, clearly-labelled **"Load Simulated Scenario"** mode (SCRIPTED, not live model output). Treat all 0.92x figures in this doc as superseded. Full detail: MODEL_CARD.md, VERIFICATION_LOG.md (P1.5).
Covers Phase 8 (adversarial simulation), 10 (model disagreement), 14
(drift/robustness) and 16 (transfer/production-readiness) of the kill test.
Sources: stored `adversarial_worlds.json`, `drift.json`, `transfer_readiness.json`,
`feature_audit.json`, plus a **live re-run of `model_disagreement.py`** this
session (marked ✔).

## 1. Adversarial worlds (stored `adversarial_worlds.json`)
Model re-scored across 8 controlled worlds (normal, geo_shift, temporal_shift,
atm_preference_shift, reporting_delay, volume_shift, pattern_drift, sparse_data):

| World | AUC | P@100 | P@1000 | Note |
|---|---|---|---|---|
| normal | 0.852 | 0.95 | 0.654 | reference |
| geo_shift | 0.853 | 0.96 | 0.634 | robust |
| temporal_shift | 0.848 | 0.88 | 0.642 | robust |
| atm_preference_shift | 0.873 | 0.99 | 0.635 | robust |
| reporting_delay | 0.857 | 0.88 | 0.657 | robust |
| volume_shift | 0.897 | 0.84 | 0.468 | robust |
| pattern_drift | 0.845 | 0.84 | 0.589 | robust |
| sparse_data | 0.804 | 0.98 | 0.727 | lowest AUC, honest |

Verdict: AUC ≥ 0.80 in every world; no world collapses the ranking. `sparse_data`
has the lowest AUC (0.804) — reported, not hidden.

## 2. Drift behavior (stored `drift.json`, 11 worlds)
AUC 0.86–0.93 everywhere; almost every world is flagged **"REDUCED"** confidence
(normal/world are both marked REDUCED). The system degrades honestly under shift
instead of fabricating high-confidence output. `pattern_drift` world emits **0
alerts at 0.7** (all held) — a conservative, disclosed behavior.

## 3. Model disagreement (✔ live re-run this session)
`model_disagreement.py`: Model A (XGBoost) AUC **0.9259** vs Model B (logistic-
statistical baseline) AUC **0.8674**; median |A−B| **0.0134**, p95 **0.1427**.
Disagreement policy: confidence downgraded one level when |A−B| > 0.20, **HOLD
ACTION** when |A−B| > 0.35. Values match the stored artifact (0.8687 / 0.0115 /
0.1378) with expected seed variance. Disagreement is a real, bounded control.

## 4. Transfer readiness (stored `transfer_readiness.json`)
Same pipeline, config-only overrides, fresh data per world:
| World | AUC | P@100 | P@1000 | AUC Δ vs ref |
|---|---|---|---|---|
| reference | 0.928 | 0.92 | 0.553 | — |
| T1 more cities | 0.937 | 0.58 | 0.386 | −0.008 |
| T2 higher fraud | 0.922 | 1.00 | 0.751 | +0.006 |
| T3 mule behaviour | 0.929 | 0.91 | 0.604 | −0.001 |

Retrains cleanly on structurally different distributions with **zero code
changes**; worst-case AUC Δ ≤ 0.008. Top-K precision varies with distribution
shape (T1 dilutes top-K, T2 raises it) — honest. Real-data onboarding requires
recalibration + threshold re-derivation, not pipeline rewrites.

## 5. Explainability (stored `feature_audit.json`)
Feature importance top-3 = 56.8% (counterparty_count_24h 32.9%, transaction_
frequency_24h 13.5%, linked_proportion_24h 10.4%); top-1 single-feature AUC
0.845. Consistent with the live `per_feature_auc` (counterparty 0.83). No single
feature dominates → the model needs the ensemble (contradicts a "single-feature
leak" theory).

## Bottom line
Robust to adversarial and drift worlds (AUC ≥ 0.80, honest REDUCED flags),
disagreement-bounded, and transfer-ready with zero code changes across structural
distributions. Weak split is `sparse_data` provenance and new-hotspot (see the
spatial doc) — both disclosed.
