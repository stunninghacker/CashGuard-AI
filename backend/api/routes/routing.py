"""
Inter-agency jurisdiction routing endpoints (Item 4 / Issue 10).

POST /routing/handoff {alert_id}
    -> re-evaluate the jurisdiction for an existing alert; if the complaint
       origin state differs from the predicted-withdrawal (ATM) state, create /
       reuse a cross-state AlertHandoff, log it in the tamper-evident ledger,
       and return a routing_log describing which state-LEA inboxes were
       notified.

Honest scope: this mirrors the engine already wired into run_alert_cycle. It
does NOT call a real inter-agency gateway (documented Tier 2). If the current
synthetic data is intra-state (no cross-state mule movement), the handoff stays
empty and the endpoint reports exactly that — no fabricated routing.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ... import models
from ... import repositories as repo
from ...database import get_db
from ...routing import origin_state_for_atm, route_alert
from ...security import require_auth

router = APIRouter(prefix="/routing", tags=["jurisdiction-routing"])


class HandoffIn(BaseModel):
    alert_id: str


def _atm_payload_from_alert(db: Session, alert: models.Alert) -> dict | None:
    """Build the same ``{atm_id,state,city,district,police_station_area,...}``
    dict shape the alert engine feeds to the routing engine, from the alert's
    ATM row."""
    atm = repo.get_atm(db, alert.atm_id)
    if atm is None:
        return None
    return {
        "atm_id": atm.atm_id,
        "state": atm.state or "",
        "city": atm.city or "",
        "district": atm.district or "",
        "police_station_area": atm.police_station_area or "",
        "bank_name": atm.bank_name or "",
    }


@router.post("/handoff")
def handoff(
    payload: HandoffIn,
    user=Depends(require_auth("I4C_ADMIN", "POLICE_STATE", "POLICE_DISTRICT")),
    db: Session = Depends(get_db),
):
    alert = repo.get_alert(db, payload.alert_id, user=user)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    atm_payload = _atm_payload_from_alert(db, alert)
    origin = ""
    handoff_rec = None

    if atm_payload is None:
        routing_log = {
            "action": "no_atm",
            "origin_state": "",
            "receiving_state": alert.state,
            "handoff": None,
            "note": "ATM record missing; routing skipped.",
        }
        return {"alert_id": alert.alert_id, "routing_log": routing_log}

    origin = origin_state_for_atm(db, atm_payload)

    # Notify the origin jurisdiction's inbox regardless (provenance).
    if origin and origin != alert.state:
        handoff_rec = route_alert(db, alert)
        repo.store_inbox_message(db, channel="state_lea", payload={
            "handoff_id": handoff_rec.handoff_id if handoff_rec else None,
            "alert_id": alert.alert_id, "atm_id": alert.atm_id,
            "origin_state": origin, "receiving_state": alert.state,
            "message": f"Cross-state alert handed off from {origin} to {alert.state}",
        })
        if handoff_rec is not None:
            # mirror the routing status onto the alert (as the scheduler does)
            alert.routing_status = "handoff"
            db.commit()
        routing_log = {
            "action": "handoff_created",
            "origin_state": origin,
            "receiving_state": alert.state,
            "handoff_id": handoff_rec.handoff_id if handoff_rec else None,
            "status": handoff_rec.status if handoff_rec else None,
            "note": "Cross-state case routed to receiving state-LEA; origin retains provenance.",
        }
    else:
        routing_log = {
            "action": "intra_jurisdiction",
            "origin_state": origin or (alert.origin_state or ""),
            "receiving_state": alert.state,
            "handoff": None,
            "note": ("No cross-state movement detected; alert stays with its "
                     "current jurisdiction. (Synthetic data is intra-state, so "
                     "this is the honest expected outcome.)"),
        }

    return {"alert_id": alert.alert_id, "routing_log": routing_log}
