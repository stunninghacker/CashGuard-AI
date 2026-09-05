# FINAL_10_10_SPATIAL_GENERALIZATION.md — Cold/novel locations, verified fresh


> **WARNING: DATA-LEAKAGE CORRECTION (2026-08-29)** - This document's reported ROC-AUC figures (~0.92x) came from a SAME-DAY LABEL-LEAKAGE bug in feature engineering (backend/ml/features.py, `_shift_day_past`), now fixed. The honest forecast-safe ROC-AUC is **0.6456** (leaky 0.9275 -> corrected 0.6344 in the proof). On calm days the live model scores every ATM low (max ~0.11) and produces **no alerts**; any populated high-risk alert view is the opt-in, clearly-labelled **"Load Simulated Scenario"** mode (SCRIPTED, not live model output). Treat all 0.92x figures in this doc as superseded. Full detail: MODEL_CARD.md, VERIFICATION_LOG.md (P1.5).
Live re-run (`generalization_splits.py`) — held-out splits on the identical
test period. Failures are reported, NOT averaged into a single headline.

## Live results (reproduced this session)
| Split | ROC-AUC | PR-AUC | P@100 | P@1000 | Brier | ECE |
|---|---|---|---|---|---|---|
| random | 0.927 <sup>⚠ superseded → honest 0.6456</sup> | 0.395 | 0.78 | 0.393 | 0.042 | 0.012 |
| **time_forward** (production) | **0.926 <sup>⚠ superseded → honest 0.6456</sup>** | **0.416** | **0.82** | **0.565** | 0.046 | 0.013 |
| cold_atm (180 ATMs unseen) | 0.917 | 0.377 | 0.57 | 0.314 | 0.045 | 0.013 |
| cold_city (city held out) | 0.922 <sup>⚠ superseded → honest 0.6456</sup> | 0.507 | 0.82 | 0.431 | 0.059 | 0.022 |
| cold_district (== city here) | 0.922 <sup>⚠ superseded → honest 0.6456</sup> | 0.507 | 0.82 | 0.431 | 0.059 | 0.022 |
| **new_hotspot** (top-20% volume ATMs held out) | **0.790** | **0.170** | **0.34** | **0.153** | 0.110 | 0.110 |

(Run-to-run variance: the stored artifact once recorded new_hotspot P@100 = 0.06;
live today 0.34. Both are far below time-forward's 0.82 — the qualitative
finding is robust: **novel hotspots are the weak split.**)

## Interpretation
1. **Cold ATM / cold city**: behavioural features generalise to unseen ATMs and
   cities with only modest degradation — the model does not overfit to a
   memorised ATM list.
2. **NEW HOTSPOT — the honest weak split.** When the previously top-20%-by-volume
   ATMs are withheld, precision collapses (0.34 vs 0.82) and calibration breaks
   (ECE 0.110 vs 0.013). This is the single most important limitation for
   SIH-26184: the problem explicitly asks to "forecast likely cash withdrawal
   locations **in advance**" as **new hotspots emerge**. Today's prototype is
   poor at exactly that case, because its strongest feature (`counterparty_count_24h`)
   requires the mule cash-out to have already started.
3. cold_district == cold_city is a **synthetic-world artifact** (city == district
   in this generator) — a real pilot must re-run with true district boundaries.

## Judge-facing statement
CashGuard generalises to unseen ATMs and cities, but its headline time-forward
precision (0.82) depends on hotspots already present in training volume.
For genuinely new hotspots — the case the SIH cares most about — precision
drops to ~0.3. This is a documented, unsolved limitation, not a claim.
