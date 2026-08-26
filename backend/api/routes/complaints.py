"""
Complaint endpoints — NCRP portal query surface (role-scoped).
Filters: city / district / state / crime type / status / date window.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ... import repositories as repo
from ...database import get_db
from ...schemas import ComplaintOut
from ...security import require_auth

router = APIRouter(prefix="/complaints", tags=["complaints"])


@router.get("", response_model=list[ComplaintOut])
def list_complaints(
    city: str | None = None,
    district: str | None = None,
    state: str | None = None,
    complaint_type: str | None = Query(default=None, alias="type"),
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=100, le=20000),
    offset: int = 0,
    db: Session = Depends(get_db),
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN")),
):
    return repo.list_complaints(
        db,
        city=city, district=district, state=state, complaint_type=complaint_type,
        status=status, date_from=date_from, date_to=date_to,
        limit=limit, offset=offset, user=user,
    )