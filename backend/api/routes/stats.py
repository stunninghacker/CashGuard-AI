"""
I4C / Admin statistics endpoints — national aggregate view.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ... import services
from ...database import get_db
from ...schemas import SummaryStatsOut
from ...security import require_auth

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary", response_model=SummaryStatsOut)
def summary(db: Session = Depends(get_db), user=Depends(require_auth("I4C_ADMIN", "POLICE_STATE", "POLICE_DISTRICT"))):
    return services.summary_stats(db, user=user)