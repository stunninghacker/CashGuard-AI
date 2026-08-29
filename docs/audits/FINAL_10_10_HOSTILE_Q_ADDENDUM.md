# FINAL_10_10_HOSTILE_Q_ADDENDUM.md — Hostile questions 76–100

Extends `Q&A_PREPARATION.md` (Q1–Q75) to a full 100. Each is answered with
evidence artifact + what NOT to claim. Items marked (✔) reflect findings
fresh-verified in the 2026-08-29 kill-test session.

## 76. **Your metrics.json once had a 9-digit lift number (9×10⁸). What was that?**
   It was a division-by-zero artifact: lift = active_prec / max(baseline, 1e-9);
   when the volume baseline caught zero positives at K=20 it produced 9e8.
   Fixed to report `null` (lift is undefined when baseline=0) and metrics
   regenerated (now 18–40×). ✔ This is precisely the class of failed artifact
   we audit for and now purge. NOT claimed: lift was intended to be 9e8.

## 77. **Your single best feature is counterparty_count_24h at AUC ~0.83. Is that reactive, not proactive?**
   Yes. It counts complaint-linked mule accounts already withdrawing at the ATM
   in the prior 24h. It is prediction-time safe but closer to early detection of
   ongoing mule cash-out than forecasting a future hotspot from complaints.
   Honest limitation documented (GENERATOR_LEAKAGE + SCORECARD). NOT claimed:
   fully proactive-from-complaints prediction.

## 78. **So is the whole model just "watch the busy mule ATM"?**
   No — it combines ~24 behavioural signals, beats busy-ATM (volume), proximity,
   complaint, logistic and hawkes baselines, and the top-3 features are only 57%
   of importance (no single feature dominates). But the mule feature is the
   largest contributor and the reactive critique stands. ✔

## 79. **Why do complaints barely move the prediction?**
   Measured: complaint-only ablation AUC 0.50 (≈ chance); city-feature
   permutation Δ < 0.001; complaints-only single-feature AUC ≤ 0.55. The
   generator's complaints are weakly coupled to the cash-out label in the way
   the model uses them. NOT claimed: complaints are the driver — they are not.

## 80. **If complaints don't matter, why did you build the system around them?**
   The SIH-26184 brief asks for complaint-driven proactive forecasting; we built
   the full complaint pipeline (ingestion, evidence, jurisdiction, CRF funnel),
   then **honestly measured** that the ML signal lives on the withdrawal side.
   That is the finding, not a hidden bug — documented to the judge explicitly.

## 81. **Your new-hotspot precision is ~0.3, not 0.8. Doesn't that defeat the purpose?**
   It is the honest weak split: when the previously top-20%-by-volume ATMs are
   withheld, P@100 drops (0.06–0.34 across runs) and ECE degrades. We report it,
   do not average it away, and the HOLD policy limits harm. Improving novel-
   hotspot detection is an open problem, not a claim. ✔

## 82. **What is your generator-seed variance?** (✔)
   Model seeds (same data): AUC stable to 0.0006 spread, P@100 0.84–0.86.
   Generator seeds (fresh draws): AUC 0.918–0.927 (stable), but **top-100
   precision 0.50–0.67** — draw-sensitive. We quote ranges, never the fixed-seed
   peak.

## 83. **What happens at 2h / 6h / 12h lead?**
   2h PR-AUC 0.04, 6h 0.08, 12h 0.16, 24h 0.41. Short horizons are labelled
   INSUFFICIENT CONFIDENCE → HOLD ACTION. Only 24h is operational. NOT claimed:
   minutes-to-hours early warning.

## 84. **Why is 24h your only real horizon?**
   Event rate at short horizons is tiny (2h: 0.003) so precision collapses; at
   >24h ranking quality decays (48h AUC 0.735, 72h 0.661). The honest band is
   ~24h with ~15h median lead time (a horizon design-property, not an accuracy
   claim).

## 85. **Your load test uses SQLite. Is that production-grade?**
   No — it is explicitly DEMO-SCALE, with the real 8,000/day intake rate met on
   ingestion (p50 28 ms) but SQLite concurrency p95 ~72 s documented as the
   weakness. PostgreSQL is the stated production path, PLANNED not shipped. NOT
   claimed: production performance.

## 86. **Can the AI order police action?**
   No. No automated action exists anywhere. The strongest output is an advisory
   recommendation + evidence for a human; fund-block requires an officer's
   explicit held/recovered action.

## 87. **Could the AI create a policing feedback loop?**
   Architecturally no: interventions/outcomes are never features and the model is
   not auto-retrained on its own actions. Concentration + repeat-targeting
   monitors and randomized review exist. ✔ (architecture verified)

## 88. **Your adversarial AUC in 'normal' world is 0.85, lower than your main 0.93. Why?**
   Different split/seed regime between the two evaluation harnesses (main is a
   dedicated chronological 70/30; adversarial_worlds uses its own world splits).
   Both are honest, internally consistent evaluations, not contradictory — the
   0.85 is the reference within its own world grid. We report the two figures
   with their methodology, not conflate them.

## 89. **Which split is the honest worst case?**
   New-hotspot (generalization_splits) and sparse_data (adversarial_worlds): AUC
   0.76–0.80, ECE up to 0.13 and PR-AUC 0.09. Both published.

## 90. **What data do you have that is real?**
   None. All metrics are synthetic-label. Real NCRP/CFCFRMS/bank data requires
   authorized access (REAL_DATA_VALIDATION_PROTOCOL.md). NOT claimed: any real
   data, any real-world performance.

## 91. **Why should MHA trust any of your numbers?**
   Use them only as controlled-synthetic evidence of architecture and method, not
   as real-world performance. The pilot protocol is the mechanism to replace
   synthetic numbers with measured ones. Reproducibility is committed (all
   numbers re-run here, in VERIFICATION_LOG).

## 92. **Your mule-graph terminal-risk P@K is only ~0.05. Why ship it?**
   It is a documented SECONDARY signal (mule-graph_eval.json: K=100 P@K 0.06–0.10
   vs random 0.01–0.02). Honest modest lift, disclosed as secondary, not
   overclaimed.

## 93. **Your wallet/graph backtest beats random but barely. Is that worth it?**
   It is a real, small, defensible edge used only as supporting evidence for the
   money-trail UI, with its own honest eval file. We do not cite it as headline
   performance.

## 94. **Your hourly mode AUC is 0.55. Why mention it at all?**
   Because we tested it and report the degradation honestly (mechanical
   feasibility, poor accuracy → experimental, not operational). Hiding a test we
   ran would be dishonest.

## 95. **What is precision@1000 vs precision@100? Does top-100 overstate?**
   P@100 0.84 vs P@1000 0.56. Top-100 is the operational dispatch band; P@1000 is
   more diluted. We report both and the threshold curve so a judge sees precision
   falls with K — no cherry-picking a single K.

## 96. **Is ECE your calibration metric? What are the worst values?**
   Yes, ECE-10bin. Main split ~0.013; worst is new-hotspot 0.11–0.13 (surfaced).
   We report per-split, never a single good number.

## 97. **How much of your advantage is the Platt calibration vs the model?**
   XGBoost-only and ensemble differ: XGB AUC 0.927 vs ensemble AUC 0.80; active
   model selection picks XGB. Calibration adds reliable probabilities and the
   threshold/HOLD policy; it does not inflate ranking.

## 98. **What is the single figure a judge should remember for robustness?**
   Under label-permutation AUC drops to 0.488 (chance) — proving the model
   cannot memorize labels and must use real signal. That is the strongest single
   leakage-defence number. ✔

## 99. **What would you do differently with more time?**
   (1) Solicit authorized real data early for recalibration; (2) engineer
   dedicated novel-hotspot and sub-daily features; (3) scale tests on PostgreSQL;
   (4) anchor the ledger to a permissioned testnet. All are documented upgrade
   paths, none are hidden gaps.

## 100. **Final: is this a working system or a demo?**
   It is a working full-stack prototype on synthetic data: every feature is
   exercised end-to-end (auth/RBAC, alerts, recovery, ledger, PDF, mule-trail),
   evaluated honestly with reproduced numbers, and packaged to run. It is NOT a
   production deployment and claims no real-world performance. "Working demo with
   an honest, reproducible scientific base" is the accurate claim.
