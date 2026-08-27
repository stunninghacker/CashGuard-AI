# Q&A_PREPARATION.md — 40 Hostile Questions, Answered (Team Prep)

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
   strict; horizon evaluation (2/6/12/24/48h); lead time 14.9h median.
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