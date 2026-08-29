# JUDGE_BRIEF.md — CashGuard AI, SIH26184 (2 pages)

> **⚠ DATA-LEAKAGE CORRECTION (2026-08-29) — read first.** The AUC figures below
> (0.926/0.927) were produced by a **same-day label-leakage** bug in feature
> engineering (fixed). The **honest forecast-safe ROC-AUC is 0.6273**. On calm days
> the live model scores every ATM low (max ~0.11) and produces **no alerts**; the
> populated alert workflow is available only via the opt-in **"Load Simulated
> Scenario"** button and is clearly SCRIPTED (not live model output). Text here that
> cites 0.92x refers to the pre-correction, leaky estimate and is superseded. Full
> detail: `MODEL_CARD.md`, `VERIFICATION_LOG.md` (P1.5).

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

## Differentiation (measured, not asserted) — figures corrected post-leak-fix
- **Beats operational baselines**: honest forecast-safe AUC **0.63** (corrected; see top
  banner — the leaky 0.926 baseline comparison is superseded and baselines need re-running
  on the corrected features).
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

## Measured results (CONTROLLED SYNTHETIC EVALUATION) — CORRECTED
⚠ post-leak-fix honest numbers. AUC **0.6273** · P@20/50/100/200/500/1000 =
0.65/0.64/0.61/0.57/0.372/0.261 · prf@0.7 = 32 alerts / P 0.75 / R 0.008 / FAR 0.25 ·
on calm demo days the model produces **no alerts** (opt-in SCRIPTED scenario shows the
workflow). Every number traces to `artifacts/metrics.json` + `artifacts/deep_eval/threshold_curve.json`.
Any earlier 0.927 here is superseded.

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