"""
Alert endpoints — the actionable intelligence feed for LEAs and banks.

GET   /alerts                  -> alert list (role-scoped server-side)
POST  /alerts                  -> create an alert (scheduler / external trigger)
POST  /alerts/run-now          -> trigger an alert cycle immediately (demo)
GET   /alerts/{alert_id}       -> one alert
GET   /alerts/{alert_id}/evidence -> 3-field evidence panel + CFCFRMS freeze intel
POST  /alerts/{alert_id}/status  -> acknowledge / mark as actioned (ledger-logged)

DEMO_MODE=true serves the alert list from the pre-computed golden-path cache.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ... import repositories as repo, services
from ...database import get_db
from ...schemas import AlertCreateIn, AlertOut, AlertUpdateIn, EvidenceOut
from ...security import require_auth

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(
    status: str | None = None,
    atm_id: str | None = None,
    city: str | None = None,
    limit: int = 100,
    offset: int = 0,
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    cached = services.read_demo_cache("alerts")
    if cached is not None:
        rows = cached
        if status:
            rows = [r for r in rows if r["status"] == status]
        if atm_id:
            rows = [r for r in rows if r["atm_id"] == atm_id]
        if city:
            rows = [r for r in rows if r["city"] == city]
        return rows[:limit]
    return repo.list_alerts(db, status=status, atm_id=atm_id, city=city, limit=limit, offset=offset, user=user)


@router.post("", response_model=AlertOut)
def create_alert(
    payload: AlertCreateIn,
    user=Depends(require_auth("POLICE_STATE", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    """Create an alert directly (used by the scheduler / external systems)."""
    atm = repo.get_atm(db, payload.atm_id)
    if atm is None:
        raise HTTPException(status_code=404, detail=f"ATM {payload.atm_id} not found")
    # Jurisdiction write-check (red-team finding 3 / medium): a POLICE_STATE user may
    # only raise alerts for ATMs inside their own state. Previously any POLICE_STATE
    # scope could fabricate an alert for an out-of-jurisdiction ATM (mass/injection).
    if user.role == "POLICE_STATE" and (atm.state or "").lower() != (user.scope or "").lower():
        raise HTTPException(
            status_code=403,
            detail=f"ATM {payload.atm_id} is in state '{atm.state}' which is outside "
                   f"your jurisdiction '{user.scope}'",
        )
    alert = repo.create_alert(
        db,
        alert_id=f"ALT-{atm.atm_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        created_at=datetime.utcnow(),
        atm_id=atm.atm_id, bank_name=atm.bank_name, city=atm.city, district=atm.district,
        state=atm.state, police_station_area=atm.police_station_area,
        risk_score=payload.risk_score, recommended_action=payload.recommended_action,
        status=payload.status,
        sms_log="[mock] SMS queued via POST /alerts",
        email_log="[mock] Email queued via POST /alerts",
    )
    return alert


@router.post("/run-now")
def run_alerts_now(
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    """Force an alert cycle — used in the demo & tests."""
    summary = services.run_alert_cycle(db)
    return {"status": "ok", "summary": summary}


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: str, user=Depends(require_auth()), db: Session = Depends(get_db)):
    alert = repo.get_alert(db, alert_id, user=user)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return alert


@router.get("/{alert_id}/evidence", response_model=EvidenceOut)
def alert_evidence(
    alert_id: str,
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    """3-field evidence panel (complaint / withdrawal / context+disclosure)."""
    cached = services.read_demo_cache("evidence")
    if cached is not None and alert_id in cached:
        return cached[alert_id]
    alert = repo.get_alert(db, alert_id, user=user)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    try:
        return services.build_alert_evidence(db, alert)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{alert_id}/status", response_model=AlertOut)
def update_alert(
    alert_id: str,
    payload: AlertUpdateIn,
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    alert = repo.get_alert(db, alert_id, user=user)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    try:
        return services.set_alert_status(db, alert, payload.status, user, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/outcomes/list")
def list_outcomes(user=Depends(require_auth("I4C_ADMIN", "POLICE_STATE")), db: Session = Depends(get_db)):
    outcomes = repo.list_alert_outcomes(db, limit=200)
    return [
        {"alert_id": o.alert_id, "atm_id": o.atm_id, "predicted_risk": o.predicted_risk,
         "actual_fraud_happened": o.actual_fraud_happened, "prediction_error": o.prediction_error,
         "is_false_positive": o.is_false_positive, "is_false_negative": o.is_false_negative,
         "evaluated_at": o.evaluated_at.isoformat(), "model_version": o.model_version}
        for o in outcomes
    ]


@router.post("/outcomes/evaluate")
def evaluate_outcomes(user=Depends(require_auth("I4C_ADMIN")), db: Session = Depends(get_db)):
    """Evaluate pending alerts past their 24h horizon against observed outcomes."""
    n = services.evaluate_pending_outcomes(db)
    return {"evaluated": n, "monitoring": services.outcome_monitoring(db)}


@router.get("/outcomes/summary")
def outcome_summary(user=Depends(require_auth("I4C_ADMIN", "POLICE_STATE")), db: Session = Depends(get_db)):
    return services.outcome_monitoring(db)


# ---------------------------- Jurisdiction routing ---------------------------

class HandoffAckIn(BaseModel):
    status: str = "ack"          # ack | complete
    note: str = ""


@router.get("/handoffs/list")
def list_handoffs(
    status: str | None = None,
    limit: int = 200,
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN", "BANK")),
    db: Session = Depends(get_db),
):
    """Inter-agency jurisdiction handoff queue (Item 4).

    Cross-state cases: the predicted withdrawal state differs from the
    complainant-origin jurisdiction that seeded the risk. Role-scoped by
    jurisdiction (origin_state or receiving_state must match the caller's scope)."""
    from ... import routing

    handoffs = routing.list_handoffs(db, status=status, limit=limit)
    scope = (user.scope or "").lower()
    rows = []
    for h in handoffs:
        if user.role == "I4C_ADMIN":
            visible = True
        elif user.role == "BANK":
            visible = False  # banks see their alert, not inter-agency handoff queue
        else:
            # police see handoffs touching their state (origin or receiving)
            visible = scope in (h.origin_state or "").lower() or scope in (h.receiving_state or "").lower()
        if visible:
            rows.append({
                "handoff_id": h.handoff_id, "alert_id": h.alert_id, "atm_id": h.atm_id,
                "origin_state": h.origin_state, "receiving_state": h.receiving_state,
                "status": h.status, "reason": h.reason,
                "created_at": h.created_at.isoformat(), "ack_by": h.ack_by,
                "ack_at": h.ack_at.isoformat() if h.ack_at else None, "note": h.note,
            })
    return {"total": len(rows), "handoffs": rows}


@router.post("/handoffs/{handoff_id}/ack")
def ack_handoff(
    handoff_id: str,
    payload: HandoffAckIn,
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    """Acknowledge / complete a handoff from the receiving state-LEA queue."""
    from ... import routing

    h = routing.ack_handoff(db, handoff_id, actor=f"{user.role}:{user.scope}",
                            complete=(payload.status == "complete"), note=payload.note)
    if h is None:
        raise HTTPException(status_code=404, detail=f"Handoff {handoff_id} not found")
    return {"handoff_id": h.handoff_id, "status": h.status, "ack_by": h.ack_by}