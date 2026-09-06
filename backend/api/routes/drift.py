"""
Feature-drift monitoring endpoints (Issue 11).

GET  /drift/status             -> green/yellow/red per-feature PSI vs reference
POST /drift/capture-reference  -> persist a reference distribution snapshot
POST /drift/check              -> run status + emit WS/inbox/ledger + retrain marker

Role-gated: capture/check are I4C-only (ops action); status is viewable by
I4C + POLICE (the dashboard surfaces green/yellow/red).
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ... import repositories as repo
from ...database import get_db
from ...ml import drift
from ...security import require_auth

router = APIRouter(prefix="/drift", tags=["drift-monitor"])

# Module-level singleton so the 600s cache persists across requests
_drift_monitor = drift.DriftMonitor()


class ReferenceIn(BaseModel):
    as_of: str | None = None


@router.get("/status")
def status(
    refresh: bool = Query(default=False),
    user=Depends(require_auth("I4C_ADMIN", "POLICE_STATE", "POLICE_DISTRICT")),
    db: Session = Depends(get_db),
):
    return _drift_monitor.status(db, refresh=refresh)


@router.post("/capture-reference")
def capture_reference(
    payload: ReferenceIn | None = None,
    user=Depends(require_auth("I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    as_of = None
    if payload and payload.as_of:
        try:
            as_of = datetime.fromisoformat(payload.as_of)
        except ValueError:
            as_of = None
    ref = drift.capture_reference(as_of)
    repo.append_ledger(db, actor=f"{user.user_id} ({user.role})",
                       event_type="drift_reference_captured",
                       entity_id="drift-reference",
                       payload={"as_of": ref["as_of"], "n_atms": ref["n_atms"],
                                "n_features": len(ref["features"])})
    db.commit()
    return {"captured": True, **ref}


@router.post("/check")
def check(
    user=Depends(require_auth("I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    if not drift.reference_exists():
        return {"status": "PENDING_REFERENCE",
                "note": "Capture a reference snapshot first (POST /drift/capture-reference)."}
    return _drift_monitor.check_and_alert(db, actor=f"{user.user_id} ({user.role})")
