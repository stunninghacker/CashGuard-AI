"""
Mobile / field-geolocation endpoint (Issue 8).

GET /mobile/nearby?lat=&lon=&max_km=&limit=5
    -> top-`limit` (default 5) highest-actionability ATMs near the caller's GPS
       fix, ranked by a transparent composite of risk + proximity.

Ranking is explicit (not a black box):
    mobile_score = 0.6 * risk_norm + 0.4 * proximity_norm
where risk_norm is the model risk score and proximity_norm = 1 / (1 + km) so a
closer, high-risk ATM ranks above a far high-risk one. This is what a field
officer needs on a phone: "the 5 AKT (actionable) ATMs around me, safest-effort
right now."

Honest scope: distance is great-circle (haversine) to the ATM's stored lat/lon;
`max_km` filters to a search radius. Sorted by mobile_score desc.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ... import services
from ...database import get_db
from ...security import require_auth

router = APIRouter(prefix="/mobile", tags=["mobile"])


@router.get("/nearby")
def nearby(
    lat: float = Query(..., ge=-90, le=90, description="Caller latitude (GPS)"),
    lon: float = Query(..., ge=-180, le=180, description="Caller longitude (GPS)"),
    max_km: float = Query(default=25.0, ge=0.5, le=500.0),
    limit: int = Query(default=5, ge=1, le=20),
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    scores = services.get_risk_scores(db, user=user)

    scored = []
    for s in scores:
        if s.get("latitude") is None or s.get("longitude") is None:
            continue
        km = services._haversine_km(s["latitude"], s["longitude"], lat, lon)
        if km > max_km:
            continue
        risk_norm = max(float(s["risk_score"]), 0.0)
        proximity_norm = 1.0 / (1.0 + km)
        mobile_score = round(0.6 * risk_norm + 0.4 * proximity_norm, 4)
        scored.append({
            "atm_id": s["atm_id"],
            "bank_name": s.get("bank_name"),
            "branch_name": s.get("branch_name"),
            "city": s.get("city"),
            "district": s.get("district"),
            "state": s.get("state"),
            "police_station_area": s.get("police_station_area"),
            "distance_km": round(km, 2),
            "risk_score": s.get("risk_score"),
            "risk_level": services._risk_level(s.get("risk_score", 0.0)),
            "mobile_score": mobile_score,
        })

    scored.sort(key=lambda x: x["mobile_score"], reverse=True)
    return {
        "lat": lat,
        "lon": lon,
        "max_km": max_km,
        "found": len(scored),
        "returned": min(len(scored), limit),
        "ranking": "0.6*risk + 0.4*(1/(1+km)) — explicit composite",
        "atms": scored[:limit],
    }
