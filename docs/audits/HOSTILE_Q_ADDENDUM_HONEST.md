# HOSTILE_Q_ADDENDUM_HONEST.md — Hostile questions 76–100 (honest register)

> **HONEST-CORRECTION BANNER**: This is the honest correction of the leaky-era hostile
> Q&A (Q76–Q100). Every 0.92x ROC-AUC figure published before 2026-08-29 came from a
> SAME-DAY LABEL-LEAKAGE bug in feature engineering (`backend/ml/features.py`,
> `_shift_day_past`), now fixed. Those figures are **invalidated**. The honest,
> forecast-safe ROC-AUC is **0.6456**. Where this doc references a superseded
> leaky-era artifact, it is tagged **"superseded (pre-leakage-fix); see
> RECONCILIATION.md"** and replaced with the honest value or marked **not re-run**.
> All numbers below are the honest register per `metrics.json` + honest re-runs.
> On calm days the live model scores every ATM low (max ~0.0627) and produces
> **no alerts**; any populated high-risk alert view is the opt-in, clearly-labelled
> **"Load Simulated Scenario"** mode (SCRIPTED, not live model output).

Extends `Q&A_PREPARATION.md` (Q1–Q75) to a full 100. Each answer gives the honest
value or explicitly says the superseded artifact was not re-run. Nothing here is
presented as stronger than the honest evidence.

## 76. **Your metrics.json once had a 9-digit lift number (9×10⁸). What was that?**
   It was a division-by-zero artifact: lift = active_prec / max(baseline, 1e-9);
   when the volume baseline caught zero positives at K=20 it produced 9e8. The bug
   was fixed and the metric regenerated. In the honest register, lift vs the volume
   baseline is **13.0 / 32.0 / 15.25** @K=20/50/100 and lift vs the proximity
   baseline is **6.5 / 8.0 / 6.78** — a genuine but modest edge, not a 9-digit
   headline. NOT claimed: a 9e8 lift was ever real.

## 77. **Your single best feature is counterparty_count_24h at AUC ~0.83. Is that reactive, not proactive?**
   That 0.83 figure is superseded (pre-leakage-fix) and invalid. In the honest
   register, **all single-feature AUCs are weak (~0.43–0.56)**: the best single
   feature is `days_since_epoch` at **0.5604**, then `counterparty_count_24h` at
   **0.5571**, and `is_weekend` at **0.434**. We concede the model is closer to
   **early detection** of ongoing withdrawal flow than proactive forecasting of a
   future hotspot, and **no single feature is strongly discriminative**. NOT
   claimed: any single feature carries the model.

## 78. **So is the whole model just "watch the busy mule ATM"?**
   No single feature dominates (best is `days_since_epoch` 0.5604;
   `counterparty_count_24h` 0.5571 — both weak), and the full model (0.6456) beats
   the volume baseline (P@100 0.04) and proximity baseline (P@100 0.09) with
   honest lift of 13–32× and 6.5–8× at K=20/50. But the honest verdict stands:
   the margin over baselines is **modest**, and the reactive critique from Q77 is
   the correct framing. No feature "dominates" in the honest register.

## 79. **Why do complaints barely move the prediction?**
   Honest ablation: complaint-only model A scores **0.4938 (≈ chance)**; adding
   geography (B) 0.4448; financial (C) 0.5814; temporal (D) 0.4219; full (E)
   0.6263. The complaint-only leg alone is indistinguishable from chance. NOT
   claimed: complaints are the driver — they are not, in either register.

## 80. **If complaints don't matter, why did you build the system around them?**
   The SIH-26184 brief asks for complaint-driven proactive forecasting; we built
   the full complaint pipeline (ingestion, evidence, jurisdiction, CRF funnel),
   then **honestly measured** that the weak ML signal sits on the withdrawal side.
   That is the finding, reported plainly, not a hidden bug.

## 81. **Your new-hotspot precision is ~0.3, not 0.8. Doesn't that defeat the purpose?**
   The honest number is now **new_hotspot AUC 0.5847 with P@100 only 0.27** — the
   weakest of all generalization splits and **the honest worst case**. It is the
   most SIH-relevant split and the least solved. We report it, never average it
   away, and the HOLD policy limits the harm. Improving novel-hotspot detection is
   an open problem, not a claim.

## 82. **What is your generator-seed variance?**
   The leaky era reported AUC 0.918–0.927; that is **superseded (pre-leakage-fix)**.
   In the honest register seeds land in the **~0.626 range** (consistent with the
   headline 0.6456), with P@100 at **0.67** — modest and noisy, and we report the
   range rather than a fixed-seed peak. NOT claimed: seed-stable strong performance.

## 83. **What happens at 2h / 6h / 12h lead?**
   The `horizons.json` curves are **superseded (pre-leakage-fix); see
   RECONCILIATION.md** and were **not re-run** in the honest register. The honest,
   confirmed operational facts are: median lead time **12.8h** (p25 8.7h, p75
   17.6h) and the 24h band (time-forward AUC 0.6263) as the operating horizon.
   Sub-daily horizons are experimental and not carried as operational claims. NOT
   claimed: minutes-to-hours early warning.

## 84. **Why is 24h your only real horizon?**
   Confirmed from the honest data: median lead time 12.8h (p25 8.7, p75 17.6) and
   the strongest honest split is time-forward at **0.6263 (P@100 0.66)**. The
   full short/long-horizon curve is superseded/not re-run; we make no accuracy
   claim beyond the 24h operational band.

## 85. **Your load test uses SQLite. Is that production-grade?**
   No — it is explicitly **DEMO-SCALE** and we do not re-confirm the specific
   latency figures from the leaky-era load test. The stated production path is
   PostgreSQL, **PLANNED not shipped**. NOT claimed: production performance.

## 86. **Can the AI order police action?**
   No. No automated action exists anywhere. The strongest output is an advisory
   recommendation + evidence for a human; fund-block requires an officer's
   explicit held/recovered action.

## 87. **Could the AI create a policing feedback loop?**
   Architecturally no: interventions/outcomes are never features and the model is
   not auto-retrained on its own actions. Concentration + repeat-targeting
   monitors and randomized review exist. (architecture verification is
   leak-independent and stands.)

## 88. **Your adversarial AUC in 'normal' world was 0.85. Why is that lower than the old 0.93?**
   Both figures are from `adversarial_worlds`, which is **superseded
   (pre-leakage-fix); see RECONCILIATION.md** and carries leaky values 0.80–0.897.
   The honest completed adversarial worlds scored **0.6321 and 0.6386** — modest,
   and consistent with the honest headline. We report the honest world grid, not
   the leaky one. Drift artifacts are likewise **not re-run**.

## 89. **Which split is the honest worst case?**
   **New-hotspot: AUC 0.5847, P@100 0.27** — the weakest honest split by the widest
   margin. Cold splits land at cold_atm 0.5963 and cold_city/cold_district 0.6228;
   new_hotspot is the honest floor. The leaky-era sparse-data adversarial claim is
   superseded/not re-run.

## 90. **What data do you have that is real?**
   None. The dataset is **100% synthetic**: a single state ("State-A") / district
   ("Northsagar"), 180 ATMs, 48,600 test rows, positive share 0.0522, split day
   2026-07-07, labels synthetic (see REAL_DATA_GAP.md, LABEL_VALIDITY.md). No real
   NCRP/CFCFRMS data. NOT claimed: any real data or any real-world performance.

## 91. **Why should MHA trust any of your numbers?**
   Use them only as controlled-synthetic evidence of architecture and method, not
   as real-world performance. Every number in this honest register is reproducible
   from `metrics.json` + honest re-runs, and the leaky-era artifacts are flagged
   superseded rather than quietly retained. The pilot protocol is the mechanism to
   replace synthetic numbers with measured ones.

## 92. **Your mule-graph terminal-risk P@K is only ~0.05. Why ship it?**
   It is a documented **secondary** signal with an honest, modest lift over random
   (P@K 0.06–0.10 vs random 0.01–0.02). Disclosed as secondary, used only as
   supporting evidence for the money-trail UI — never as headline performance.

## 93. **Your wallet/graph backtest beats random but barely. Is that worth it?**
   It is a real, small, defensible edge, used only as supporting evidence for the
   money-trail UI, with its own honest eval file. We do not cite it as headline
   performance.

## 94. **Your hourly mode AUC is 0.55. Why mention it at all?**
   We tested it and report the degradation honestly (mechanical feasibility, poor
   accuracy → experimental, not operational). Hiding a test we ran would be
   dishonest.

## 95. **What is precision@1000 vs precision@100? Does top-100 overstate?**
   Honest: **P@100 = 0.67, P@1000 = 0.329**. The full curve is
   P@20/50/100/200/500/1000 = 0.70/0.70/0.67/0.57/0.434/0.329, with
   Recall@20/50/100 = 0.0044/0.0107/0.0205. Top-100 is the dispatch band; rank
   quality falls as K grows. No cherry-picking a single K.

## 96. **Is ECE your calibration metric? What are the worst values?**
   Probabilities come from a Platt-sigmoid on XGBoost. The specific leaky-era ECE
   figures are **not carried over**; we do not quote an ECE value we cannot defend
   in the honest register, and we state per-split calibration honestly rather than
   one headline number.

## 97. **How much of your advantage is the Platt calibration vs the model?**
   Honest model selection: **XGBoost AUC 0.6456 vs ensemble AUC 0.5902** — the
   ensemble is *worse*, so the **active model is XGBoost**. Calibration (Platt)
   adds well-formed probabilities and supports the threshold/HOLD policy; it does
   not inflate ranking, and in the honest register the ranking edge itself is
   modest.

## 98. **What is the single figure a judge should remember for robustness?**
   The leaky-era label-permutation artifact (claimed AUC drop to ~0.488) is
   **superseded (pre-leakage-fix) and was not re-run** — we do not overclaim a
   strong permutation result we cannot reproduce. The honest leakage-defence
   framing is: complaint-only ablation 0.4938 (≈ chance), all single-feature AUCs
   weak (0.43–0.56), and honest splits clustering at ~0.58–0.63 — **modest but real
   signal**, not memorization, and not a strong model.

## 99. **What would you do differently with more time?**
   (1) Solicit authorized real data early for recalibration; (2) engineer dedicated
   novel-hotspot and sub-daily features (new_hotspot 0.5847 is the honest weak
   case); (3) scale tests on PostgreSQL; (4) anchor the ledger to a permissioned
   testnet. All are documented upgrade paths, none are hidden gaps.

## 100. **Final: is this a working system or a demo?**
   A working full-stack prototype on 100% synthetic data: every feature is
   exercised end-to-end (auth/RBAC, alerts, recovery, ledger, PDF, mule-trail),
   and every number in this file is honest (ROC-AUC 0.6456). It is **not** a
   production deployment, it claims **no** real-world performance, and its
   discrimination is modest. "Working demo with an honest, reproducible
   scientific base" is the accurate claim.

---

**Superseded-artifact ledger (per RECONCILIATION.md):**
`adversarial_worlds`, `drift`, `seed_stability`, `feature_audit`, `horizons`,
`transfer_readiness`, `baseline_war`, `model_disagreement`, `permutation_tests` —
all leaky, all pre-2026-08-29-fix. Honest replacements used above where available;
artifacts with no honest re-run are marked **not re-run** and make no claim.