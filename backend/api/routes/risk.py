"""
Risk scoring endpoints — the predictive intelligence output (deliverable a).

GET /risk-scores   -> per-ATM P(fraud withdrawal in next 24h), role-scoped
GET /hotspots      -> top-K high-risk ATMs (filterable by city / time / category)

DEMO_MODE=true serves the pre-computed golden-path cache (fallback plan).
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ... import repositories as repo, services
from ...database import get_db
from ...schemas import RiskScoreOut
from ...security import require_auth

router = APIRouter(tags=["risk"])


@router.get("/horizons")
def horizons(
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
):
    """Multi-horizon forecast confidence (2/6/12/24/48h) — CONTROLLED SYNTHETIC
    EVALUATION. Drives the dashboard's FORECAST HORIZON / MODEL CONFIDENCE panel."""
    import json

    from ...config import ARTIFACT_DIR

    path = ARTIFACT_DIR / "deep_eval" / "horizons.json"
    if not path.exists():
        return {"status": "missing", "note": "Run scripts/horizon_eval.py"}
    return json.loads(path.read_text())


@router.get("/risk-scores", response_model=list[RiskScoreOut])
def risk_scores(
    city: str | None = None,
    as_of: str | None = Query(default=None, description="ISO datetime; defaults to simulated now"),
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    cached = services.read_demo_cache("risk-scores")
    if cached is not None:
        rows = cached if not city else [r for r in cached if r["city"] == city]
        return rows
    ref = services.resolve_as_of(db, as_of)
    return services.get_risk_scores(db, as_of=ref, city=city, user=user)


@router.get("/hotspots", response_model=list[RiskScoreOut])
def hotspots(
    k: int = Query(default=20, ge=1, le=200),
    city: str | None = None,
    as_of: str | None = None,
    category: str | None = None,
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    ref = services.resolve_as_of(db, as_of)
    scores = services.get_risk_scores(db, as_of=ref, city=city, user=user)
    if category:
        # crime-category drill-down: keep ATMs whose recent complaint activity
        # matches the selected category (evidence-style scan)
        cat_cities = set(repo.complaint_cities_for_category(db, category, since=ref - timedelta(hours=24)))
        scores = [s for s in scores if s["city"] in cat_cities]
    return sorted(scores, key=lambda s: s["risk_score"], reverse=True)[:k]