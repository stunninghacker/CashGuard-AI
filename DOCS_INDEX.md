# DOCS_INDEX.md — Where to Look (30-Second Map)

## Start here
- **README.md** — overview, architecture, quickstart (`python run.py`)
- **DEMO_SCRIPT.md** — click-by-click demo walkthrough + DEMO_MODE fallback plan

## Read before quoting any metric or claim
- **LIMITATIONS.md** — evaluation ceiling, jurisdiction limits, explainability method
- **CALIBRATION_NOTES.md** — every data-generation parameter, source-tagged and cited
- **MODEL_CARD.md** — model facts, and why precision@K isn't artificially perfect
- **VERIFICATION_LOG.md** — dated, real test results for every demo feature

## Deeper technical detail (reference only, not required reading)
- **SECURITY_AUDIT.md** — auth/RBAC/WS/rate-limit control checks, tested live
- **FAIRNESS_AUDIT.md** — group false-positive rates (flat across jurisdictions) + feedback-loop audit
- **MODEL_DRIFT.md** — 11 adversarial worlds: AUC stable, threshold precision varies honestly
- **LOAD_TEST.md** — 8,000-complaints/day benchmark, incl. the measured SQLite concurrency limit
- **OPERATIONAL_IMPACT.md** — intervention simulation (top-K capture) + alert-fatigue dedup rule
- **PRIVACY_MODEL.md** — tokenization, data minimization, DPDP posture
- **PRODUCTION_DATA_INTEGRATION.md** — NCRP/CFCFRMS/bank-swap integration points
- **REAL_DATA_ONBOARDING.md** — 30-day shadow-mode pilot plan
- **NOVELTY.md** — what is (and is not) claimed as novel
- **INTERVENTION_PRIORITY.md** — the priority score behind the dashboard column
- **AUDIT_REPORT.md** — baseline engineering audit (checklist, not a score)

## Evidence (every cited number traces here)
- **artifacts/metrics.json** — training metrics, baselines, lead time, per-feature AUC
- **artifacts/deep_evaluation.json** + **artifacts/deep_eval/** — deep-eval suite (horizons, drift, fairness, simulation, feature audit) — regenerate with `python scripts/` (each script is one command)
- **REPO_HYGIENE_NOTE.md** — confirmation that git history contains no internal-process artifacts