"""
Canonical metrics endpoint — serves artifacts/current_metrics.json as the
single source of truth for all current model metrics.
"""
from __future__ import annotations

import json

from fastapi import APIRouter
from pathlib import Path

router = APIRouter(prefix="/metrics", tags=["metrics"])

_METRICS_FILE = Path(__file__).resolve().parent.parent.parent.parent / "artifacts" / "current_metrics.json"


@router.get("/current")
def current_metrics():
    """Return the canonical current metrics JSON (single source of truth)."""
    if _METRICS_FILE.exists():
        return json.loads(_METRICS_FILE.read_text())
    return {"error": "current_metrics.json not found", "status": "missing"}
