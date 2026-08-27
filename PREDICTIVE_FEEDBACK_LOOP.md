# PREDICTIVE_FEEDBACK_LOOP.md — Could CashGuard create a self-reinforcing policing loop?

## The loop we must detect and prevent
```
prediction → intervention → more observation at targeted sites
          → new data → retraining → stronger prediction at the same sites
```

A system that retrains on its own interventions silently amplifies whatever
it initially targeted — the classic predictive-policing feedback loop.

## Why this CANNOT happen in CashGuard (each point is code, not policy)

1. **Interventions are never features.** The model's features are complaints,
   withdrawals, mule-behaviour, and geography (`backend/ml/features.py`).
   Alert status, decisions, dispatch, and outcomes are stored in separate
   tables (`alerts`, `recovery_recommendations`, `AlertOutcome`) that the
   feature builder never reads. Grep-verified.
2. **No auto-retraining.** `POST /train` is I4C_ADMIN-only, manual, versioned,
   and requires a human decision. There is no scheduled retraining job that
   consumes outcomes. The closed loop (MODEL_OUTCOME_MONITOR.md) evaluates
   performance — it does not feed back into weights.
3. **Retraining would still not see interventions** (point 1), and the
   protocol (REAL_DATA_VALIDATION_PROTOCOL.md §14) pre-registers a rollback
   if outcome-calibration error rises.

## Safeguards (implemented)
- Minimum-evidence requirement → alerts below evidence 3/5 are HOLD ACTION.
- Uncertainty threshold → low-confidence forecasts never produce aggressive
  recommendations.
- Human review gate + mandatory reason for dismiss/escalate; every decision
  on the tamper-evident audit chain.
- **Repeat-targeting control**: per-district alert-share + Gini concentration
  monitor (`artifacts/fairness_report.json`); persistent domination triggers
  ops review, never automation.
- Group fairness audit re-run per artifact cycle: FPR flat 0.0015–0.0062
  across jurisdiction/complaint-area/ATM-volume groups (if the loop were
  forming, FPR or alert-rate divergence would appear first).
- **Exploration/review sampling**: the pilot protocol (Week 4) includes
  human-reviewed evaluation of alerts that were NOT acted on — a random
  review sample exists precisely to detect blind spots the model would never
  see in its own actioned-alert history.

## Honest limits
- On synthetic data the loop cannot be demonstrated end-to-end (no real
  interventions); the audit proves the *architecture* cannot close the loop.
- A real deployment must keep points 1–2 enforced in code review — the
  repo pins them in `backend/ml/features.py` with an inline comment warning
  against adding intervention features.