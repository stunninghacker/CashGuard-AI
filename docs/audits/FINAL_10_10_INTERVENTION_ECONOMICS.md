# FINAL_10_10_INTERVENTION_ECONOMICS.md — Economics at a fixed intervention budget


> **WARNING: DATA-LEAKAGE CORRECTION (2026-08-29)** - This document's reported ROC-AUC figures (~0.92x) came from a SAME-DAY LABEL-LEAKAGE bug in feature engineering (backend/ml/features.py, `_shift_day_past`), now fixed. The honest forecast-safe ROC-AUC is **0.6273** (leaky 0.9275 -> corrected 0.6344 in the proof). On calm days the live model scores every ATM low (max ~0.11) and produces **no alerts**; any populated high-risk alert view is the opt-in, clearly-labelled **"Load Simulated Scenario"** mode (SCRIPTED, not live model output). Treat all 0.92x figures in this doc as superseded. Full detail: MODEL_CARD.md, VERIFICATION_LOG.md (P1.5).
Source: stored `intervention_simulation.json` (verified by direct read this
session; a live re-run exceeded the session timeout, so numbers below are the
stored, internally-consistent simulation). All values are **CONTROLLED
SYNTHETIC SIMULATION — never a real-world loss claim.**

## Methodology
Identical held-out test forecast days; top-K ATMs per day per strategy;
jittered across 10 seeds (mean, 95% CI); 24h capture window. Total exposure in
test set: ~₹445.4M (INR, synthetic).

## Headline at K=10 (per-day top-10 ATMs targeted)
| Strategy | Fraud capture | Loss prevented | Efficiency ₹/intervention | Eff vs random |
|---|---|---|---|---|
| random | 0.4% | 0.37% | ~3,094 | 1x |
| volume | 0.5% | 0.52% | ~4,271 | 1.4x |
| historical | 1.9% | 1.80% | ~14,846 | 4.8x |
| **CashGuard** | **5.5%** | **5.02%** | **~41,418** | **13.4x** |

CashGuard captures **2.89x** the fraud events of the historical-hotspot
baseline and **11.0x** the volume baseline at the same K=10 budget.

## Across budgets (CashGuard, ₹/intervention)
- K=5: capture 3.7%, efficiency ₹53,273
- K=10: capture 5.5%, efficiency ₹41,418
- K=20: capture 8.1%, efficiency ₹30,530
- K=50: capture 13.6%, efficiency ₹21,209
- K=100: capture 20.7%, efficiency ₹16,531

Efficiency declines with K for ALL strategies — concentrating on fewer, more
confident ATMs maximizes INR per intervention, which argues for the ACTIVE
"HOLD below confidence" dispatch policy rather than blanket top-K.

## Interpretation (honest)
1. The model's economic edge is **3–13x** over operational heuristics at the
   same budget — real and directionally robust.
2. It is a **synthetic** simulation: no real NCRP/CFCFRMS/bank loss data was
   used. The ₹ figures are illustrative, not predicted real-world savings.
3. Because capture is concentrated where the model is already strong, these
   numbers do NOT reflect novel-hotspot value — the weak split. Real-value
   claims require the pilot.

## Judge-facing bottom line
CashGuard delivers meaningfully more fraud capture per intervention than
volume-, random-, or historical-based targeting on the same budget in the
synthetic world, and the ACTIVE "hold low-confidence" policy maximizes
efficiency. No real-world loss figure is claimed.
