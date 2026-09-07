"""
Historical replay — one-click "Replay Historical High-Risk Day" (demo robustness).

Pure database analytics: finds the days with the most ACTUAL fraud withdrawals
(inside the caller's RBAC scope) and returns the `as_of` timestamp that lets the
LIVE model re-forecast that day through the existing `GET /risk-scores?as_of=`
parameter. Feature engineering stays strictly backward-looking from `as_of`, so
this is a genuine out-of-sample replay of the live model on historical synthetic
data — deliberately separate from the SCRIPTED `/simulated/scenario` walkthrough
and clearly labelled as such in the UI.

No model, threshold, or metric is modified by this module.
"""
from __future__ import annotations

from datetime import datetime, time as dtime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ... import models, repositories as repo
from ...database import get_db
from ...security import require_auth

router = APIRouter(tags=["replay"])


@router.get("/replay/high-risk-days")
def high_risk_days(
    limit: int = Query(default=5, ge=1, le=20),
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    """Days with the highest actual fraud-withdrawal volume (role-scoped), plus
    the `as_of` (end of the previous day) under which the live model's next-24h
    forecast covers that day."""
    day = func.date(models.Withdrawal.timestamp)

    atm_filter = repo._scoped_atm_stmt(user)
    atm_ids = select(models.ATM.atm_id)
    if atm_filter is not None:
        atm_ids = atm_ids.where(atm_filter)

    fraud_cnt = func.sum(case((models.Withdrawal.is_fraud_withdrawal.is_(True), 1), else_=0))
    fraud_amt = func.sum(case((models.Withdrawal.is_fraud_withdrawal.is_(True), models.Withdrawal.amount), else_=0.0))

    stmt = (
        select(
            day.label("d"),
            func.count(models.Withdrawal.id).label("total"),
            fraud_cnt.label("fraud"),
            fraud_amt.label("amount"),
        )
        .where(models.Withdrawal.atm_id.in_(atm_ids))
        .group_by(day)
        .order_by(fraud_cnt.desc(), fraud_amt.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()

    # Complaint counts per day for context (police + I4C only — BANK sees
    # complaints via evidence, not as a list, so it is not counted here).
    complaint_counts: dict[str, int] = {}
    if user.role != "BANK":
        cday = func.date(models.Complaint.filing_timestamp)
        cfilter = repo._scoped_complaint_stmt(user)
        cstmt = select(cday.label("d"), func.count(models.Complaint.complaint_id)).group_by(cday)
        if cfilter is not None:
            cstmt = cstmt.where(cfilter)
        complaint_counts = {str(d): int(c) for d, c in db.execute(cstmt).all()}

    days = []
    for d, total, fraud, amount in rows:
        d = str(d)
        try:
            peak = datetime.fromisoformat(d)
        except ValueError:
            continue
        # Model reference point: end of the PREVIOUS day, so the model's next-24h
        # forecast window covers the peak day using only prior data.
        as_of_dt = datetime.combine(peak.date() - timedelta(days=1), dtime(23, 59, 59))
        days.append({
            "date": d,
            "as_of": as_of_dt.isoformat(),
            "fraud_withdrawals": int(fraud or 0),
            "total_withdrawals": int(total or 0),
            "fraud_amount_inr": round(float(amount or 0.0), 2),
            "complaints_filed": complaint_counts.get(d, 0),
        })

    return {
        "days": days,
        "mode": "historical_replay",
        "live_model": True,
        "methodology_note": (
            "Replay runs the LIVE model via /risk-scores?as_of=<end of previous day>. "
            "Features are strictly backward-looking from that instant, so the model "
            "genuinely re-forecasts the next 24h of a historical high-risk day. "
            "This is NOT the scripted /simulated/scenario path."
        ),
        "scope_note": "Counts are within your role's jurisdiction.",
    }
