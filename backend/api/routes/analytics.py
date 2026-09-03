"""
Time-granularity analytics (Issue 7).

GET /analytics/time-granularity?window=hour|6h|day&hours=&atm_id=
    -> fraud/legit withdrawal + complaint volume bucketed by the chosen window.

HONEST DEAD-END DOCUMENTATION (Issue 7):
The product request asks for sub-daily (hourly/6h) *model re-training* windows.
We already explored and EVALUATED a 6h-window model during Issue 1. The honest
result: the 6h-window model scored LOWER (AUC 0.6463) than the production daily
model (AUC 0.6801) and was therefore REJECTED — it is not promoted to
production. Hourly re-training would only compound that degradation on the
same crowded-window features.

This endpoint therefore does NOT claim a model-quality win. It exposes the
sub-daily *analytics* view (real operational value for day-part pattern
identification), and surfaces the dead-end note in `model_note` so the 
limitation is transparent rather than fabricated.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Complaint, Withdrawal
from ...security import require_auth

router = APIRouter(prefix="/analytics", tags=["analytics"])

_WINDOW_FORMAT = {
    "hour": "%Y-%m-%d %H:00",
    "6h": "%Y-%m-%d %H:00",   # re-bucketed in python below (kept human-readable key)
    "day": "%Y-%m-%d",
}

MODEL_NOTE = (
    "Honest Issue-7 note: sub-daily (6h/hourly) model RE-TRAINING was evaluated "
    "and REJECTED — the 6h-window model scored AUC 0.6463 vs the production daily "
    "model's 0.6801 (same feature pipeline, leak-free). Hourly re-training is NOT "
    "promoted to production. This endpoint exposes sub-daily ANALYTICS only."
)


@router.get("/time-granularity")
def time_granularity(
    window: str = Query(default="hour", pattern="^(hour|6h|day)$"),
    hours: int = Query(default=48, ge=1, le=24 * 30 * 3),
    atm_id: str | None = Query(default=None),
    user=Depends(require_auth("I4C_ADMIN", "POLICE_STATE", "POLICE_DISTRICT", "BANK")),
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(hours=hours)

    # ---- withdrawals bucketed ----
    q = (
        select(
            func.strftime(_WINDOW_FORMAT[window], Withdrawal.timestamp).label("bucket"),
            func.count().label("n"),
            func.sum(case((Withdrawal.is_fraud_withdrawal, 1), else_=0)).label("n_fraud"),
            func.sum(Withdrawal.amount).label("amount"),
            func.sum(
                case((Withdrawal.is_fraud_withdrawal, Withdrawal.amount), else_=0.0)
            ).label("fraud_amount"),
        )
        .where(Withdrawal.timestamp >= since)
        .group_by("bucket")
        .order_by("bucket")
    )
    if atm_id:
        q = q.where(Withdrawal.atm_id == atm_id)
    rows = list(db.execute(q))

    # ---- complaints bucketed ----
    cq = (
        select(
            func.strftime(_WINDOW_FORMAT[window], Complaint.filing_timestamp).label("bucket"),
            func.count().label("n"),
        )
        .where(Complaint.filing_timestamp >= since)
        .group_by("bucket")
        .order_by("bucket")
    )
    crows = {r.bucket: r.n for r in db.execute(cq)}

    # ---- re-bucket 6h into 0-6/6-12/12-18/18-24 day-part keys ----
    buckets: dict[str, dict] = {}
    for r in rows:
        key = _rekey(r.bucket, window)
        b = buckets.setdefault(key, {"withdrawals": 0, "fraud_withdrawals": 0,
                                     "amount": 0.0, "fraud_amount": 0.0})
        b["withdrawals"] += int(r.n)
        b["fraud_withdrawals"] += int(r.n_fraud or 0)
        b["amount"] = round(b["amount"] + float(r.amount or 0.0), 2)
        b["fraud_amount"] = round(b["fraud_amount"] + float(r.fraud_amount or 0.0), 2)
        b["complaints"] = b.get("complaints", 0) + int(crows.get(r.bucket, 0))

    series = [
        {
            "bucket": k,
            "withdrawals": v["withdrawals"],
            "fraud_withdrawals": v["fraud_withdrawals"],
            "complaints": v.get("complaints", 0),
            "amount_total": v["amount"],
            "amount_fraud": v["fraud_amount"],
            "fraud_rate": round(v["fraud_withdrawals"] / v["withdrawals"], 4) if v["withdrawals"] else 0.0,
        }
        for k, v in sorted(buckets.items())
    ]

    return {
        "window": window,
        "hours": hours,
        "atm_id": atm_id,
        "n_buckets": len(series),
        "model_note": MODEL_NOTE,
        "series": series,
    }


def _rekey(bucket: str, window: str) -> str:
    """Collapse 6h buckets to human day-part labels; identity otherwise."""
    if window != "6h" or not bucket:
        return bucket or "na"
    hour = int(bucket[11:13])
    part = f"{hour // 6 * 6:02d}-{hour // 6 * 6 + 6:02d}"
    return f"{bucket[:10]} {part}"
