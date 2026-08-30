"""
Withdrawal endpoints — bank transaction feed (role-scoped).
Filters: ATM / account token / fraud-only / date window.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ... import repositories as repo
from ...database import get_db
from ...schemas import WithdrawalOut
from ...security import require_auth

router = APIRouter(prefix="/withdrawals", tags=["withdrawals"])


@router.get("", response_model=list[WithdrawalOut])
def list_withdrawals(
    atm_id: str | None = None,
    account_token: str | None = None,
    fraud_only: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
):
    return repo.list_withdrawals(
        db,
        atm_id=atm_id, account_token=account_token, fraud_only=fraud_only,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset,
        user=user,  # RBAC bank-scoping (red-team finding 2)
    )