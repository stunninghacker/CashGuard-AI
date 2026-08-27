# JUDGE_BRIEF.md — CashGuard AI, SIH26184 (2 pages)

## Problem
~8,000 cybercrime complaints/day reach NCRP, but by the time police act on a
complaint, the cash has already been withdrawn from an ATM. Recovery is
effectively zero. SIH26184 asks for the *reverse*: predict the withdrawal
locations in advance so intervention happens before the money moves.

## Existing gap
Off-the-shelf fraud platforms are *reactive* (flag past transactions).
Hotspot heuristics ("busiest ATM", "nearest complaint", "historical hotspot")
are *weak*: measured baseline precision@100 of 0.01–0.25 on our test split.
Nothing on the competition floor combines location forecasting, evidence,
uncertainty, an audit trail, and human-gated action.

## CashGuard
A prototype predictive-analytics framework: complaint + ATM/withdrawal data
→ calibrated XGBoost (P(fraud at ATM in next 24h), Platt-calibrated) →
GIS hotspot dashboard with multi-horizon confidence (2/6/12/24/48/72h) →
evidence panel (per-instance TreeSHAP + counterfactual + source tags) →
graded, review-oriented recommendations (ACT/REVIEW/HOLD policy) → recovery
funnel → tamper-evident audit chain replicated across 3 nodes (Blockchain &
Cybersecurity theme, honestly scoped). Synthetic data is calibration-honest
(every parameter source-tagged), and a formal real-data validation protocol
+ 30-day shadow-mode pilot plan make the authorized-data path explicit.

## Architecture
Repository-layer data isolation (SQLite↔PostgreSQL one-config) · FastAPI +
JWT/RBAC with row-level scoping verified at the API level (14 security
regression tests) · WebSocket live push (token-auth) · alert cycle with dedup
+ escalation bypass · short-TTL single-flight inference cache (8 users in
5.5s) · role-based dashboards (Police / Bank / I4C) · Dockerfile · DEMO_MODE
deterministic fallback that survives a missing model.

## Differentiation (measured, not asserted)
- **Beats operational baselines**: AUC 0.926 vs ≤0.68 for random/volume/
  proximity/historical-hotspot; P@100 0.86 vs ≤0.25; Brier 0.047 vs 0.31+.
- **Intervention value**: at K=10/day, CashGuard captures 5.5% of fraud
  exposure vs 0.5% (volume), 1.9% (historical), 0.4% (random) — 3–14×, with
  half the false interventions and ~10× per-intervention efficiency.
- **Honest by construction**: precision strong-but-imperfect (P@1000 0.53);
  38% false-alert rate disclosed; short horizons say INSUFFICIENT
  CONFIDENCE — HOLD; hourly mode measured and honestly reported as weaker
  (AUC 0.55 vs 0.93 daily — experimental, not claimed).
- **Adversarially tested**: 12 drift worlds, permutation tests (no identity
  memorization), 6 generalization splits (new-hotspot weak split reported),
  transfer readiness (AUC degradation ≤0.006 across distributions), baseline
  war, seed stability — all reproducible in one command.
- **Fairness on the dashboard outputs**: FPR flat 0.0015–0.0062 across 15
  groups; the model can never learn from its own interventions.

## Measured results (CONTROLLED SYNTHETIC EVALUATION)
AUC 0.927 · P@100 0.86 · P@1000 0.53 · Brier 0.047 · ECE 0.016 · lead 14.9h ·
fairness FPR flat across 15 groups · load test sustains 8,000/day (ingestion
28–66ms/batch) · 8-user concurrency 5.5s (cache) · every number traces to an
artifact under `artifacts/`.

## Blockchain & Cybersecurity theme (honest scope)
Tamper-evident SHA-256 audit chain (live, verified by the tamper demo) +
3-node majority-quorum replicated ledger (live demo, fault tolerance).
External testnet anchoring is a documented integration point
(`LEDGER_ANCHOR_RPC_URL`), **not exercised** — see BLOCKCHAIN_JUSTIFICATION.md.

## Limitations (stated, not hidden)
Synthetic labels only · real data requires authorized access (protocol ready,
not started) · SQLite write-concurrency at scale (PostgreSQL = one config
swap) · prototype token scheme (OAuth2/OIDC documented as production path) ·
hourly granularity experimental.

## Production path
NCRP/CFCFRMS/bank feeds via the repository layer (exact contract in
REAL_DATA_READINESS.md) → shadow mode → silent prediction → human-reviewed
pilot (30 days, pre-registered KPIs) → monitored operation with rollback.
No automated police action exists at any stage.

## Why SIH should care
CashGuard is the entry where the forecast, the uncertainty, the evidence,
the human decision, and the audit trail form one traceable loop — and where
every claim is falsifiable by a judge running `python run.py`.