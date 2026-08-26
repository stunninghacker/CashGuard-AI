"""
Training endpoint — retrain the model on demand (I4C_ADMIN only).
In production, retraining would be a scheduled/CI job; this endpoint exists
so the hackathon demo can show the training pipeline live.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...config import METRICS_PATH
from ...database import engine, get_db
from ...ml.train import train
from ...schemas import TrainResponse
from ...security import require_auth

router = APIRouter(prefix="/train", tags=["train"])


@router.get("/status")
def train_status(user=Depends(require_auth())):
    """Last training run's metrics."""
    if METRICS_PATH.exists():
        return {"status": "ok", "metrics": json.loads(METRICS_PATH.read_text())}
    return {"status": "not_trained", "metrics": None}


@router.post("", response_model=TrainResponse)
def train_model(
    days_back: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_auth("I4C_ADMIN")),
):
    try:
        metrics = train(engine, days_back=days_back)
        return TrainResponse(status="ok", message="Model retrained successfully", metrics=metrics)
    except Exception as exc:  # pragma: no cover
        return TrainResponse(status="error", message=str(exc), metrics=None)