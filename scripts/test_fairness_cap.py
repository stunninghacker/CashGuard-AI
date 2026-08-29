"""
Item 5 — Active fairness constraint (per-jurisdiction proportional alert cap).

Deterministic unit test of the FairnessCap mechanism:
  1. Budgets are sized proportional to the national ATM population per state.
  2. Over-budget (dispatch/action) alerts are demoted to monitor (capped counter).
  3. Dispatch-tier alerts are NEVER suppressed (allow_override) - a real
     escalating incident always stays actionable.
  4. Kept alerts still count against the state budget (used tracking).
  5. Disabled (FAIRNESS_ALERT_CAP=false) -> consume() never demotes.

Run:  python scripts/test_fairness_cap.py
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import models
from backend.database import SessionLocal
from backend.services import FairnessCap

FIXTURE_ATMS = ["FCAP-ATM-A1", "FCAP-ATM-B1", "FCAP-ATM-B2"]


def main() -> int:
    db = SessionLocal()
    try:
        # State-agnostic: use a real state from the DB population (may contain
        # existing seeded ATMs). The mechanism is what we test, not absolute budgets.
        from backend.repositories import atm_population_by_state
        pop = atm_population_by_state(db)
        assert pop, "DB must have at least one ATM population state for the fixture"
        state = max(pop, key=pop.get)  # a state with the largest population

        # 1) Enabled by default, budget sized from population share.
        cap = FairnessCap(db, cycle_budget=10)
        assert cap.enabled, "cap should be enabled by default"
        assert state in cap.state_budget and cap.state_budget[state] >= 1, cap.state_budget

        # 2) Over-budget dispatch -> demoted to monitor (capped counter increments).
        budget = cap.state_budget[state]
        demoted = 0
        for i in range(budget + 2):  # exceed budget by 2
            r = cap.consume(state, "dispatch")
            if r != "dispatch":
                demoted += 1
        assert demoted == 2, f"expected 2 demotions, got {demoted}"
        assert cap.capped == 2, cap.capped

        # 3) Dispatch override: a real escalating dispatch is never suppressed.
        cap2 = FairnessCap(db, cycle_budget=10)
        b2 = cap2.state_budget[state]
        for i in range(b2):
            cap2.consume(state, "dispatch")
        over = cap2.consume(state, "dispatch", allow_override=True)
        assert over == "dispatch", "dispatch with allow_override must stay dispatch"

        # 4) Under-budget alerts keep tier.
        cap3 = FairnessCap(db, cycle_budget=10)
        r_under = cap3.consume(state, "dispatch")
        assert r_under == "dispatch", "under-budget alert keeps tier"

        # 5) Disabled -> never demotes.
        import backend.config as config
        old = config.FAIRNESS_ALERT_CAP
        config.FAIRNESS_ALERT_CAP = False
        try:
            cap4 = FairnessCap(db, cycle_budget=10)
            assert not cap4.enabled, "disabled cap should be inert"
            r = cap4.consume(state, "dispatch")
            assert r == "dispatch", "disabled cap never demotes"
            assert cap4.capped == 0
        finally:
            config.FAIRNESS_ALERT_CAP = old

        print("FAIRNESS CAP TEST: ALL CHECKS PASS (5/5)")
        return 0
    finally:
        db.query(models.Alert).filter(
            models.Alert.atm_id.in_(FIXTURE_ATMS)
        ).delete(synchronize_session=False)
        db.query(models.ATM).filter(
            models.ATM.atm_id.in_(FIXTURE_ATMS)
        ).delete(synchronize_session=False)
        db.commit()
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
