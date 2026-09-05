# FINAL EXTERNAL LIMITATIONS — CashGuard AI (SIH26184 prototype)

**Date:** 2026-08-30 · **Integrity:** all numbers are the honest, post-leakage-fix values from
`artifacts/metrics.json`. The earlier 0.92x ROC-AUC was invalidated by a same-day label-leakage fix
and is not valid (see `docs/FINAL_LEAKAGE_AUDIT.md`). This document is the honest, external-facing
statement of what this prototype does and does not establish.

Companion docs: `REAL_DATA_GAP.md`, `THREAT_MODEL.md`, `LIMITATIONS.md`, `LABEL_VALIDITY.md`.

---

## 1. Synthetic, single-region dataset — and no real per-ATM fraud benchmark

**What it is:** Every metric is measured on synthetic labels generated from
public-pattern-calibrated data (complaint volumes, fraud-share direction, mule behaviour) in a
single state (`State-A`) and single district (`Northsagar`), 900 ATMs, chronological split from
a 200K-withdrawal, 180-day span dataset.

**Why it matters:** There is **no real-world per-ATM fraud benchmark in this repository.** This
must be stated plainly: **calibration against a real baseline is not possible** — there is no real
ground truth here to calibrate to. The honest ROC-AUC of **0.6456** (and P@20..1000 of
0.70/0.70/0.67/0.57/0.434/0.329) is a score on synthetic labels. It demonstrates methodology
(time-based splits, precision@K, baseline lifts, lead-time) but is not a field-validated trueness
or precision claim.

**What it takes to close:** An authorized real-data pilot per `REAL_DATA_GAP.md` — a MoU/sandbox
extract of historical NCRP complaints plus investigation-confirmed withdrawal outcomes for a pilot
district, shadow-mode scoring, then threshold re-derivation and re-evaluation of precision@K and
lead-time. Only that replaces synthetic labels with real ones.

## 2. Low base-rate recall trade-off

**What it is:** Positive share is ~5%. The model concentrates precision at the top of
the ranking (P@20 0.70, prf@0.7 P 0.75) but absolute recall is low at dispatch thresholds.

**Why it matters:** At these thresholds the system flags few true positives as a fraction of all
fraudulent ATM-days. Operators should read "67-75% of what we flag is real (in this synthetic
window)" and "we still miss most fraud", not "we catch most fraud".

**What it takes to close:** Real-outcome calibration plus an ops review that trades recall against
alert budget per district/bank. This cannot be done meaningfully on synthetic labels.

## 3. Single district — no true multi-jurisdiction / RBAC data

**What it is:** The dataset has a single state and single district (`Northsagar`), and in this
synthetic world district == city (see `generalization_splits.json`). RBAC row-scoping is enforced in
the repository layer and verified live (district/bank/state/I4C scoping), but the prototype has not
been exercised across genuinely distinct jurisdictions with different routing.

**Why it matters:** `THREAT_MODEL.md`'s multi-role access posture is implemented and audited, yet
true inter-agency routing/handoff and cross-state coordination depend on non-public MHA/I4C
operational protocols and can only be validated with real multi-jurisdiction data.

**What it takes to close:** A multi-district / multi-state authorized pilot (REAL_DATA_GAP.md asks);
re-run the RBAC and routing verification on real, route-distinct data.

## 4. Demo-scale and no live traffic

**What it is:** 180 ATMs on a single process (SQLite, uvicorn). The alert pipeline, ledger, WS
feed, and webhook path are real but demo-scale. There is no live traffic — the streaming feed is a
simulator (`StreamSimulatorAdapter`); a Kafka adapter for ~8,000 complaints/day scale is a Tier-2
stub (`LIMITATIONS.md`).

**Why it matters:** Load behaviour, concurrent-writer limits (SQLite), WS connection pooling, and
fairness-cap behaviour at national scale are not demonstrated. `LOAD_TEST.md` covers demo-scale only.

**What it takes to close:** PostgreSQL + read replicas, distributed rate limiting, and a national-scale
load test with replicated model serving — all documented as production requirements, not claimed.

## 5. Calibration on real data not yet performed

**What it is:** The model is Platt-sigmoid calibrated on a synthetic validation slice.

**Why it matters:** Real-world probabilities will differ; the honest lead-time (median 12.8h, P25
8.7, P75 17.6) and calibration are valid for the synthetic world only, and are horizon-dependent
(`metrics.json lead_time_is_horizon_dependent: true`).

**What it takes to close:** Platt recalibration on real confirmed outcomes during the pilot
(`REAL_DATA_GAP.md`), plus PSI drift baselines and re-audit per `REAL_DATA_VALIDATION_PROTOCOL.md`.

---

**Bottom line:** This is a methodologically rigorous, demo-scale single-region prototype on
synthetic data. It does not claim field-validated fraud accuracy, real calibration, multi-jurisdiction
operation, or live-traffic maturity. Those are closed only by an authorized real-data pilot.
