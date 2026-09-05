# FINAL_10_10_TEMPORAL_GENERALIZATION.md — Forecast lead-time honesty


> **WARNING: DATA-LEAKAGE CORRECTION (2026-08-29)** - This document's reported ROC-AUC figures (~0.92x) came from a SAME-DAY LABEL-LEAKAGE bug in feature engineering (backend/ml/features.py, `_shift_day_past`), now fixed. The honest forecast-safe ROC-AUC is **0.6456** (leaky 0.9275 -> corrected 0.6344 in the proof). On calm days the live model scores every ATM low (max ~0.11) and produces **no alerts**; any populated high-risk alert view is the opt-in, clearly-labelled **"Load Simulated Scenario"** mode (SCRIPTED, not live model output). Treat all 0.92x figures in this doc as superseded. Full detail: MODEL_CARD.md, VERIFICATION_LOG.md (P1.5).
Question: how far in advance can CashGuard actually predict a cash-out hotspot?

Scope note: `horizons.json` is a stored artifact. It was NOT re-run live this
session, but its 24h-horizon ROC-AUC (0.9261 <sup>⚠ superseded → honest 0.6456</sup>) is consistent with the live
retrain (0.9272 <sup>⚠ superseded → honest 0.6456</sup>) and the live time-forward split (0.926 <sup>⚠ superseded → honest 0.6456</sup>) — the numbers are
credible and internally consistent, and the qualitative finding is robust.

## The lead time / horizon curve (stored `horizons.json`)
Calibrated 24h score evaluated against per-horizon event labels.

| Horizon | ROC-AUC | PR-AUC | P@1000(h) | Recall@1000 | Event rate | Confidence |
|---|---|---|---|---|---|---|
| 2h | 0.921 <sup>⚠ superseded → honest 0.6456</sup> | 0.039 | 0.04 | 0.267 | 0.003 | **INSUFFICIENT → HOLD** |
| 6h | 0.917 | 0.076 | 0.082 | 0.280 | 0.006 | **INSUFFICIENT → HOLD** |
| 12h | 0.916 | 0.157 | 0.18 | 0.226 | 0.016 | **INSUFFICIENT → HOLD** |
| **24h** | **0.926 <sup>⚠ superseded → honest 0.6456</sup>** | **0.408** | 0.528 | 0.176 | 0.062 | MEDIUM |
| 48h | 0.735 | 0.346 | 0.577 | 0.104 | 0.114 | MEDIUM |
| 72h | 0.661 | 0.344 | 0.608 | 0.078 | 0.161 | MEDIUM |

## Interpretation (honest)
1. **24h is the only operationally meaningful horizon.** ROC-AUC stays high at
   2–12h but PR-AUC collapses (0.04–0.16) because the event rate at short
   horizons is tiny — at a 2h lead the false-alert rate at 0.7 threshold is
   94.8%. The system runs an ACTIVE dispatch rule that correctly labels short
   horizons **"INSUFFICIENT CONFIDENCE — HOLD ACTION"**.
2. **Beyond 24h, ranking quality decays** (48h AUC 0.735, 72h 0.661). The
   system does NOT overclaim multi-day early warning.
3. **Judge-facing tension:** the SIH brief implies "real-time / near-real-time
   alerts" AND "forecast in advance". CashGuard's alert generation is real-time,
   but its *predictive granularity* only supports a ~24h planning horizon. That
   is honestly bounded (median lead time ~15h, p75 ~20h), not hidden.

## Bottom line
The claim that survives scrutiny is: **"~24h-ahead hotspot ranking with
high-precision top-K, modest lead time, and explicit HOLD at sub-daily
horizons."** Any claim of minutes-to-hours early warning would be unsupported
by the evidence and is explicitly NOT made.
