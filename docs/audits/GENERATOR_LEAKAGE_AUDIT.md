# GENERATOR_LEAKAGE_AUDIT.md — Can the model be rediscovering generator assumptions?

Red-team question: is CashGuard's "performance" merely echoing the generator's
construction rules? This audit attacks the generator + pipeline directly.

## 1. Feature-target correlation audit (artifact: `metrics.json` `per_feature_auc`, `feature_audit.json`)
- Strongest single feature: `counterparty_count_24h` (complaint-linked mule
  accounts at the ATM in the trailing 24h) — single-feature AUC **0.8447**.
  This is a *legitimate* signal: complaints precede cash-outs (the feature's
  window ends before the forecast point; the label is fraud in the 24h AFTER).
- Next-strongest: `distinct_accounts_24h` 0.6722. All other features < 0.6.
- Post-de-separation feature audit: top-1 importance **32.9%**, top-3 56.8% —
  no single feature dominates; the model needs the ensemble.
- A genuine generator leak would show single-feature AUC ≈ 1.0 (the 2026
  `fraud_withdrawals_24h` leak had exactly that signature and was removed +
  grep-verified as label-only).

## 2. Generator parameter sensitivity (artifact: `robustness_check.json`)
±30% perturbation of clustering/timing/behaviour parameters → AUC moves
**0.9232–0.9324** (<0.01). The model is not riding a knife-edge configuration.

## 3. Seed variation (artifact: `seed_stability.json`)
- Model seeds (same data, 5 seeds): AUC 0.9264–0.9273 (spread **0.0009**),
  P@100 0.80–0.83, P@1000 0.518–0.525 — the pipeline is deterministic-stable.
- Generator seeds (fresh data draws, 5 seeds): AUC 0.9201–0.9247 (spread
  0.005), P@100 0.53–0.69, P@1000 0.341–0.369 — the *data draw* itself moves
  top-100 precision by up to 0.16. This is honest variance, reported: P@K at
  the very top of the ranking is draw-sensitive; the headline operational
  numbers (P@1000, AUC) are stable.

## 4. Counterfactual worlds (artifact: `counterfactual.json`, `adversarial_worlds.json`, `drift.json`)
- Complaint-surge counterfactual: +50% surge moves mean risk by +0.0013 —
  the model does NOT mechanically echo complaint volume; mule behaviour
  dominates (consistent with the ablation: complaints-only AUC 0.50).
- Ablation: complaint-only 0.50 → +geography 0.55 → **+financial 0.93** →
  +temporal 0.56 (temporal features hurt — honest) → full 0.93. The signal
  lives in withdrawal/mule behaviour, not in the generator's complaint rules.
- 12 adversarial worlds (incl. risk_avoidance): AUC ≥ 0.86 everywhere —
  the model tracks fraud even when the generator's own preferences change.

## 5. Distribution-shift behavior (artifact: `drift.json`)
Threshold precision varies 0.55–0.83 across worlds; REDUCED confidence is
flagged — the system degrades honestly instead of overclaiming.

## 6. Permutation tests (artifact: `permutation_tests.json`)
- Label shuffle → AUC **0.475** (chance) — the pipeline cannot memorize arbitrary labels.
- Features contain **NO ATM/city/district identity columns** (identity lives in meta only);
  row-order shuffle → AUC identical (0.9265 vs 0.9274) — no order/identity memorization.
- City-feature permutation: negligible (<0.001) — behavioural features carry the signal.

## 7. Spatial generalization (artifact: `generalization_splits.json`)
random 0.931 · time-forward 0.927 · cold-ATM 0.918 · cold-city/district 0.924 ·
**new-hotspot 0.764 (ECE 0.128) — the honest weak split; failures are reported, not averaged away.**

## Verdict
**No target-rediscovery leak found.** The strongest features are
operationally legitimate and prediction-time-safe; the model beats simple
operational baselines (see `baseline_war.json`) because it combines signals,
not because it reads the generator's construction rules. Residual risk is
the honest one: synthetic patterns ≠ real patterns — the real-data protocol
(REAL_DATA_VALIDATION_PROTOCOL.md) re-runs every check above on authorized
data.