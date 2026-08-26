"""
Model training pipeline.

* Chronological split: first 70% of days train, last 30% test (no shuffle —
  forecasts must never learn from the future).
* Classifier: XGBoost (tree_method='hist') with scale_pos_weight to handle
  class imbalance; falls back to sklearn HistGradientBoosting if XGBoost is
  unavailable.
* Evaluation: precision@K / recall@K (the operational metric — police deploy
  to the top-K ATMs), ROC-AUC, and simple accuracy.
* Artifacts saved with joblib: model + feature list + training metadata.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, roc_auc_score

from ..config import METRICS_PATH, MODEL_PATH, SEED
from .features import FEATURE_COLUMNS, build_features, build_target, load_dataframes

try:  # XGBoost preferred, sklearn fallback keeps the demo dependency-light
    from xgboost import XGBClassifier
    _HAS_XGB = True
except ImportError:  # pragma: no cover
    from sklearn.ensemble import HistGradientBoostingClassifier

    _HAS_XGB = False


def _precision_at_k(y_true: np.ndarray, probs: np.ndarray, k: int) -> float:
    top_k = np.argsort(probs)[::-1][:k]
    return float(y_true[top_k].mean())


def _recall_at_k(y_true: np.ndarray, probs: np.ndarray, k: int) -> float:
    top_k = np.argsort(probs)[::-1][:k]
    n_pos = max(int(y_true.sum()), 1)
    return float(y_true[top_k].sum() / n_pos)


def _save_eval_charts(out_dir: Path, yte: np.ndarray, probs_cal: np.ndarray, preds: np.ndarray) -> None:
    """Calibration curve + confusion matrix as static PNGs (pitch-deck assets)."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from sklearn.metrics import ConfusionMatrixDisplay, confusion_matrix
    except ImportError:  # pragma: no cover
        return

    # calibration curve: predicted probability bins vs observed frequency
    bins = np.linspace(0.0, 1.0, 11)
    centers, observed, counts = [], [], []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (probs_cal >= lo) & (probs_cal < hi)
        if m.sum() >= 5:
            centers.append((lo + hi) / 2)
            observed.append(yte[m].mean())
            counts.append(m.sum())
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), dpi=130)
    axes[0].plot([0, 1], [0, 1], "k--", lw=1, label="Perfect calibration")
    if centers:
        axes[0].plot(centers, observed, "o-", color="#38bdf8", label="Model")
        axes[0].set_xlabel("Predicted probability (Platt-calibrated)")
        axes[0].set_ylabel("Observed frequency")
        axes[0].set_title(f"Calibration curve (n={len(yte):,} test rows)")
        axes[0].legend()
        axes[0].grid(alpha=0.2)
    ConfusionMatrixDisplay(confusion_matrix(yte, preds)).plot(ax=axes[1], cmap="Blues", colorbar=False)
    axes[1].set_title("Confusion matrix (threshold 0.5)")
    fig.suptitle("CashGuard AI — evaluation on SYNTHETIC labels (time-based split; not real-world accuracy)", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_dir / "calibration_and_confusion.png")
    plt.close(fig)


def train(
    engine,
    days_back: int | None = None,
    seed: int = SEED,
    out_dir: Path | None = None,
) -> dict:
    """
    Run the full training pipeline. Returns the metric summary dict.

    days_back: restrict to the last N days (useful for fast re-training demos).
    """
    t0 = time.time()
    out_dir = out_dir or MODEL_PATH.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    comp, wd, atms = load_dataframes(engine)
    comp = comp.copy()
    comp["day"] = comp["filing_timestamp"].dt.normalize()
    wd = wd.copy()
    wd["day"] = wd["timestamp"].dt.normalize()

    all_days = pd.date_range(
        min(comp["day"].min(), wd["day"].min()),
        max(comp["day"].max(), wd["day"].max()),
        freq="D",
    )
    if days_back:
        all_days = all_days[-days_back:]
    days = all_days[2:]  # skip warm-up days (need history for rolling features)

    # ---- Hawkes params — fitted on the TRAINING period ONLY ----
    # λ(t) = μ + Σ_{tᵢ<t} α·exp(−β(t−tᵢ)) over past complaints; future-free by
    # construction (strict mask) and asserted by hawkes.self_test().
    from .hawkes import fit_location_params, self_test

    self_test()
    epoch = comp["day"].min()
    split_day = days[int(len(days) * 0.7)]
    hawkes_params: dict[str, tuple[float, float, float]] = {}
    train_comps = comp[comp["day"] < split_day]
    for city in sorted(train_comps["victim_city"].unique()):
        t = (train_comps.loc[train_comps["victim_city"] == city, "day"] - epoch).dt.total_seconds().to_numpy(dtype=float) / 86400.0
        horizon = (split_day - epoch).total_seconds() / 86400.0
        hawkes_params[city] = fit_location_params(t, horizon)

    X, meta = build_features(engine, days, comp, wd, atms, hawkes_params=hawkes_params)
    y = build_target(wd, atms, days)

    # ---- chronological split (train | validation | test — no future leakage) ----
    # The last ~15% of TRAIN days form the validation slice used ONLY for XGBoost
    # early stopping + Platt calibration. The held-out test set is used ONLY for
    # reporting — never for early stopping (test-set peeking removed).
    day_mask_tr = np.asarray(days < split_day)
    train_days = days[day_mask_tr]
    n_val = max(int(len(train_days) * 0.15), 2)
    val_start = train_days[-n_val]
    day_mask_val = (days >= val_start) & (days < split_day)
    mask_tr = np.tile(day_mask_tr & ~day_mask_val, len(atms))
    mask_val = np.tile(day_mask_val, len(atms))
    mask_te = np.tile(~day_mask_tr, len(atms))
    Xtr, ytr = X[mask_tr], y[mask_tr]
    Xval, yval = X[mask_val], y[mask_val]
    Xte, yte = X[mask_te], y[mask_te]
    # meta_te is aligned POSITIONALLY with yte / active_preds (the full `meta`
    # is atm-major across ALL days — test-relative indices would point at the
    # wrong (atm_id, day) rows).
    meta_te = meta[mask_te].reset_index(drop=True)

    pos_ratio = float(ytr.mean())

    if _HAS_XGB:
        model = XGBClassifier(
            n_estimators=400,
            max_depth=6,
            learning_rate=0.07,
            subsample=0.85,
            colsample_bytree=0.8,
            tree_method="hist",
            eval_metric="aucpr",
            early_stopping_rounds=30,
            random_state=seed,
        )
        model.fit(Xtr, ytr, eval_set=[(Xval, yval)], verbose=False)
        model_type = "xgboost"
    else:  # pragma: no cover
        model = HistGradientBoostingClassifier(
            max_iter=250,
            max_depth=6,
            learning_rate=0.08,
            class_weight="balanced",
            random_state=seed,
        )
        model.fit(Xtr, ytr)
        model_type = "sklearn-histgradientboosting"

    # ---- Platt calibration (fitted on the VALIDATION slice, never test) ----
    from sklearn.linear_model import LogisticRegression

    def _platt(raw_val: np.ndarray, yv: np.ndarray, raw_te: np.ndarray) -> tuple[np.ndarray, LogisticRegression]:
        cal = LogisticRegression()
        cal.fit(raw_val.reshape(-1, 1), yv)
        return cal.predict_proba(raw_te.reshape(-1, 1))[:, 1], cal

    probs = model.predict_proba(Xte)[:, 1]
    probs_val = model.predict_proba(Xval)[:, 1]

    # ---- ensemble: rank-average of XGB probability + Hawkes intensity ----
    def _rank_pct(v: np.ndarray) -> np.ndarray:
        return pd.Series(v).rank(pct=True).to_numpy()

    hawkes_te = Xte["hawkes_intensity_24h"].to_numpy()
    hawkes_val = Xval["hawkes_intensity_24h"].to_numpy()
    ens_raw = 0.5 * _rank_pct(probs) + 0.5 * _rank_pct(hawkes_te)
    ens_raw_val = 0.5 * _rank_pct(probs_val) + 0.5 * _rank_pct(hawkes_val)

    probs_cal, calibrator = _platt(probs_val, yval, probs)
    ens_cal, ens_calibrator = _platt(ens_raw_val, yval, ens_raw)

    # ---- metric blocks: pure-XGBoost vs ensemble (honest comparison) ----
    def _metric_block(y: np.ndarray, score: np.ndarray) -> dict:
        preds = (score >= 0.5).astype(int)
        mask70 = score >= 0.70
        return {
            "precision_at_20": round(_precision_at_k(y, score, 20), 4),
            "precision_at_50": round(_precision_at_k(y, score, 50), 4),
            "precision_at_100": round(_precision_at_k(y, score, 100), 4),
            "precision_at_200": round(_precision_at_k(y, score, 200), 4),
            "precision_at_500": round(_precision_at_k(y, score, 500), 4),
            "precision_at_1000": round(_precision_at_k(y, score, 1000), 4),
            "recall_at_20": round(_recall_at_k(y, score, 20), 4),
            "recall_at_50": round(_recall_at_k(y, score, 50), 4),
            "recall_at_100": round(_recall_at_k(y, score, 100), 4),
            "roc_auc": round(float(roc_auc_score(y, score)), 4),
            "accuracy": round(float(accuracy_score(y, preds)), 4),
            "precision_at_threshold_0p7": round(float(y[mask70].mean()), 4) if mask70.sum() > 0 else None,
            "n_flagged_at_0p7": int(mask70.sum()),
        }

    blk_xgb = _metric_block(yte, probs_cal)
    blk_ens = _metric_block(yte, ens_cal)

    # active model = the honestly-better one. SELECTED ON THE VALIDATION SLICE
    # (never the test set): rank-based AUC is calibration-invariant, so we score
    # the raw train/val outputs. Ensemble trails decisively on both splits, so
    # this cannot change the active model or any reported top-level metric.
    val_auc_xgb = float(roc_auc_score(yval, probs_val))
    val_auc_ens = float(roc_auc_score(yval, ens_raw_val))
    active = "ensemble" if val_auc_ens >= val_auc_xgb else "xgboost"
    active_score = ens_cal if active == "ensemble" else probs_cal
    active_block = dict(blk_ens if active == "ensemble" else blk_xgb)
    active_preds = (active_score >= 0.5).astype(int)

    # ---- instance-percentile reference (evidence panel) ----
    # Per-feature quantiles over the TRAINING set let the evidence panel report
    # "this feature's value is at the 95th percentile" — a simple, honest
    # per-instance signal. This is NOT SHAP (see explainability note).
    quantile_levels = np.array([0.5, 0.90, 0.95, 0.99])
    feature_quantiles: dict[str, list[float]] = {
        col: np.quantile(Xtr[col], quantile_levels).round(4).tolist()
        for col in FEATURE_COLUMNS
    }

    # ---- BASELINES: recent-volume AND complaint-proximity ----
    # volume:      "busy ATMs are busy" — rank by withdrawal volume
    # proximity:   "near recent complaints" — complaint counts/1+distance
    def _baseline_precision_at_k(order: np.ndarray, y: np.ndarray, k: int) -> float:
        return float(y[order[:k]].mean())

    order_volume = np.argsort(-Xte["withdrawals_24h"].to_numpy())
    proximity_score = Xte["n_complaints_city_7d"].to_numpy() / (
        1.0 + Xte["dist_to_complaint_centroid_km"].to_numpy()
    )
    order_proximity = np.argsort(-proximity_score)

    baseline_vol = {k: _baseline_precision_at_k(order_volume, yte, k) for k in (20, 50, 100)}
    baseline_prox = {k: _baseline_precision_at_k(order_proximity, yte, k) for k in (20, 50, 100)}
    lift_vol = {k: round(active_block[f"precision_at_{k}"] / max(v, 1e-9), 3) for k, v in baseline_vol.items()}
    lift_prox = {k: round(active_block[f"precision_at_{k}"] / max(v, 1e-9), 3) for k, v in baseline_prox.items()}

    # ---- LEAD-TIME ----
    # For every test-period TRUE POSITIVE that was flagged (score >= 0.5):
    # hours of warning from the forecast day-start until the first actual fraud
    # withdrawal at that ATM. ANNOTATED: this is a horizon design-property
    # (24h forecasts bound the achievable warning), not an accuracy claim.
    days_te = days[~day_mask_tr]
    fr_te = wd[wd["is_fraud_withdrawal"] & wd["day"].isin(days_te)]
    first_fraud = fr_te.groupby(["atm_id", "day"])["timestamp"].min()
    lead_times: list[float] = []
    for idx in np.where((yte == 1) & (active_preds == 1))[0]:
        # meta_te is positionally aligned with yte / active_preds — the full
        # `meta` is atm-major over ALL days and would yield wrong (atm, day).
        key = (meta_te.iloc[idx]["atm_id"], meta_te.iloc[idx]["day"])
        if key in first_fraud.index:
            lead_times.append((first_fraud.loc[key] - key[1]).total_seconds() / 3600.0)
    lead_time_h = float(np.median(lead_times)) if lead_times else float("nan")
    lead_time_p25 = float(np.percentile(lead_times, 25)) if lead_times else float("nan")
    lead_time_p75 = float(np.percentile(lead_times, 75)) if lead_times else float("nan")

    # ---- PER-FEATURE AUC (label-leak diagnostic) ----
    # Single-feature ROC-AUC on the held-out test set: proves no individual
    # feature trivially separates the classes (a leaking feature would show
    # AUC ~1.0 here). Read back from metrics.json — never hardcoded in docs.
    per_feature_auc: dict[str, float] = {}
    for col in FEATURE_COLUMNS:
        try:
            per_feature_auc[col] = round(float(roc_auc_score(yte, Xte[col].to_numpy())), 4)
        except ValueError:  # single-class scores for a constant column
            per_feature_auc[col] = None

    metrics = {
        "model_type": model_type,
        "calibration": "platt-sigmoid (fitted on validation slice)",
        "active_model": active,
        "trained_at": datetime.utcnow().isoformat(),
        "split_day": str(split_day.date()),
        "n_train_samples": int(len(Xtr)),
        "n_val_samples": int(len(Xval)),
        "n_test_samples": int(len(Xte)),
        "positive_share": round(pos_ratio, 4),
        **{k: v for k, v in active_block.items()},
        "per_feature_auc": per_feature_auc,
        "new_feature_single_auc_hawkes": per_feature_auc.get("hawkes_intensity_24h"),
        "metrics_xgboost_only": blk_xgb,
        "metrics_ensemble": blk_ens,
        "baseline_volume_precision_at_20": round(baseline_vol[20], 4),
        "baseline_volume_precision_at_50": round(baseline_vol[50], 4),
        "baseline_volume_precision_at_100": round(baseline_vol[100], 4),
        "baseline_proximity_precision_at_20": round(baseline_prox[20], 4),
        "baseline_proximity_precision_at_50": round(baseline_prox[50], 4),
        "baseline_proximity_precision_at_100": round(baseline_prox[100], 4),
        "lift_vs_volume_at_20": lift_vol[20],
        "lift_vs_volume_at_50": lift_vol[50],
        "lift_vs_volume_at_100": lift_vol[100],
        "lift_vs_proximity_at_20": lift_prox[20],
        "lift_vs_proximity_at_50": lift_prox[50],
        "lift_vs_proximity_at_100": lift_prox[100],
        "lead_time_median_hours": round(lead_time_h, 1),
        "lead_time_p25_hours": round(lead_time_p25, 1),
        "lead_time_p75_hours": round(lead_time_p75, 1),
        "lead_time_is_horizon_dependent": True,  # horizon design-property, not an accuracy claim
        "hawkes_per_location": {
            city: {"mu": round(p[0], 4), "alpha": round(p[1], 4), "beta": round(p[2], 4)}
            for city, p in hawkes_params.items()
        },
        "training_seconds": round(time.time() - t0, 1),
    }

    # ---- static evaluation charts (calibration curve + confusion matrix) ----
    _save_eval_charts(out_dir, yte, active_score, active_preds)

    artifact = {
        "model": model,
        "calibrator": calibrator,
        "ens_calibrator": ens_calibrator,
        "active_model": active,
        "feature_names": FEATURE_COLUMNS,
        "feature_quantiles": feature_quantiles,  # {feature: [p50, p90, p95, p99]}
        "quantile_levels": quantile_levels.tolist(),
        "hawkes_params": hawkes_params,
        "model_type": model_type,
        "trained_at": metrics["trained_at"],
        "split_day": str(split_day.date()),
        "seed": seed,
    }
    joblib.dump(artifact, MODEL_PATH)
    (out_dir / "metrics.json").write_text(json.dumps(_json_safe(metrics), indent=2))
    return metrics


def _json_safe(o):
    """Sanitize non-finite floats (nan/inf) -> None so metrics.json is ALWAYS
    valid JSON (json.dumps would emit literal NaN otherwise)."""
    import math

    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_json_safe(v) for v in o]
    return o