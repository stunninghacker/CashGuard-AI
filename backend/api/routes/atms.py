"""
ATM endpoints — bank network master data (role-scoped).
Also exposes the distinct bank list (Bank dashboard selector).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ... import repositories as repo
from ...database import get_db
from ...schemas import ATMOut
from ...security import require_auth

router = APIRouter(prefix="/atms", tags=["atms"])


@router.get("", response_model=list[ATMOut])
def list_atms(
    city: str | None = None,
    bank_name: str | None = None,
    limit: int = Query(default=1000, le=5000),
    offset: int = 0,
    db: Session = Depends(get_db),
    user=Depends(require_auth()),
):
    return repo.list_atms(db, city=city, bank_name=bank_name, limit=limit, offset=offset, user=user)


@router.get("/banks")
def list_banks(db: Session = Depends(get_db), user=Depends(require_auth())):
    """Distinct bank names — drives the Bank dashboard selector."""
    return {"banks": repo.list_banks(db)}