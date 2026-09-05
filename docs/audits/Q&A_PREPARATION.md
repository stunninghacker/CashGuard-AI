# Q&A_PREPARATION.md — 40 Hostile Questions, Answered (Team Prep)


> **WARNING: DATA-LEAKAGE CORRECTION (2026-08-29)** - This document's reported ROC-AUC figures (~0.92x) came from a SAME-DAY LABEL-LEAKAGE bug in feature engineering (backend/ml/features.py, `_shift_day_past`), now fixed. The honest forecast-safe ROC-AUC is **0.6456** (leaky 0.9275 -> corrected 0.6344 in the proof). On calm days the live model scores every ATM low (max ~0.11) and produces **no alerts**; any populated high-risk alert view is the opt-in, clearly-labelled **"Load Simulated Scenario"** mode (SCRIPTED, not live model output). Treat all 0.92x figures in this doc as superseded. Full detail: MODEL_CARD.md, VERIFICATION_LOG.md (P1.5).
Format per question: **Answer** / Evidence / Limitation / What NOT to claim.
All numbers are artifact-backed (synthetic evaluation unless stated).

## DATA
1. **Where is the real data?** — None; all synthetic by design (access-controlled).
   Evidence: CALIBRATION_NOTES.md + REAL_DATA_VALIDATION_PROTOCOL.md (14-step path).
   NOT claimed: access, partnership.
2. **Why synthetic?** — NCRP/bank data is access-controlled; a calibration-honest
   generator + a runnable real-data harness is the honest alternative.
   Limitation: synthetic ≠ real. NOT claimed: realism.
3. **How do you know synthetic patterns are realistic?** — Every generator parameter
   is source-tagged (verified pattern vs assumption) + cited; directional sources:
   I4C Suspect Registry clustering, IBA mule behaviour, RBI time-delay direction.
   Limitation: no India-specific public statistics for exact coefficients.
4. **What happens when real data differs?** — The protocol handles it: schema
   validation, PSI drift monitors, shadow mode, recalibration, rollback.

## ML
5. **Why XGBoost?** — Tabular spatio-temporal task; fast, early stopping, native
   TreeSHAP; the student-feasible, explainable choice. Baselines disclosed.
6. **Why not deep learning?** — No evidence of benefit at this scale; explainability
   and reproducibility cost. NOT claimed: DL would be worse everywhere.
7. **What is the target?** — P(fraud withdrawal at ATM in next 24h), daily granularity,
   per-ATM rows, chronological split (2026-07-03).
8. **How do you prevent leakage?** — Feature windows end before the forecast point;
   the leak feature was removed and grep-verified; per-feature AUC audit; early
   stopping/calibration on validation only.
9. **How do you validate temporal generalization?** — Chronological 70/30 split,
   strict; horizon evaluation (2/6/12/24/48h); lead time 12.8h median.
10. **How do you validate new locations?** — Cold-location eval: held-out city AUC
    0.9244; features are behavioural, not memorization.
11. **What happens at 2h?** — P@1000 0.04 → INSUFFICIENT CONFIDENCE, HOLD ACTION,
    shown in the UI. Not hidden.
12. **What happens at 6h?** — P@1000 0.082 → INSUFFICIENT CONFIDENCE, HOLD.
13. **What happens at 24h?** — P@1000 0.528, MEDIUM confidence; the operational band.
14. **What happens under drift?** — 12 worlds, AUC ≥ 0.86 everywhere; threshold
    precision varies (0.55–0.83) → REDUCED confidence surfaced, never silent.

## OPERATIONS
15. **Why should police trust the result?** — It is decision support: evidence panel,
    uncertainty, HOLD bands, source tags, audit chain. Trust is earned via the pilot.
16. **What does an officer do with the alert?** — Graded response playbook (notify →
    monitor → CCTV/pre-position → verify); human decision required; ledger-logged.
17. **What if the prediction is wrong?** — 38% false-alert rate is disclosed; dismiss
    with reason; outcomes store FP/FN; model is not an autonomous trigger.
18. **What if evidence is weak?** — HOLD ACTION (evidence strength < 3/5, or risk in
    the 0.70–0.78 band).
19. **What if two models disagree?** — |A−B| > 0.20 downgrades confidence; > 0.35
    HOLD (Model B = logistic baseline, AUC 0.876 vs 0.931).
20. **How is intervention prioritized?** — Risk × exposure × urgency × evidence ×
    confidence (INTERVENTION_PRIORITY.md); the simulation shows top-10/day captures
    ~5.5% of exposure vs 0 baseline.

## FAIRNESS
21. **Could this create predictive-policing feedback loops?** — The model never
    consumes interventions/outcomes as features; concentration monitor + ops review.
22. **How do you avoid repeatedly targeting the same area?** — Gini monitor,
    repeated-targeting review trigger, no auto-action.
23. **How do you audit geographic bias?** — Group audit across jurisdictions,
    complaint-areas, and ATM-volume groups: FPR flat 0.002–0.005.
24. **Can the system say HOLD ACTION?** — Yes — stale data, high uncertainty, high
    disagreement, weak evidence, short-horizon inadequacy (the HOLD-engine cases).

## SECURITY
25. **How is PII protected?** — Salted tokens; vault with role-scoped re-identification;
    DPDP-aligned minimization (PRIVACY_MODEL.md).
26. **Who can see complaints?** — POLICE_STATE/POLICE_DISTRICT (own jurisdiction),
    I4C (national); banks do not see complaints.
27. **Who can see bank data?** — The owning bank + police + I4C; role-scoped row-level.
28. **How are APIs protected?** — JWT (30min/24h), role dependencies on every route,
    rate limits, tightened CORS; 401/403 verified live (FINAL_SECURITY_AUDIT.md).
29. **How are audit logs protected?** — Tamper-evident SHA-256 chain; verify endpoint;
    tamper demo proves detection (True → False → restore → True, verified live).

## DEPLOYMENT
30. **How does NCRP integrate?** — Repository-layer ETL swap; schema-compatible;
    PRODUCTION_DATA_INTEGRATION.md + REAL_DATA_ONBOARDING.md.
31. **How does CFCFRMS integrate?** — Fund-block queue + webhook path (mock inbox
    receives real HTTP POSTs); real API is the Tier-2 integration point.
32. **How do banks integrate?** — Withdrawal/ATM feeds to the same schema; bank-scoped
    dashboards; webhook outbound.
33. **How does this scale to 8,000 complaints/day?** — Measured: ingestion 22–38ms
    per batch at the real rate; burst <5ms/record; inference 2.7–3.0s for 900 ATMs
    (LOAD_TEST.md).
34. **What is p95 latency?** — Ingestion p95 36ms; per-record burst p95 1.0ms;
    inference p95 2.98s; concurrent-user p95 71.9s on SQLite (documented weakness →
    PostgreSQL is the production path).
35. **What if a bank does not provide data?** — Features degrade gracefully per ATM;
    freshness flags; HOLD on stale.

## NOVELTY
36. **Isn't this just ML hotspot prediction?** — The loop is the novelty: prediction →
    evidence → graded response → recovery funnel → tamper-evident audit chain, with
    uncertainty/HOLD/disagreement throughout. NOVELTY.md is explicit about what is
    not claimed.
37. **What exactly is innovative?** — Evidence-first, uncertainty-aware, human-gated,
    audit-provable closed loop with adversarial evaluation; Hawkes temporal intensity
    (disclosed as weak alone, AUC 0.51).
38. **Why not use an existing fraud platform?** — Existing platforms are reactive
    transaction fraud detection; the SIH26184 ask is proactive location forecasting
    for deployment — a different decision surface.

## BLOCKCHAIN
39. **Where is the blockchain?** — There is no blockchain. There is an append-only
    SHA-256 tamper-evident audit chain (precise term), verified live via the tamper
    demo; permissioned ledger anchoring is the documented Tier-2 upgrade.
40. **Why do you need it?** — Chain-of-custody for court-facing inter-agency
    decisions: every alert, decision, and report is attributable and tamper-evident.

## RED-TEAM ADDITIONS (41–50)

41. **How do you know you beat a simple 'busiest ATM' rule?** — Measured on the
    identical split (baseline_war.json): AUC 0.6456 vs 0.56; P@100 0.67 vs 0.03;
    intervention capture at K=10 is 5.5% vs 0.5% (11×). NOT claimed: beat every
    conceivable heuristic.
42. **What is the intervention cost?** — False interventions are counted and
    reported per K (242 at K=10), plus ₹/intervention efficiency (₹41k) —
    the priority score trades K against cost. No real costs claimed (synthetic).
43. **What if a competitor has real bank data?** — They would win the data
    dimension; we win the governance dimension (evidence/uncertainty/audit/
    pilot protocol). The gap is external and explicit. NOT claimed: parity on
    data.
44. **Why not train on NPCI/UPI data?** — No authorized access; NPCI feeds are
    an integration point (PRODUCTION_DATA_INTEGRATION.md), not a claim.
45. **Can the cache serve stale scores?** — Fixed: TTL + single-flight + data
    stamp on the split cache; invalidation verified live (drip → recompute →
    payload changes). Verified byte-identical on cache hits.
46. **What if the model file is missing on stage?** — Kill-tested: DEMO_MODE
    serves everything from cache with no model loaded (risk-scores/alerts/
    evidence/horizons/stats — all 200). Restore = copy model back.
47. **What did the red team actually break?** — An IDOR on single-alert reads
    (fixed + retested) and a stale split cache (fixed with data stamps) —
    both documented in FINAL_EXTERNAL_JUDGE_AUDIT.md with retest evidence.
48. **Does the pilot risk creating a policing loop?** — Architecture cannot
    close the loop (interventions never features, no auto-retraining);
    repeat-targeting monitor + randomized review sample (PREDICTIVE_FEEDBACK_LOOP.md).
49. **Why should MHA adopt rather than build in-house?** — The framework is
    the spec: protocol, shadow mode, HOLD policy, audit chain, monitored
    rollback — an adoption-ready contract, not a black box.
50. **What is the single most honest weakness?** — No authorized real data has
    been evaluated; everything above is synthetic-label measurement. That is
    why the pilot protocol exists and why no real-world number is claimed.


## FINAL KILL-TEST ADDITIONS (51–75)

51. **Could the model be memorizing generator assumptions?** — Permutation tests (permutation_tests.json): label shuffle collapses AUC to 0.475 (chance); features contain NO ATM/city/district identity columns; row-order shuffle leaves AUC identical. The model cannot be memorizing identities.
52. **Could it be learning reporting behaviour, not fraud?** — Complaints-only ablation AUC 0.50; city-feature permutation changes AUC by <0.001; the decisive features are withdrawal-side mule signals (LABEL_VALIDITY.md).
53. **What is your label, who made it, can it leak?** — Generator-set `is_fraud_withdrawal` at creation; label-only in the feature module (grep-verified); windows end before the forecast point (LABEL_VALIDITY.md).
54. **Do you generalize to new ATMs?** — Cold-ATM split AUC 0.918 (behavioural features transfer); cold-city 0.924. Honest ceiling: new-high-volume ATMs are the weak split (AUC 0.76, ECE 0.13) — reported, not hidden (generalization_splits.json).
55. **Why is historical hotspot not enough?** — Measured: historical-hotspot AUC 0.685 / P@100 0.25 vs CashGuard 0.926 / 0.86; at K=10 CashGuard captures 2.9× more exposure than historical targeting (baseline_war.json).
56. **Why does the model beat logistic regression?** — Logistic AUC 0.49 vs XGBoost 0.926: the decision surface needs nonlinear interactions of behavioural signals; disclosed, not assumed.
57. **What do the ablation variants show?** — XGB without spatial features 0.9272; without complaint features 0.9276 — the value is in withdrawal/mule behaviour; complaints and geometry are secondary (baseline_war.json).
58. **How did you test for temporal leakage?** — Chronological splits in train/eval; the split cache is data-stamped; permutation of day-of-week changes AUC by <0.002.
59. **What happens at 72h?** — P@1000 0.608, MEDIUM — precision rises but recall decays (event rate is lower per day); shown in horizons.json, not hidden.
60. **What is the ECE at 24h?** — 0.0156 (main split); reported per split in generalization_splits.json (worst case: new-hotspot 0.128 — surfaced).
61. **Can one district see another district's report?** — Fixed and regression-tested: situational reports are I4C-only; hotspot reports scoped by jurisdiction; foreign → 404, own → 200 (test_security_regression.py).
62. **Can a forged token escalate role?** — Regression test: bank-signed I4C claim → 403 on /train and /stats (fail-safe, not trust-the-claim).
63. **What happens if the model file is corrupted?** — Clean EOFError on load (no silent wrong predictions); DEMO_MODE serves everything from cache; restore = copy back (failure-engineering pass).
64. **What happens if the database is unavailable?** — SQLite is the demo store; a DB outage surfaces as clean 500s, never fabricated data; DEMO_MODE serves the golden path without the DB for read-only flows. PostgreSQL failover is a production requirement (PLANNED, not claimed).
65. **Can attackers game the demo-mode?** — DEMO_MODE is a read-only cache path with auth still enforced (regression-tested); it is not a privilege-escalation route.
66. **What if attackers deliberately avoid flagged ATMs?** — World-tested: risk_avoidance world (hot use 15%) AUC 0.930, no collapse; REDUCED confidence flagged honestly (drift.json).
67. **What if fraud migrates to new cities?** — Cold-city split AUC 0.924; new-city coverage is behavioural (no identity features); the pilot re-validates.
68. **Who makes the final decision?** — Always a human: ACT/REVIEW/HOLD policy (INTERVENTION_PRIORITY.md); no autonomous action exists; dismiss/escalate require reasons.
69. **Can the AI order police action?** — No. Recommendation language is review-oriented; the strongest output is a recommendation + evidence for a human.
70. **What is your false-positive cost?** — Disclosed: 38% at the 0.7 threshold; dedup + HOLD bands reduce noise; false interventions are counted per K in the intervention evaluation (242/day at K=10).
71. **How do you protect PII?** — Tokens everywhere, vault-gated re-identification, DPDP-aligned minimization, no demographic features; role-scoped access verified at API level.
72. **What is genuinely novel?** — The closed evidence-driven loop with honest uncertainty and audit, adversarial validation, and a mechanical real-data path — not the ML components (NOVELTY.md says exactly this).
73. **Why should SIH choose you over a bank's internal fraud team?** — Different decision surface (proactive location forecasting vs reactive transaction scoring), plus an adoption-ready contract: protocol, shadow mode, HOLD policy, monitored rollback.
74. **What is your weakest result?** — New-hotspot generalization (AUC 0.76, ECE 0.128) and short horizons (2h P@1000 0.04) — both published with the HOLD policy they drive.
75. **What did your own red team break?** — An IDOR on single-alert reads and report scoping (both fixed + regression-tested), a stale split cache (data-stamped), DEMO_MODE stats needing the model (cache-backed), and a mislabeled-SHAP documentation bug — all recorded in FINAL_EXTERNAL_JUDGE_AUDIT.md / FINAL_KILL_TEST_AUDIT.md.
