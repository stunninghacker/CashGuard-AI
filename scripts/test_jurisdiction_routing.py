"""
Item 4 — Inter-agency jurisdiction routing: repeatable unit test.

Proves the routing MECHANISM (handoff creation, ack, idempotency) on controlled
cross-state fixtures, independent of whether the current synthetic production
data is intra-state. Cleans up all fixtures unconditionally.

Run:  python scripts/test_jurisdiction_routing.py
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from backend import models
from backend.database import SessionLocal
from backend.routing import ack_handoff, route_alert

FIXTURE_IDS = ["RT-INTRA-1", "RT-XSTATE-1", "RT-XSTATE-2"]


def make_alert(aid: str, state: str, origin: str) -> models.Alert:
    return models.Alert(
        alert_id=aid, created_at=datetime.utcnow(), atm_id=aid.replace("RT-", "ATM-"),
        city="TestCity", bank_name="TestBank", district="TestDistrict",
        state=state, origin_state=origin, risk_score=0.9, tier="dispatch",
    )


def main() -> int:
    db = SessionLocal()
    try:
        # 1) intra-state -> no handoff
        al1 = make_alert("RT-INTRA-1", "State-A", "State-A")
        db.add(al1); db.commit()
        assert route_alert(db, al1) is None, "intra-state should not hand off"

        # 2) cross-state -> handoff queued
        al2 = make_alert("RT-XSTATE-1", "State-B", "State-C")
        db.add(al2); db.commit()
        h2 = route_alert(db, al2)
        assert h2 is not None
        assert (h2.origin_state, h2.receiving_state, h2.status) == ("State-C", "State-B", "queued")

        # 3) ack-complete mirrors routing_status onto the alert
        h2 = ack_handoff(db, h2.handoff_id, actor="POLICE:state-b", complete=True, note="received")
        assert h2.status == "complete"
        al2b = db.query(models.Alert).filter_by(alert_id="RT-XSTATE-1").first()
        assert al2b.routing_status == "handoff_complete"

        # 4) idempotent
        n = db.query(models.AlertHandoff).filter_by(alert_id="RT-XSTATE-1").count()
        route_alert(db, al2b)
        n2 = db.query(models.AlertHandoff).filter_by(alert_id="RT-XSTATE-1").count()
        assert n == n2 == 1, "route_alert must not duplicate handoffs"

        print("JURISDICTION ROUTING TEST: ALL CHECKS PASS (4/4)")
        return 0
    finally:
        for aid in FIXTURE_IDS:
            db.query(models.Alert).filter_by(alert_id=aid).delete()
            db.execute(text("DELETE FROM alert_handoffs WHERE alert_id=:a"), {"a": aid})
        db.commit()
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())