"""
Risk scoring endpoints — the predictive intelligence output (deliverable a).

GET /risk-scores   -> per-ATM P(fraud withdrawal in next 24h), role-scoped
GET /hotspots      -> top-K high-risk ATMs (filterable by city / time / category)

DEMO_MODE=true serves the pre-computed golden-path cache (fallback plan).
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
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


@router.get("/model/status")
def model_status(
    horizon: int = Query(default=24, ge=2, le=72, description="Forecast horizon the strip reflects"),
    as_of: str | None = Query(default=None, description="ISO datetime; set while replaying a historical day"),
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    """Model Status strip data: last inference run time, ATMs scored, current
    max/median risk — so a calm day renders as a legible, credible state.
    Read-only over the existing cached scoring path (no model changes)."""
    return services.get_model_status(db, user=user, horizon=horizon, as_of=as_of)


@router.get("/risk-scores", response_model=list[RiskScoreOut])
def risk_scores(
    city: str | None = None,
    as_of: str | None = Query(default=None, description="ISO datetime; defaults to simulated now"),
    horizon: int = Query(default=24, ge=2, le=72, description="Forecast horizon in hours: 2, 6, 12, 24, 48, 72"),
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    cached = services.read_demo_cache("risk-scores")
    if cached is not None:
        rows = cached if not city else [r for r in cached if r["city"] == city]
        rows = services._scope_risk_scores(rows, user)
        return rows
    ref = services.resolve_as_of(db, as_of)
    # Select model appropriate for the requested horizon
    scores = services.get_risk_scores(db, as_of=ref, city=city, user=user, horizon=horizon)
    return scores


@router.get("/threshold-explorer")
def threshold_explorer(user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN"))):
    """Precision-recall tradeoff explorer — artifact-backed curve from the
    held-out test split (scripts/threshold_curve.py). Not recomputed per
    request; the operational threshold stays 0.7 unless ops re-derives it."""
    import json as _json
    from ...eval.deep_evaluation import OUT

    path = OUT / "threshold_curve.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="threshold_curve.json missing - run scripts/threshold_curve.py")
    return _json.loads(path.read_text(encoding="utf-8"))


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