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
    alert = repo.get_alert(db, alert_id)
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
    alert = repo.get_alert(db, alert_id)
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
    alert = repo.get_alert(db, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return services.set_alert_status(db, alert, payload.status, user)