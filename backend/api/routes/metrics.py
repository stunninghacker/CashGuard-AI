"""
Canonical metrics endpoint — serves artifacts/current_metrics.json as the
single source of truth for all current model metrics.
"""
from __future__ import annotations

import json

from fastapi import APIRouter
from pathlib import Path

router = APIRouter(prefix="/metrics", tags=["metrics"])

_ARTIFACT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "artifacts"
_METRICS_FILE = _ARTIFACT_DIR / "current_metrics.json"
_TRAIN_METRICS_FILE = _ARTIFACT_DIR / "metrics.json"


@router.get("/current")
def current_metrics():
    """Return the canonical current metrics JSON (single source of truth)."""
    data = {}
    if _METRICS_FILE.exists():
        data = json.loads(_METRICS_FILE.read_text())
    else:
        return {"error": "current_metrics.json not found", "status": "missing"}
    if _TRAIN_METRICS_FILE.exists():
        try:
            train = json.loads(_TRAIN_METRICS_FILE.read_text())
            if "per_feature_auc" in train:
                data["feature_importances"] = train["per_feature_auc"]
        except Exception:
            pass
    return data
