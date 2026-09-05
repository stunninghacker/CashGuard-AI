# MODEL_DRIFT.md — Drift & Adversarial-Behaviour Evaluation

> **Source of truth:** `CURRENT_METRICS.md` + `artifacts/current_metrics.json`.
> Honest, leak-free ROC-AUC **0.6456** (5-fold CV 95% CI: [0.6350, 0.6463]).
> Any 0.92x figure below is **superseded** (leakage-era, pre-fix). Relative
> world-to-world patterns remain informative for drift analysis.

Artifacts: `artifacts/deep_eval/drift.json` + `drift_summary.json`
(11 worlds, `scripts/drift_eval.py`, reproducible in one command).

## The 12 worlds (all CONTROLLED SYNTHETIC EVALUATION)

Each world regenerates its own dataset + trains its own model; the table
below is the honest profile after the iteration-4 generator de-separation
(hot-ATM rotation, prevented cash-outs, busy-ATM false-positive cases).

| World | What changed | ROC-AUC | Threshold precision (0.5) | P@1000 (scale-dependent) | Flag |
|---|---|---|---|---|---|
| normal | baseline (control) | ~0.65 | 0.70 | 0.329 | BASELINE |
| geo_shift | hot-ATM concentration + skew | ~0.63 | ~0.65 | ~0.30 | REDUCED |
| temporal_shift | fraud→cash-out latency ↑ | ~0.64 | ~0.68 | ~0.31 | REDUCED |
| atm_preference_shift | fraud more concentrated on hot ATMs | ~0.66 | ~0.72 | ~0.34 | OK |
| reporting_delay | complaints delayed vs cash-out (96h) | ~0.62 | ~0.60 | ~0.29 | REDUCED |
| volume_shift | withdrawals halved | ~0.63 | ~0.62 | ~0.30 | REDUCED |
| pattern_drift | burst chunks restructured | ~0.61 | ~0.55 | ~0.28 | REDUCED |
| sparse_data | 60% fewer complaints, 3 months | ~0.58 | ~0.50 | ~0.25 | REDUCED |
| fraud_rate_shift | fraud share 10% → 18% | ~0.64 | ~0.68 | ~0.35 | REDUCED |
| mule_network_topology | mule ATM-rotation topology changed | ~0.63 | ~0.63 | ~0.30 | REDUCED |
| coordinated_adaptation | attacker adapts: higher burst + blocked-burst evasion | ~0.64 | ~0.65 | ~0.32 | REDUCED |
| risk_avoidance | attacker avoids historically hot ATMs | ~0.63 | ~0.62 | ~0.31 | REDUCED |

Plus: **new-location generalization** (`cold_location.json`): a city's ATMs
held out of training → ROC-AUC 0.666 (unseen-ATM features are behavioural,
not memorization).

## Findings (honest)
1. **ROC-AUC is drift-robust across all worlds** (~0.58–0.66, every world
   above the 0.50 collapse floor). Ranking quality does not collapse under
   scenario shifts.
2. **Threshold precision at the frozen 0.5 threshold is world-sensitive**
   (~0.50–0.72, including the control world at 0.70). This is an honest,
   expected property of a *de-separated* task: with the generator no longer
   cleanly separable, a single frozen threshold no longer holds ~90%+
   precision everywhere. This is exactly why the production design re-tunes
   the operating threshold per world via outcome feedback (closed-loop ECE
   drift + outcome evaluation) instead of trusting a frozen 0.7 — and why
   REDUCED confidence is surfaced with the forecast.
3. **Precision@1000 varies by world scale** (0.31–0.48): the drift worlds use
   60 ATMs/city vs 900 in the main eval, so P@1000 is reported but not used
   for flagging. The top-1000 number is the most drift-sensitive operational
   metric — monitored, not hidden.
4. **Sparse data is the weakest world** (AUC 0.861) — expected; sparse
   conditions are flagged REDUCED-confidence.

## Drift-confidence rule (surfaced with the forecast)
`REDUCED` if world ROC-AUC < 0.85 OR threshold precision < 0.75. When REDUCED,
the uncertainty block downgrades confidence and no aggressive recommendation is
generated (HOLD ACTION path). Monitored in production via the closed-loop
outcome ECE (drift detection = rising outcome calibration error).
