# PHASE_SCORECARD_HONEST.md — Phase 1–25 scorecard (honest register)

> **HONEST-CORRECTION BANNER**: This is the honest scorecard. Every 0.92x ROC-AUC
> figure published before 2026-08-29 came from a SAME-DAY LABEL-LEAKAGE bug in
> feature engineering (`backend/ml/features.py`, `_shift_day_past`), now fixed.
> Those figures are **invalidated / superseded**. The honest, forecast-safe
> ROC-AUC is **0.6273**. Superseded leaky artifacts are flagged below with honest
> replacements where available or "not re-run". Full detail: MODEL_CARD.md,
> VERIFICATION_LOG.md (P1.5), RECONCILIATION.md.

## Headline honest performance (per metrics.json + honest re-runs)

| Metric | Honest value |
|---|---|
| ROC-AUC | **0.6273** |
| Accuracy | 0.9391 |
| P@20 / 50 / 100 / 200 / 500 / 1000 | 0.65 / 0.64 / 0.61 / 0.57 / 0.372 / 0.261 |
| Recall@20 / 50 / 100 | 0.0044 / 0.0107 / 0.0205 |
| Baselines (volume) P@20/50/100 | 0.05 / 0.02 / 0.04 |
| Baselines (proximity) P@20/50/100 | 0.10 / 0.08 / 0.09 |
| Lift vs volume @20/50/100 | 13.0 / 32.0 / 15.25 |
| Lift vs proximity @20/50/100 | 6.5 / 8.0 / 6.78 |
| Lead time (operational) | median 15.9h (p25 10.6h, p75 19.7h) |

Precision/recall operating points (prf thresholds):

| Threshold | Alerts | Precision | Recall | FAR |
|---|---|---|---|---|
| 0.5 | 62 | 0.6613 | 0.0138 | 0.3387 |
| 0.6 | 47 | 0.6383 | 0.0101 | — |
| 0.7 | 32 | 0.75 | 0.0081 | 0.25 |
| 0.85 | 3 | 0.6667 | 0.0007 | 0.3333 |

Honest generalization splits (artifacts/deep_eval/generalization_splits.json):
random **0.627**, time_forward **0.6263** (P@100 0.66), cold_atm **0.5963**,
cold_city/cold_district **0.6228**, new_hotspot **0.5847** (P@100 0.27 — the
honest worst split).

Ablation (honest): A complaint-only 0.4938; B +geography 0.4448; C +financial
0.5814; D +temporal 0.4219; E full 0.6263.

Dataset: 100% synthetic, single state "State-A" / district "Northsagar", 180 ATMs,
XGBoost + Platt-sigmoid, n_test 48,600, positive_share 0.0522, split_day
2026-07-07. Labels 100% synthetic — no real NCRP/CFCFRMS data (REAL_DATA_GAP.md,
LABEL_VALIDITY.md).

Live calm day (honest consequence): all ATMs low risk (max ~0.0627), 0 high-risk,
0 alerts.

## Phase-by-phase verdict (honest register, scores /10)

| # | Phase | Evidence | Honest result | Verdict | Score |
|---|---|---|---|---|---|
| 1 | Baseline & headline metrics | `metrics.json`, `operational.json` (honest) | AUC 0.6273; P@100 0.61; P@1000 0.261 | MODEST, leak-free, honestly reproduced | 6 |
| 2 | Generator/label leakage audit | `permutation_tests.json`, `feature_audit.json` — **superseded (pre-leakage-fix); not re-run** | Honest stand-in: complaint-only ablation 0.4938 (≈ chance); single-feature AUCs 0.43–0.56 | No leak indicated; weak complaint signal | 5 |
| 3 | Spatial generalization | `generalization_splits.json`, `cold_location.json` (honest) | cold_city/district 0.6228; cold_atm 0.5963; **new_hotspot 0.5847 (P@100 0.27)** | Weak splits reported; new-hotspot is the weakest | 6 |
| 4 | Temporal generalization & lead time | `horizons.json` — **superseded (pre-leakage-fix)**; honest re-runs | time_forward 0.6263 (P@100 0.66); median lead 15.9h (p25 10.6, p75 19.7) | 24h operational band confirmed; sub-daily not re-run | 6 |
| 5 | Label validity | LABEL_VALIDITY.md, REAL_DATA_GAP.md | 100% synthetic labels; single region; n_test 48,600; pos share 0.0522 | Honest disclosure; no real-data claim | 7 |
| 6 | Baseline war / model comparison | `baseline_war.json` — **superseded (pre-leakage-fix)**; honest values above | Lift vs volume 13.0/32.0/15.25; vs proximity 6.5/8.0/6.78 | Modest but real edge over trivial baselines | 6 |
| 7 | Feature signal / no-single-feature | `feature_audit.json` — **superseded (pre-leakage-fix)**; honest ablation | Best single feature `days_since_epoch` 0.5604; `counterparty_count_24h` 0.5571; `is_weekend` 0.434; ablation E full 0.6263 | All single features weak; ensemble-of-weak not strong | 5 |
| 8 | Model selection / disagreement | `model_disagreement.json` — **superseded (pre-leakage-fix)**; honest re-run | XGB 0.6273 vs ensemble 0.5902 → **XGB is the active model** | Selection logic sound; gap small either way | 5 |
| 9 | Adversarial simulation & drift | `adversarial_worlds.json`, `drift.json` — **superseded (pre-leakage-fix)** | Honest completed worlds 0.6321 / 0.6386; drift not re-run | Honest worlds modest; no drift claim | 4 |
| 10 | Seed stability | `seed_stability.json` — **superseded (pre-leakage-fix)**; honest re-runs | Seeds in ~0.626 AUC range; P@100 0.61 (noisy) | Stable-ish but modest; leaky 0.918–0.927 invalid | 5 |
| 11 | Threshold / HOLD / uncertainty policy | prf threshold table, threshold curve (honest) | 0.5→62 alerts (P 0.6613, FAR 0.3387); 0.7→32 (P 0.75, FAR 0.25); 0.85→3 (P 0.6667) | Sound policy, but recall is very low; high-FAR tradeoff at operational thresholds | 7 |
| 12 | PDP safety | RESPONSE_PLAYBOOK, priority docs, threat model | Graded, human-gated, no automation | Structure verified, leak-independent | 8 |
| 13 | Feedback-loop safety | ledger replication + architecture | Interventions never features; no auto-retrain; tamper-evident ledger | Architecture verified, leak-independent | 8 |
| 14 | Fairness | `fairness_groups.json` (leaky-era) | Honest re-run not confirmed; no honest group-FPR number carried forward | Retained as process; no honest numeric claim | 5 |
| 15 | Security red team | FINAL_SECURITY_AUDIT.md + regression tests | IDOR + stale-cache found, fixed, 12/12 regression green (leak-independent) | Strong, reproducible security work | 9 |
| 16 | Failure engineering | DEMO_MODE, corrupt-model, DB-outage paths | Clean failures, cache fallback, restore path | Leak-independent engineering | 8 |
| 17 | Production integration | `transfer_readiness.json` — **superseded (pre-leakage-fix); not re-run** | No honest retrain-on-shift claim carries over | Pending honest re-run | 4 |
| 18 | Scale | `load_test.json` (leaky-era) | Demo-scale only; exact latencies not re-confirmed; PostgreSQL = PLANNED path | Honest about demo ceiling | 6 |
| 19 | GitHub / judge experience | DEMO_CREDENTIALS, README, VERIFICATION_LOG | Runnable demo + role login + reproducible log | Strong delivery plumbing | 8 |
| 20 | SIH deliverable completeness | THREAT_MODEL, NOVELTY, real-data protocol | All 8 mandated deliverables present | Complete as deliverables; scientific claim modest | 7 |
| 21 | Live operational mode | live calm-day run (honest) | all ATMs low risk (max ~0.0627); 0 high-risk; 0 alerts | Honest consequence: no false alarm storm on calm days | 6 |
| 22 | Data honesty / real-data gap | REAL_DATA_GAP.md, LABEL_VALIDITY.md | 100% synthetic, single state/district, pilot protocol documented | Exemplary candour about the gap | 10 |
| 23 | Lead-time operability | honest re-runs | median 15.9h (p25 10.6, p75 19.7); 24h band only | Useful but not sub-daily | 6 |
| 24 | 100 hostile questions | Q&A_PREPARATION.md + HOSTILE_Q_ADDENDUM_HONEST.md | 100 answered in the honest register; superseded artifacts flagged | Candid, reproducible | 8 |
| 25 | Kill loop / final report | VERIFICATION_LOG, FINAL docs, RECONCILIATION.md | Leak fixed; all 0.92x figures invalidated; honest equivalents published | See final scorecard | 7 |

## Honest limitations (stated to every judge, never hidden)
1. **No real data** — all numbers are 100% synthetic-label (single district, 180
   ATMs); no real-world performance claim of any kind.
2. **Weak single-feature signal** — every single feature AUC is ~0.43–0.56; the
   best is `days_since_epoch` 0.5604. The discrimination edge is modest, not
   driven by a strong predictive feature.
3. **Low recall / high false-alert tradeoff** — at operational thresholds recall
   is 0.005–0.014; FAR rises with sensitivity. Few alerts, and those are noisy.
4. **New-hotspot generalization is the honest weak split** — AUC 0.5847, P@100
   0.27; the most SIH-relevant case is the least solved.
5. **Single-region, synthetic, demo-scale** — State-A/Northsagar only; SQLite
   demo; PostgreSQL planned, not shipped.
6. **Superseded artifacts pending honest re-run** — adversarial_worlds, drift,
   seed_stability, feature_audit, horizons, transfer_readiness, baseline_war,
   model_disagreement, permutation_tests are all pre-leakage-fix and flagged as
   such in RECONCILIATION.md; only the honest values quoted here are load-bearing.

## Final scorecard (honest self-assessment, out of 10)
| Dimension | Score | Rationale |
|---|---|---|
| Authentic SIH relevance | 7 | Right problem, honest pipeline, but evidence is synthetic and the novel-hotspot case (0.5847) is weak |
| ML rigor / leakage defense | 6 | Modest discrimination; leak-fixed and honestly re-run; many auxiliary artifacts still superseded |
| Honesty / anti-fabrication | 10 | 0.92x figures invalidated, superseded artifacts flagged, real-data gap never hidden |
| Security & governance | 9 | IDOR/stale-cache fixed + regression-tested; HITL; tamper-evident ledger; no automation |
| Engineering | 8 | Full-stack prototype, RBAC, reproducible pipeline, runnable demo |
| Operational realism | 6 | Human-gated, evidence-first, HOLD policy — but low recall at honest thresholds |
| **Overall** | **7/10** | Honest, well-engineered prototype with modest synthetic-data discrimination; the real-data pilot is the genuine next step, and we say so |

## The one sentence for the judge
"On identical synthetic data, CashGuard's honest forecast-safe model is modest
(ROC-AUC 0.6273, P@100 0.61) but leak-free, beats its trivial baselines, reports
its weakest split (new-hotspot 0.5847) openly, ships with real security and
governance engineering, and never claims a number it cannot reproduce — the
real-data pilot protocol is the honest next step, not a gap we paper over."