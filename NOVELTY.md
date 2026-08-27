# NOVELTY.md — Defensible Innovation Claims (Phase 14)

## What existing hotspot prediction systems generally do
- Rank locations by historical incident density or complaint volume.
- Flag "busy" areas; rarely model the *withdrawal* side of cyber-fraud.
- Present a single risk number with no uncertainty, evidence chain, or
  closed-loop outcome monitoring.
- Rarely combine complaint intelligence with bank cash-out behaviour.

## What CashGuard adds (the defensible claims)
1. **Evidence-first cyber-fraud cash-out intelligence**: prediction is joined to
   a per-alert evidence graph (complaint surge → velocity → mule concentration →
   proximity → temporal similarity), each node with value, direction, source
   type, and observed/synthetic label — no unexplained AI reasoning.
2. **Uncertainty-aware forecasting**: every forecast carries confidence,
   evidence strength, data freshness, model version, horizon, and a HOLD ACTION
   state when evidence is weak or data is stale.
3. **Emerging vs historical risk**: a rate-of-change score separates "usually
   risky" from "risk is rising fast now" and the UI prioritizes the latter.
4. **Lead-time evaluation across horizons** (6/12/24/48h) — "how much warning
   could this forecast provide" is measured, not claimed.
5. **Human review gate**: review-oriented recommendations, mandatory reason for
   dismiss/escalate, everything ledger-audited.
6. **Closed-loop outcome monitoring**: predicted vs actual vs UNKNOWN with
   FP/FN and calibration-drift tracking — no auto-retraining on tiny samples.
7. **Intervention-aware ranking**: operational metrics (PR-AUC, false-alert
   rate, alert volume, capture rate, threshold precision) reported alongside
   headline ranking metrics.
8. **Adversarial-world evaluation**: the model is tested across 8 controlled
   scenario worlds (geographic/temporal/ATM-preference/reporting-delay/volume/
   drift/sparse), not just one generator.

## What we cannot honestly claim as unique
- Hawkes-style contagion modelling is not new (we say so).
- XGBoost is not new. GIS dashboards are not new.
- We do not claim real-world accuracy, government access, or deployment.

## The honest innovation statement
> "The innovation is not a single algorithm — it is an evidence-first,
> uncertainty-aware, human-reviewed loop that turns complaint intelligence
> into intervention-ready, audit-provable forecasts of cash withdrawal risk,
> evaluated honestly across adversarial synthetic worlds."