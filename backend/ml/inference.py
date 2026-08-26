"""
Inference — live risk scoring.

predict_risk(as_of) computes P(fraud withdrawal in next 24h) for every ATM
using only data available BEFORE `as_of`, then joins ATM metadata so the
dashboard can render the heatmap without further lookups.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import joblib
import numpy as np

from ..config import MODEL_PATH
from ..database import engine
from .features import FEATURE_COLUMNS, build_features

_pipeline: dict[str, Any] | None = None


def load_pipeline() -> dict[str, Any]:
    """Load (and cache) the trained artifact bundle."""
    global _pipeline
    if _pipeline is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model artifact not found at {MODEL_PATH}. Run: python scripts/train_model.py"
            )
        _pipeline = joblib.load(MODEL_PATH)
    return _pipeline


def score_all(as_of: datetime) -> tuple:
    """
    Build the feature matrix for the next forecast day and score every ATM
    with the ACTIVE model (pure-XGBoost or XGB+Hawkes ensemble, per artifact).

    Returns (X, meta, probs) so callers can reuse the instance feature row
    (evidence panel) without re-computing features.
    """
    pipe = load_pipeline()
    model = pipe["model"]
    calibrator = pipe.get("calibrator")
    ens_calibrator = pipe.get("ens_calibrator")
    active_model = pipe.get("active_model", "xgboost")
    hawkes_params = pipe.get("hawkes_params")

    feature_day = as_of.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    X, meta = build_features(engine, [feature_day], hawkes_params=hawkes_params)
    raw = model.predict_proba(X)[:, 1]
    if active_model == "ensemble" and ens_calibrator is not None and "hawkes_intensity_24h" in X.columns:
        # rank-average ensemble: 0.5·rank(XGB prob) + 0.5·rank(Hawkes intensity)
        def _rank_pct(v):
            import pandas as pd

            return pd.Series(v).rank(pct=True).to_numpy()

        ens_raw = 0.5 * _rank_pct(raw) + 0.5 * _rank_pct(X["hawkes_intensity_24h"].to_numpy())
        probs = ens_calibrator.predict_proba(ens_raw.reshape(-1, 1))[:, 1]
    else:
        if calibrator is not None:  # Platt-scaled probability
            probs = calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]
        else:  # backward-compatible with uncalibrated artifacts
            probs = raw
    return X, meta, probs


def shap_contributions(feature_row) -> list[dict]:
    """
    Per-instance SHAP contributions for ONE row, via XGBoost's native
    pred_contribs (no new dependency). Returns the top-5 features by |SHAP|
    with their values, labelled per-instance.
    """
    pipe = load_pipeline()
    model = pipe["model"]
    try:
        import xgboost as xgb

        dmat = xgb.DMatrix(feature_row.to_frame().T, feature_names=pipe["feature_names"])
        contribs = model.get_booster().predict(dmat, pred_contribs=True)[0]
    except Exception:  # pragma: no cover - sklearn fallback path
        return []
    names = list(pipe["feature_names"]) + ["bias"]
    out = []
    for name, value, contrib in zip(names, feature_row.to_numpy().tolist(), contribs.tolist()):
        if name == "bias":
            continue
        out.append({"feature": name, "value": round(float(value), 4), "shap": round(float(contrib), 4)})
    out.sort(key=lambda c: -abs(c["shap"]))
    return out[:5]


def predict_risk(as_of: datetime, city: str | None = None) -> list[dict]:
    """
    Risk scores for all ATMs as of `as_of` (next 24h horizon).

    Convention: the forecast covers [next_midnight, next_midnight + 24h) and the
    features are computed at next_midnight — i.e. the model sees EVERYTHING
    known up to `as_of`, including today's partial activity. This mirrors real
    LEA practice: "based on today's complaints and cash-outs, where do fraud
    withdrawals happen tomorrow?"

    Returns list of dicts: atm_id, bank_name, branch_name, city, district,
    state, police_station_area, pin, latitude, longitude, risk_score.
    Sorted by risk desc.
    """
    _, meta, probs = score_all(as_of)

    out = []
    for i in range(len(meta)):
        row = meta.iloc[i]
        if city and row["city"] != city:
            continue
        out.append(
            {
                "atm_id": row["atm_id"],
                "bank_name": row["bank_name"],
                "branch_name": row["branch_name"],
                "city": row["city"],
                "district": row["district"],
                "state": row["state"],
                "pin": row["pin"],
                "police_station_area": row["police_station_area"],
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "risk_score": round(float(probs[i]), 4),
            }
        )
    out.sort(key=lambda s: s["risk_score"], reverse=True)
    return out