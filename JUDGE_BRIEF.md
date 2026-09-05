# JUDGE_BRIEF.md — CashGuard AI, SIH26184 (2 pages)

> **METRICS UPDATED (2026-09-05).** The data bug (40-day withdrawal span) has been
> fixed. The full 200K dataset now spans 180 days. **Honest forecast-safe ROC-AUC: 0.6456.**
> 5-fold CV 95% CI: [0.6350, 0.6463]. The previous 0.927 AUC was leakage-invalid
> and is permanently blocked by pre-commit hook.
> **[SOURCE OF TRUTH: `CURRENT_METRICS.md` + `artifacts/current_metrics.json`]**

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

## Differentiation (measured, not asserted) — metrics as of Sep 5 2026
- **Beats operational baselines**: honest forecast-safe AUC **0.646** (5-fold CV
  [0.635, 0.646]). P@100 = 0.71 vs 0.09 (random), 0.22 (historical), 0.04
  (volume) — 3.2–17.8x lift.
- **Intervention value**: at K=10/day, CashGuard captures fraud exposure with
  7.9x lift over random selection and 3.2x over historical hotspot baselines.
- **Honest by construction**: precision strong-but-imperfect (P@1000 0.34);
  30% false-alert rate disclosed; short horizons say INSUFFICIENT
  CONFIDENCE — HOLD.
- **Adversarially tested**: 12 drift worlds, permutation tests (no identity
  memorization), 6 generalization splits (cold-ATM 0.638, cold-city 0.666,
  new-hotspot 0.673 AUC), baseline war, all reproducible.
- **Fairness on the dashboard outputs**: FPR flat across demographic groups
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