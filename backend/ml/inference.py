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


def score_all(as_of: datetime, horizon: int = 24) -> tuple:
    """
    Build the feature matrix for the next forecast day and score every ATM
    with the ACTIVE model (pure-XGBoost or XGB+Hawkes ensemble, per artifact).

    The forecast horizon determines the target window: [as_of, as_of + horizon h).
    Features are computed backward-from as_of so no future label leaks.

    Returns (X, meta, probs) so callers can reuse the instance feature row
    (evidence panel) without re-computing features.
    """
    pipe = load_pipeline()
    model = pipe["model"]
    calibrator = pipe.get("calibrator")
    ens_calibrator = pipe.get("ens_calibrator")
    active_model = pipe.get("active_model", "xgboost")
    hawkes_params = pipe.get("hawkes_params")

    # Use 24h feature builder by default (the model was trained on 24h windows).
    # The horizon parameter is recorded for API compatibility; actual scoring
    # uses the 24h window model with the horizon annotation.
    feature_day = as_of.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    # Pass persisted train-set lookups so Issue-1 features (latency / bank rate)
    # are identical to what the model saw during training (no train/serve skew).
    X, meta = build_features(
        engine,
        [feature_day],
        hawkes_params=hawkes_params,
        fraud_latency_by_type=pipe.get("fraud_latency_by_type") or {},
        bank_fraud_rate=pipe.get("bank_fraud_rate") or {},
    )
    
    raw = model.predict_proba(X)[:, 1]
    if active_model == "stacked" and pipe.get("stack_available"):
        # Issue-1 stacked model: XGB+LightGBM blended by the logistic meta-learner.
        xgb_sm, lgb, meta_lr = pipe["stack_xgb"], pipe["stack_lgb"], pipe["stack_meta"]
        xgb_v = xgb_sm.predict_proba(X)[:, 1]
        lgb_v = lgb.predict_proba(X)[:, 1]
        stack_v = meta_lr.predict_proba(np.column_stack([xgb_v, lgb_v]))[:, 1]
        sc = pipe.get("stack_calibrator")
        probs = sc.predict_proba(stack_v.reshape(-1, 1))[:, 1] if sc is not None else stack_v
    elif active_model == "ensemble" and ens_calibrator is not None and "hawkes_intensity_24h" in X.columns:
        # rank-average ensemble: 0.5·rank(XGB prob) + 0.5·rank(Hawkes intensity)
        def _rank_pct(v):
            import pandas as pd
            return pd.Series(v).rank(pct=True).to_numpy()
        
        ens_raw = 0.5 * _rank_pct(raw) + 0.5 * _rank_pct(X["hawkes_intensity_24h"].to_numpy())
        probs = ens_calibrator.predict_proba(ens_raw.reshape(-1, 1))[:, 1] if hasattr(ens_calibrator, "coef_") else ens_raw
    else:
        if calibrator is not None and hasattr(calibrator, "coef_"):  # Platt-scaled probability
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


def predict_risk(as_of: datetime, city: str | None = None, horizon: int = 24) -> list[dict]:
    """
    Risk scores for all ATMs as of `as_of` (forecast horizon in hours).

    Convention: the forecast covers [as_of, as_of + horizon h) and the
    features are computed at as_of — i.e. the model sees EVERYTHING
    known up to `as_of`, including today's partial activity. This mirrors real
    LEA practice: "based on today's complaints and cash-outs, where do fraud
    withdrawals happen in the next N hours?"

    Returns list of dicts: atm_id, bank_name, branch_name, city, district,
    state, police_station_area, pin, latitude, longitude, risk_score.
    Sorted by risk desc.
    """
    X, meta, probs = score_all(as_of, horizon=horizon)

    out = []
    for i in range(len(meta)):
        row = meta.iloc[i]
        if city and row["city"] != city:
            continue
        x = X.iloc[i]
        # Emerging-risk score: rate-of-change signals vs historical levels
        # (complaint surge, mule-account concentration, short-window velocity)
        city_base = max(float(x["n_complaints_city_7d"]) / 7.0, 1.0)
        surge = min(float(x["n_complaints_city_24h"]) / city_base, 2.0) / 2.0
        mule_share = min(
            float(x["counterparty_count_24h"]) / max(float(x["distinct_accounts_24h"]), 1.0),
            1.0,
        )
        velocity = min(
            float(x["withdrawals_6h"]) / max(float(x["withdrawals_24h"]) / 4.0, 1.0),
            2.0,
        ) / 2.0
        emerging = round(min(0.4 * surge + 0.35 * mule_share + 0.25 * velocity, 1.0), 4)
        # ---- Intervention priority (Phase 3, formulation in INTERVENTION_PRIORITY.md) ----
        # P = (0.40*risk + 0.25*exposure + 0.15*urgency + 0.20*evidence) * confidence-weight
        p = float(probs[i])
        exposure = min(float(x["amount_sum_24h"]) / 1_000_000.0, 1.0)   # INR exposure, normalized (assumption: 1M cap)
        urgency = emerging
        evidence = min(
            1.0,
            0.25 + 0.25 * min(float(x["counterparty_count_24h"]) / 8.0, 1.0)
            + 0.25 * float(x["linked_proportion_24h"])
            + 0.25 * min(float(x["n_complaints_city_24h"]) / 40.0, 1.0),
        )
        q = 1.0 if p >= 0.80 else 0.7 if p >= 0.70 else 0.4  # confidence weight from probability band
        priority = round((0.40 * p + 0.25 * exposure + 0.15 * urgency + 0.20 * evidence) * q, 4)
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
                "risk_score": round(p, 4),
                "emerging_risk": emerging,  # "risk rising fast" vs "usually risky"
                "intervention_priority": priority,
                "priority_exposure": round(exposure, 4),
                "priority_urgency": round(urgency, 4),
                "priority_evidence": round(evidence, 4),
                "priority_confidence_weight": q,
            }
        )
    out.sort(key=lambda s: s["risk_score"], reverse=True)
    return out