# Phase 5 — Fairness Cap: Per-Jurisdiction Proportional Alert Budgeting

**Item 5** from the SIH specification — active fairness constraint gating. This is a
**scheduling constraint on alert pressure, not a model change**. It ensures no single
jurisdiction can monopolize the actionable (dispatch/action) alert queue.

## 1. Configuration

| Setting | Default | Description |
|---|---|---|
| `FAIRNESS_ALERT_CAP` | `true` (env) | Feature flag: `true` = enabled, `false` = disabled |
| `FAIRNESS_CAP_PREFERENCE` | `dispatch` | Which alerts keep high tier when budget exceeded: `dispatch` (highest-risk keep rank) or `action` |

Enable/disable via environment:
```bash
export FAIRNESS_ALERT_CAP="false"  # disable fairness cap
export FAIRNESS_CAP_PREFERENCE="action"  # alternative preference when capped
```

## 2. How It Works

### 2.1 Budget Allocation
Each state receives an alert budget **proportional to its share of the national ATM population**:

```
state_budget[state] = max(1, round(cycle_budget * n_atm_in_state / total_atm_national))
```

- Minimum budget of 1 alert per state (even if state has very few ATMs)
- Budgets computed once per alert cycle from the national ATM population

### 2.2 Consumption & Demotion
The `FairnessCap.consume(state, tier)` method records each alert against the state's budget:

| State of Budget | Tier | Action |
|---|---|---|
| Under budget | Any | Tier preserved as-is |
| At/over budget | `dispatch` or `action` | **Demoted to `monitor`** (review-only, no SMS/email dispatch push) |
| At/over budget | `monitor` | Tier preserved (already review-only) |
| At/over budget | Any | `allow_override=True` | Tier preserved (reserved for genuine escalating incidents) |

### 2.3 Intelligence Preservation
- Over-budget alerts are **still created** and ledger-logged
- They are **demoted to `monitor` tier** — intelligence is preserved, actionable push is suppressed
- A `capped` counter tracks how many alerts were demoted across the cycle
- Dismissed/escalated alerts still require a recorded reason (HITL constraint)

### 2.3 Example
```
Cycle budget: 100 alerts nationwide
State A ATM share: 15% → budget = 15 alerts
State A uses 15 alerts → budget exhausted
16th alert from State A → demoted from "dispatch" to "monitor"
16th alert from State A with allow_override=True → stays "dispatch" (genuine escalation)
```

## 3. Integration in Alert Cycle

The fairness cap is applied **after** deduplication and **before** SMS/email dispatch:

1. Compute risk scores (`get_risk_scores`)
2. Flag ATMs with `risk_score >= RISK_THRESHOLD` (default 0.70)
3. Deduplicate within cooldown window (`ALERT_COOLDOWN_HOURS`)
4. **Apply fairness cap** — `fairness.consume(state, proposed_tier)` for each flagged ATM
5. If demoted from `dispatch`/`action` to `monitor`:
   - Action message updated to: `FAIRNESS-CAPPED (per-jurisdiction cap) — MONITOR + review; [original action]`
   - SMS/email **suppressed** (no dispatch push)
   - Webhook dispatch **suppressed** (no CFCFRMS gateway push)
   - Alert still created with `tier="monitor"` and ledger-logged
6. If not demoted: normal dispatch pipeline (SMS, email, webhook, WS push)

### 3.1 Action Message Format
When an alert is fairness-capped:
```
action = f"FAIRNESS-CAPPED (per-jurisdiction cap) — MONITOR + review; {original_recommended_action}"
```

### 3.2 SHADOW_MODE Interaction
When `SHADOW_MODE=true`:
- All alerts are recorded only — no channels fire (SMS, email, dispatch)
- Fairness cap is still applied for budget tracking purposes
- `capped` counter still increments for auditability
- All predictions recorded for evaluation (no real-world impact)

## 4. Per-State Budget Sizes (Sample — based on national ATM distribution)

| State | ATM Count | Cycle Budget (if 100 alerts) | Per-Alert Fraction |
|---|---|---|---|
| Maharashtra | ~25 | 15 | 15% |
| Tamil Nadu | ~18 | 11 | 11% |
| Gujarat | ~14 | 8 | 8% |
| Delhi | ~10 | 6 | 6% |
| Karnataka | ~10 | 6 | 6% |
| West Bengal | ~8 | 5 | 5% |
| remaining states/UTs | ~53 | 30 | ~0.6% each |

*Exact sizes computed dynamically from live ATM population at each cycle.*

## 5. Honest Limits

- Budget proportions depend on **national ATM distribution** which may not reflect actual fraud distribution
- A state with few ATMs but high fraud rate could be **under-budgeted** — fairness cap may constrain necessary action
- The cap is **config-gated** (`FAIRNESS_ALERT_CAP`) — can be disabled for testing or high-volume periods
- `FAIRNESS_CAP_PREFERENCE` controls which alerts keep high tier: `dispatch` keeps the highest-risk alerts; `action` keeps more alerts at `action` tier
- **Intelligence is never lost**: over-budget alerts are demoted to `monitor` (review-only), not deleted
- **Real-world validation required**: fairness constraints should be tuned per program's cost-loss ratio and LEA capacity

## 5. Artifacts Generated

| File | Description |
|---|---|
| `artifacts/deep_eval/fairness_analysis.md` (planned) | Per-state budget sizes, demotion statistics, SHADOW_MODE interaction |
| `backend/services.py` | `FairnessCap` class implementation (lines 133-186) |
| `backend/services.py` | `run_alert_cycle()` fairness integration (lines 207-258) |
| `backend/config.py` | `FAIRNESS_ALERT_CAP`, `FAIRNESS_CAP_PREFERENCE` configuration |

**Phase 5 complete: fairness cap per-jurisdiction budgeting documented and implemented.**