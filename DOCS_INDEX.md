# DOCS_INDEX.md — Where to Look (30-Second Map)

## Start here (judge reading path)
- **README.md** — overview, architecture, quickstart (`python run.py`)
- **ONE_SLIDE_EXECUTIVE_SUMMARY.md** — 20-second summary of the project
- **JUDGE_BRIEF.md** — 2-page judge brief (problem → solution → evidence)
- **DEMO_SCRIPT.md** — click-by-click demo walkthrough + DEMO_MODE fallback plan
- **docs/DEMO_CREDENTIALS.md** — synthetic demo logins (**NOT FOR PRODUCTION**)

## Read before quoting any metric or claim
- **LIMITATIONS.md** — evaluation ceiling, jurisdiction limits, explainability method
- **CALIBRATION_NOTES.md** — every data-generation parameter, source-tagged and cited
- **MODEL_CARD.md** — model facts, and why precision@K isn't artificially perfect
- **VERIFICATION_LOG.md** — dated, real test results for every demo feature
- **REAL_DATA_VALIDATION_PROTOCOL.md** — the 14-step path from authorized data to validated operation (synthetic demo vs real-data pilot vs production)
- **REAL_DATA_READINESS.md** — exact data contract + onboarding timeline + what changes in the ML pipeline

## Evidence (every cited number traces here)
- **artifacts/metrics.json** — training metrics, baselines, lead time, per-feature AUC
- **artifacts/deep_evaluation.json** + **artifacts/deep_eval/** — deep-eval suite (horizons, drift, fairness, simulation, baseline war, permutation tests, generalization splits, transfer readiness, ledger replication) — regenerate with `python scripts/` (each script is one command)
- **BLOCKCHAIN_JUSTIFICATION.md** — honest account: tamper-evident chain + 3-node replication (real) vs testnet anchoring (integration point, not exercised)

## Deeper technical detail (reference only, not required reading)
- **FAIRNESS_AUDIT.md** — group false-positive rates (15 groups, flat 0.0015–0.0062) + feedback-loop audit
- **FAIRNESS_ONE_SLIDER.md** — pitch-ready fairness summary + dashboard-output chart
- **MODEL_DRIFT.md** — 12 adversarial worlds: AUC stable, threshold precision varies honestly
- **LOAD_TEST.md** — 8,000-complaints/day benchmark + the inference cache (8 users in 5.5s)
- **OPERATIONAL_IMPACT.md** — intervention simulation + alert-fatigue dedup rule + tiered triage
- **JURISDICTION_ROUTING.md** — inter-agency cross-state handoff queue (Item 4; mechanism tested, activates when cross-state data arrives)
- **INTERVENTION_VALUE_EVALUATION.md** — random vs volume vs historical vs CashGuard (11–14× at K=10)
- **INTERVENTION_PRIORITY.md** — the priority score + the formal ACT/REVIEW/HOLD policy
- **MODEL_OUTCOME_MONITOR.md** — closed-loop outcome evaluation + runtime drift monitors
- **PREDICTIVE_FEEDBACK_LOOP.md** — why the architecture cannot create a self-reinforcing policing loop
- **LABEL_VALIDITY.md** — the label contract: what it is, who made it, why it cannot leak
- **PRIVACY_MODEL.md** — tokenization, data minimization, DPDP posture
- **DPDP_ACT_COMPLIANCE.md** — DPDP Act mapping: minimization, purpose, retention, consent basis
- **PRODUCTION_DATA_INTEGRATION.md** — IMPLEMENTED/SIMULATED/PLANNED architecture matrix
- **REAL_DATA_ONBOARDING.md** — 30-day shadow-mode pilot plan
- **NOVELTY.md** — what is (and is not) claimed as novel
- **DEMO_VIDEO.md** — 3–5 min demo video shot list + submission links
- **docs/audits/** — internal audits, kill tests, and Q&A prep (not required reading):
  FINAL_JUDGE_AUDIT, FINAL_EXTERNAL_JUDGE_AUDIT, FINAL_KILL_TEST_AUDIT,
  GENERATOR_LEAKAGE_AUDIT, SECURITY_AUDIT, FINAL_SECURITY_AUDIT, AUDIT_REPORT,
  REPO_HYGIENE_NOTE, Q&A_PREPARATION (75 questions)