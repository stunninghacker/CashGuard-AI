# DOCS_INDEX.md — Where to Look (30-Second Map)

## Start here
- **README.md** — overview, architecture, quickstart (`python run.py`)
- **DEMO_SCRIPT.md** — click-by-click demo walkthrough + DEMO_MODE fallback plan

## Read before quoting any metric or claim
- **LIMITATIONS.md** — evaluation ceiling, jurisdiction limits, explainability method
- **CALIBRATION_NOTES.md** — every data-generation parameter, source-tagged and cited
- **MODEL_CARD.md** — model facts, and why precision@K isn't artificially perfect
- **VERIFICATION_LOG.md** — dated, real test results for every demo feature
- **REAL_DATA_VALIDATION_PROTOCOL.md** — the 14-step path from authorized data to validated operation (synthetic demo vs real-data pilot vs production)

## Deeper technical detail (reference only, not required reading)
- **SECURITY_AUDIT.md** — auth/RBAC/WS/rate-limit control checks, tested live
- **FINAL_SECURITY_AUDIT.md** — full control inventory (auth, CORS, WS, PII, model, mock endpoints)
- **PREDICTIVE_FEEDBACK_LOOP.md** — why the architecture cannot create a self-reinforcing policing loop
- **GENERATOR_LEAKAGE_AUDIT.md** — feature-target correlations, seed stability, parameter sensitivity
- **FAIRNESS_AUDIT.md** — group false-positive rates (flat across 12 groups) + feedback-loop audit
- **MODEL_DRIFT.md** — 12 adversarial worlds: AUC stable, threshold precision varies honestly
- **LOAD_TEST.md** — 8,000-complaints/day benchmark, incl. the measured SQLite concurrency limit
- **INTERVENTION_VALUE_EVALUATION.md** — random vs volume vs CashGuard intervention comparison (11–14× at K=10)
- **OPERATIONAL_IMPACT.md** — intervention simulation (top-K capture, false interventions, missed events) + alert-fatigue dedup rule
- **MODEL_OUTCOME_MONITOR.md** — closed-loop outcome evaluation + runtime drift monitors
- **PRIVACY_MODEL.md** — tokenization, data minimization, DPDP posture
- **PRODUCTION_DATA_INTEGRATION.md** — NCRP/CFCFRMS/bank-swap integration points
- **REAL_DATA_ONBOARDING.md** — 30-day shadow-mode pilot plan
- **NOVELTY.md** — what is (and is not) claimed as novel
- **INTERVENTION_PRIORITY.md** — the priority score behind the dashboard column
- **AUDIT_REPORT.md** — baseline engineering audit (checklist, not a score)
- **FINAL_JUDGE_AUDIT.md** — hostile re-audit: 17 category scores + residual blockers
- **FINAL_EXTERNAL_JUDGE_AUDIT.md** — fresh red-team pass: baseline war, IDOR fix, missing-model kill test
- **JUDGE_BRIEF.md** — 2-page judge brief · **ONE_SLIDE_EXECUTIVE_SUMMARY.md** — 20-second summary — hostile re-audit: 17 category scores + residual blockers
- **Q&A_PREPARATION.md** — 40 hostile questions answered (team prep)

## Evidence (every cited number traces here)
- **artifacts/metrics.json** — training metrics, baselines, lead time, per-feature AUC
- **artifacts/deep_evaluation.json** + **artifacts/deep_eval/** — deep-eval suite (horizons, drift, fairness, simulation, feature audit) — regenerate with `python scripts/` (each script is one command)
- **REPO_HYGIENE_NOTE.md** — confirmation that git history contains no internal-process artifacts