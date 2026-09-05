# FINAL_10_10_OPS_AND_SCALE.md — Uncertainty policy, feedback-loop, failure, scale


> **WARNING: DATA-LEAKAGE CORRECTION (2026-08-29)** - This document's reported ROC-AUC figures (~0.92x) came from a SAME-DAY LABEL-LEAKAGE bug in feature engineering (backend/ml/features.py, `_shift_day_past`), now fixed. The honest forecast-safe ROC-AUC is **0.6456** (leaky 0.9275 -> corrected 0.6344 in the proof). On calm days the live model scores every ATM low (max ~0.11) and produces **no alerts**; any populated high-risk alert view is the opt-in, clearly-labelled **"Load Simulated Scenario"** mode (SCRIPTED, not live model output). Treat all 0.92x figures in this doc as superseded. Full detail: MODEL_CARD.md, VERIFICATION_LOG.md (P1.5).
Covers Phase 11 (uncertainty/ACT/REVIEW/HOLD), 12 (PDP safety), 7
(feedback-loop), 15 (failure engineering) and 17 (scale) of the kill test.

## 1. Uncertainty / ACT-REVIEW-HOLD policy (stored `threshold_curve.json`)
Artifact-backed threshold curve over the chronological test set:

| Threshold | Alert rate | Precision | Recall | Tier |
|---|---|---|---|---|
| 0.50 | 1.72% | 0.554 | 0.154 | monitor |
| 0.60 | 1.31% | 0.590 | 0.125 | monitor |
| **0.70** | 1.02% | 0.624 | 0.103 | **action** |
| 0.80 | 0.73% | 0.690 | 0.082 | action |
| **0.85** | 0.60% | 0.721 | 0.070 | **dispatch** |
| 0.95 | 0.34% | 0.834 | 0.045 | dispatch |

Operational threshold stays 0.7 unless ops re-derives it on real data. Higher
thresholds trade recall for precision — the policy concentrates action on the
most confident ATMs. Sub-daily horizons are **HOLD** (see temporal doc); stale /
disagreeing / low-evidence cases are also HOLD (see response playbook).

## 2. PDP / human-gated safety (RESPONSE_PLAYBOOK + architecture)
- Every alert carries graded, advisory `recommended_actions` (notify → monitor →
  CCTV → verify). **No automated enforcement/freezing anywhere**; fund-block
  requires an explicit bank-officer `held`/`recovered` action.
- `recommended_recipients` resolves state → district → police-station → bank;
  notifications are simulated gateways, real API path.
- Transparency blocks: evidence panel, uncertainty, source tags, tamper-evident
  audit chain. Strongest output is a recommendation for a human, never an order.

## 3. Feedback-loop safety (architecture, verified in G-item work)
- The model **never consumes interventions/outcomes as features** and is not
  auto-retrained on its own actions → the risky "the model targets X, police
  act, model re-encodes police attention" loop cannot close.
- Concentration monitors (`backend/eval/fairness_check.py`) + repeated-targeting
  review triggers + randomized review sample guard against geographic feedback.
- Alert escalation timer (G2) is a bounded, ledger-logged scheduler action with
  HITL audit trail — not autonomous enforcement.

## 4. Failure engineering (stored artifacts + confirmed behavior)
- **Corrupt/missing model**: clean EOFError on load (no silent wrong output);
  DEMO_MODE serves everything from cache with no model loaded (read-only,
  auth still enforced).
- **Stale split cache**: fixed with TTL + single-flight + data stamps; verified
  byte-identical on hits, recomputes and changes payload on data drip.
- **DB unavailable**: clean 500s never fabricated data; DEMO_MODE serves the
  golden read-only path. PostgreSQL failover is documented PLANNED, not shipped.

## 5. Scale (stored `load_test.json`, honest demo-scale numbers)
- Sustained real-rate (8,000 complaints/day ≈ 1 per 10.7s): ingestion p50 28 ms,
  p95 66 ms per batch.
- Burst (200 records): p50 0.19 ms, p99 10 ms per record.
- Full scoring of 900 ATMs: p50 4.2 s, p99 ~6 s.
- Alert cycle ~7.8 s; 8 concurrent users OK.
- **Documented weakness**: SQLite single-process concurrency p95 ~72 s → the
  production path is PostgreSQL (PLANNED). Label explicitly: "DEMO-SCALE LOAD
  TEST — not a production benchmark."

## Bottom line
The loop is human-gated and feedback-safe by construction; failures degrade to
clean, cache-served states rather than wrong output; and the demo meets the real
8,000/day intake rate on the ingestion path while being honest that the serving
stack is demo-scale, with PostgreSQL as the documented production upgrade.
