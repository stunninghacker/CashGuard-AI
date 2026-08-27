# JUDGE_BRIEF.md — CashGuard AI, SIH26184 (2 pages)

## Problem
~8,000 cybercrime complaints/day reach NCRP, but by the time police act on a
complaint, the cash has already been withdrawn from an ATM. Recovery is
effectively zero. SIH26184 asks for the *reverse*: predict the withdrawal
locations in advance so intervention happens before the money moves.

## Existing gap
Off-the-shelf fraud platforms are *reactive* (flag past transactions).
Hotspot heuristics ("busiest ATM", "nearest complaint") are *weak*: measured
baseline precision@100 of 0.03–0.07 on our test split. Nothing on the
competition floor combines location forecasting, evidence, uncertainty, and
an audit trail with human-gated action.

## CashGuard
A prototype predictive-analytics framework: complaint + ATM/withdrawal data
→ calibrated XGBoost (P(fraud at ATM in next 24h), Platt-calibrated) →
GIS hotspot dashboard with multi-horizon confidence (2/6/12/24/48h) →
evidence panel (TreeSHAP + counterfactual + source tags) → graded,
review-oriented recommendations → recovery funnel → tamper-evident audit
chain. Synthetic data is calibration-honest (every parameter source-tagged),
and a formal real-data validation protocol + 30-day shadow-mode pilot plan
make the authorized-data path explicit and mechanical.

## Architecture
Repository-layer data isolation (SQLite↔PostgreSQL one-config) · FastAPI +
JWT/RBAC with row-level scoping verified at the API level · WebSocket live
push (token-auth) · APScheduler alert cycle with dedup + escalation bypass ·
short-TTL single-flight inference cache · role-based dashboards (Police /
Bank / I4C) · Dockerfile · DEMO_MODE deterministic fallback.

## Differentiation (measured, not asserted)
- **Beats operational baselines**: AUC 0.926 vs ≤0.56 for random/volume/
  proximity; P@100 0.86 vs ≤0.07.
- **Intervention value**: at K=10/day, CashGuard captures 5.5% of fraud
  exposure vs 0.5% (volume) / 0.4% (random) — 11–14×, with half the false
  interventions and ~10× per-intervention efficiency.
- **Honest by construction**: precision is strong-but-imperfect (P@1000
  0.53); the 38% false-alert rate is disclosed; short horizons say
  INSUFFICIENT CONFIDENCE — HOLD; per-instance TreeSHAP is implemented and
  labeled correctly.
- **Adversarially tested**: 12 drift worlds, cold-location (unseen city AUC
  0.92), baseline war, seed-stability (AUC spread 0.0009), generator-leakage
  audit — all reproducible in one command.

## Measured results (CONTROLLED SYNTHETIC EVALUATION)
AUC 0.927 · P@100 0.86 · P@1000 0.53 · Brier 0.047 · lead 14.9h · fairness
FPR flat 0.002–0.006 across 12 groups · load test sustains 8,000/day
(ingestion 28–66ms/batch) · 8-user concurrency 5.5s (cache) · every number
traces to an artifact.

## Limitations (stated, not hidden)
Synthetic labels only · real data requires authorized access (protocol ready,
not started) · SQLite write-concurrency at scale (PostgreSQL = one config
swap) · prototype token scheme (OAuth2/OIDC documented as production path).

## Production path
NCRP/CFCFRMS/bank feeds via the repository layer → shadow mode → silent
prediction → human-reviewed pilot (30 days, pre-registered KPIs) → monitored
operation with rollback. No automated police action exists at any stage.

## Why SIH should care
CashGuard is the only entry where the forecast, the uncertainty, the
evidence, the human decision, and the audit trail form one traceable loop —
and where every claim is falsifiable by a judge running `python run.py`.