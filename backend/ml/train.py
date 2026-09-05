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
from .features import (
    FEATURE_COLUMNS,
    build_features,
    build_target,
    load_dataframes,
)

try:  # XGBoost preferred, sklearn fallback keeps the demo dependency-light
    from xgboost import XGBClassifier
    _HAS_XGB = True
except ImportError:  # pragma: no cover
    from sklearn.ensemble import HistGradientBoostingClassifier

    _HAS_XGB = False

try:  # LightGBM second base learner for the stacked ensemble
    from lightgbm import LGBMClassifier, early_stopping
    _HAS_LGB = True
except ImportError:  # pragma: no cover
    _HAS_LGB = False

try:  # SMOTE-Tomek (train-only resampling) — installed as imbalanced-learn
    from imblearn.combine import SMOTETomek
    _HAS_SMOTE = True
except ImportError:  # pragma: no cover
    _HAS_SMOTE = False

from sklearn.linear_model import LogisticRegression


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
    pos_weight_multiplier: float = 1.0,
) -> dict:
    """
    Run the full training pipeline. Returns the metric summary dict.

    days_back: restrict to the last N days (useful for fast re-training demos).
    pos_weight_multiplier: up-weights the rare positive class relative to the
      natural imbalance ratio. >1.0 trades some precision for higher recall at
      any fixed threshold (P1.5 recall tuning). 1.0 == XGBoost's auto balance.
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

    # ---- Issue-1 NEW lookups — computed on the TRAINING period ONLY so the
    # latency / bank-rate features never observe a test-window label. ----
    train_wd = wd[wd["day"] < split_day].merge(atms[["atm_id", "city", "bank_name"]], on="atm_id", how="left")
    fraud_train = train_wd[train_wd["is_fraud_withdrawal"]].copy()

    # fraud_latency_by_type: for each complaint (train), days until the NEXT
    # fraud withdrawal in the SAME city; median per complaint type. City-level
    # linkage is a deliberate, leak-free proxy (no complaint<->withdrawal FK).
    fraud_latency_by_type: dict[str, float] = {}
    if len(fraud_train) and "victim_city" in comp.columns:
        fw = fraud_train[["city", "timestamp"]].rename(columns={"timestamp": "f_ts"}).dropna(subset=["city"])
        comp_city = comp[comp["day"] < split_day][["victim_city", "complaint_type", "filing_timestamp"]].rename(
            columns={"victim_city": "city"}
        ).dropna(subset=["city"])
        if len(comp_city) and len(fw):
            # next fraud at/after each complaint within the same city (train only)
            merged = pd.merge_asof(
                comp_city.sort_values("filing_timestamp"),
                fw.sort_values("f_ts"),
                left_on="filing_timestamp",
                right_on="f_ts",
                by="city",
                direction="forward",
            )
            merged["latency_days"] = (merged["f_ts"] - merged["filing_timestamp"]).dt.total_seconds() / 86400.0
            merged = merged[merged["latency_days"] > 0]
            if len(merged):
                fraud_latency_by_type = {
                    t: float(g.median())
                    for t, g in merged.groupby("complaint_type")["latency_days"]
                    if len(g) > 0
                }

    # bank_fraud_rate: historical fraud proportion per bank (train only).
    bank_fraud_rate: dict[str, float] = {}
    total_by_bank = train_wd.groupby("bank_name").size()
    fraud_by_bank = train_wd[train_wd["is_fraud_withdrawal"]].groupby("bank_name").size()
    for b in total_by_bank.index:
        t = total_by_bank.get(b, 0)
        bank_fraud_rate[b] = fraud_by_bank.get(b, 0) / t if t else 0.0

    X, meta = build_features(
        engine,
        days,
        comp,
        wd,
        atms,
        hawkes_params=hawkes_params,
        fraud_latency_by_type=fraud_latency_by_type,
        bank_fraud_rate=bank_fraud_rate,
    )
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
    # P1.5: explicit positive-class weight = natural imbalance ratio x a knob.
    # At multiplier==1.0 we pass None so XGBoost uses its exact original
    # auto-balance -> bit-for-bit preserves the verified baseline. Only when
    # up-weighting (>1.0) do we supply an explicit scale_pos_weight, recording
    # the real P/R/F1 trade-off in metrics.json (never presumed).
    p0 = max(float((ytr == 0).sum()), 1.0)
    p1 = max(float((ytr == 1).sum()), 1.0)
    scale_pos_weight = (p0 / p1) * max(pos_weight_multiplier, 0.1)
    xgb_scale = None if pos_weight_multiplier == 1.0 else scale_pos_weight

    if _HAS_XGB:
        model = XGBClassifier(
            n_estimators=400,
            max_depth=6,
            learning_rate=0.07,
            subsample=0.85,
            colsample_bytree=0.8,
            tree_method="hist",
            scale_pos_weight=xgb_scale,
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
    def _platt(raw_val: np.ndarray, yv: np.ndarray, raw_te: np.ndarray) -> tuple[np.ndarray, LogisticRegression]:
        cal = LogisticRegression()
        if len(np.unique(yv)) < 2:
            # Single-class validation set — skip calibration, return raw probs
            return raw_te, LogisticRegression()
        cal.fit(raw_val.reshape(-1, 1), yv)
        return cal.predict_proba(raw_te.reshape(-1, 1))[:, 1], cal

    probs = model.predict_proba(Xte)[:, 1]
    probs_val = model.predict_proba(Xval)[:, 1]
    probs_cal, calibrator = _platt(probs_val, yval, probs)
    # BEFORE (baseline) AUC: the single XGBoost trained on the RAW train set —
    # this is the honest reference point the Issue-1 changes must beat.
    auc_before = float(roc_auc_score(yte, probs)) if len(np.unique(yte)) >= 2 else 0.5

    # ---- Issue-1: stacked ensemble (XGB + LightGBM) on a SMOTE-Tomek
    # resampled TRAINING set, blended by a logistic meta-learner. ----
    # SMOTE-Tomek is applied ONLY to the train slice (never val/test) so it
    # cannot leak; the meta-learner is fit on the VALIDATION slice only.
    stack_available = _HAS_LGB and _HAS_SMOTE
    used_smote = False
    Xtr_fit, ytr_fit = Xtr, ytr
    if stack_available and _HAS_SMOTE:
        smote = SMOTETomek(random_state=seed)
        Xtr_fit, ytr_fit = smote.fit_resample(Xtr, ytr)
        used_smote = True

    stack_raw = av_before = None
    if stack_available:
        lgb = LGBMClassifier(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            num_leaves=31,
            subsample=0.85,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            random_state=seed,
            verbosity=-1,
        )
        # early stopping for LGB
        lgb.fit(
            Xtr_fit, ytr_fit,
            eval_set=[(Xval, yval)],
            eval_metric="auc",
            callbacks=[__import__("lightgbm").early_stopping(30, verbose=False)],
        )
        lgb_val = lgb.predict_proba(Xval)[:, 1]
        lgb_te = lgb.predict_proba(Xte)[:, 1]

        # xgb_sm: XGBoost retrained on the resampled train (no separate object
        # to keep weights; reuse scale_pos_weight behavior).
        xgb_sm = XGBClassifier(
            n_estimators=400,
            max_depth=6,
            learning_rate=0.07,
            subsample=0.85,
            colsample_bytree=0.8,
            tree_method="hist",
            scale_pos_weight=xgb_scale,
            eval_metric="aucpr",
            early_stopping_rounds=30,
            random_state=seed,
        )
        xgb_sm.fit(Xtr_fit, ytr_fit, eval_set=[(Xval, yval)], verbose=False)
        xgb_sm_val = xgb_sm.predict_proba(Xval)[:, 1]
        xgb_sm_te = xgb_sm.predict_proba(Xte)[:, 1]

        # meta-learner over [xgb_sm, lgb] — fit on VALIDATION only
        stack_val_feats = np.column_stack([xgb_sm_val, lgb_val])
        stack_te_feats = np.column_stack([xgb_sm_te, lgb_te])
        meta = LogisticRegression()
        meta.fit(stack_val_feats, yval)
        stack_raw = meta.predict_proba(stack_te_feats)[:, 1]
        stack_raw_val = meta.predict_proba(stack_val_feats)[:, 1]
        stack_cal, stack_calibrator = _platt(stack_raw_val, yval, stack_raw)
    else:
        stack_cal = probs_cal
        stack_calibrator = calibrator
        stack_raw = probs

    # AFTER (stacked) AUC: the honest target metric.
    auc_after = float(roc_auc_score(yte, stack_raw)) if len(np.unique(yte)) >= 2 else 0.5

    # ---- ensemble: rank-average of XGB probability + Hawkes intensity ----
    def _rank_pct(v: np.ndarray) -> np.ndarray:
        return pd.Series(v).rank(pct=True).to_numpy()

    hawkes_te = Xte["hawkes_intensity_24h"].to_numpy()
    hawkes_val = Xval["hawkes_intensity_24h"].to_numpy()
    ens_raw = 0.5 * _rank_pct(probs) + 0.5 * _rank_pct(hawkes_te)
    ens_raw_val = 0.5 * _rank_pct(probs_val) + 0.5 * _rank_pct(hawkes_val)

    ens_cal, ens_calibrator = _platt(ens_raw_val, yval, ens_raw)

    # ---- metric blocks: pure-XGBoost vs ensemble (honest comparison) ----
    def _prf_at(score: np.ndarray, y: np.ndarray, thr: float) -> dict:
        alert = score >= thr
        n = int(alert.sum())
        tp = int((alert & (y == 1)).sum())
        fn = int((~alert & (y == 1)).sum())
        fp = int((alert & (y == 0)).sum())
        prec = tp / max(n, 1)
        rec = tp / max(tp + fn, 1)
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        return {"threshold": thr, "alerts": n, "precision": round(prec, 4),
                "recall": round(rec, 4), "f1": round(f1, 4), "false_alerts": fp,
                "false_alert_rate": round(fp / max(n, 1), 4)}

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
            "roc_auc": round(float(roc_auc_score(y, score)) if len(np.unique(y)) >= 2 else 0.5, 4),
            "accuracy": round(float(accuracy_score(y, preds)), 4),
            "precision_at_threshold_0p7": round(float(y[mask70].mean()), 4) if mask70.sum() > 0 else None,
            "n_flagged_at_0p7": int(mask70.sum()),
            "prf_at_0p50": _prf_at(score, y, 0.50),
            "prf_at_0p60": _prf_at(score, y, 0.60),
            "prf_at_0p70": _prf_at(score, y, 0.70),
            "prf_at_0p85": _prf_at(score, y, 0.85),
        }

    blk_xgb = _metric_block(yte, probs_cal)
    blk_ens = _metric_block(yte, ens_cal)
    blk_stack = _metric_block(yte, stack_cal if stack_available else stack_raw)

    # active model = the honestly-better one. SELECTED ON THE VALIDATION SLICE
    # (never the test set): rank-based AUC is calibration-invariant, so we score
    # the raw train/val outputs. The stack (Issue 1) is a candidate; whichever
    # wins on VALIDATION becomes the active model actually served in production.
    val_auc_xgb = float(roc_auc_score(yval, probs_val)) if len(np.unique(yval)) >= 2 else 0.5
    val_auc_ens = float(roc_auc_score(yval, ens_raw_val)) if len(np.unique(yval)) >= 2 else 0.5
    val_auc_stack = float(roc_auc_score(yval, stack_raw_val)) if (stack_available and len(np.unique(yval)) >= 2) else -1.0
    candidates = {
        "xgboost": (val_auc_xgb, probs_cal, blk_xgb),
        "ensemble": (val_auc_ens, ens_cal, blk_ens),
    }
    if stack_available:
        candidates["stacked"] = (val_auc_stack, stack_cal, blk_stack)
    active = max(candidates, key=lambda k: candidates[k][0])
    active_score = candidates[active][1]
    active_block = dict(candidates[active][2])
    active_preds = (active_score >= 0.5).astype(int)

    # ---- instance-percentile reference (evidence panel) ----
    # Per-feature quantiles over the TRAINING set let the evidence panel report
    # "this feature's value is at the 95th percentile" — a simple, honest
    # per-instance signal (TreeSHAP via native pred_contribs; see explainability note).
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

    def _lift(active_prec: float, base_prec: float) -> float | None:
        # A zero baseline captures NO fraud in top-K, so the lift ratio is
        # mathematically undefined (not a valid 9e8). Report None honestly
        # rather than emitting a fabricated huge number into metrics.json.
        if base_prec <= 0.0:
            return None
        return round(active_prec / base_prec, 3)

    lift_vol = {k: _lift(active_block[f"precision_at_{k}"], v) for k, v in baseline_vol.items()}
    lift_prox = {k: _lift(active_block[f"precision_at_{k}"], v) for k, v in baseline_prox.items()}

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
        "pos_weight_multiplier": pos_weight_multiplier,
        # Issue-1 honest before/after comparison (both on the held-out TEST set):
        #   auc_before_xgb  = single XGBoost, raw train (the pre-Issue-1 baseline)
        #   auc_after_stack = XGB+LightGBM stacked, SMOTE-Tomek resampled train
        "auc_before_xgb": round(auc_before, 4),
        "auc_after_stack_raw": round(auc_after, 4),
        "stack_available": bool(stack_available),
        "stack_used_smote_tomek": bool(used_smote),
        "val_auc_xgb": round(val_auc_xgb, 4),
        "val_auc_ensemble": round(val_auc_ens, 4),
        "val_auc_stacked": round(val_auc_stack, 4) if stack_available else None,
        "scale_pos_weight": None if pos_weight_multiplier == 1.0 else round(scale_pos_weight, 3),
        **{k: v for k, v in active_block.items()},
        "per_feature_auc": per_feature_auc,
        "new_feature_single_auc_hawkes": per_feature_auc.get("hawkes_intensity_24h"),
        "metrics_xgboost_only": blk_xgb,
        "metrics_ensemble": blk_ens,
        "metrics_stacked_smote": blk_stack,
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
        "pos_weight_multiplier": pos_weight_multiplier,
        # Issue-1 stacked-ensemble components (only present when LightGBM +
        # SMOTE-Tomek are available). Used by inference when active_model is
        # the stack, so served scores match the reported metrics.
        "stack_available": bool(stack_available),
        "stack_used_smote_tomek": bool(used_smote),
        "stack_xgb": xgb_sm if (stack_available and not isinstance(xgb_sm, str)) else None,
        "stack_lgb": lgb if (stack_available and not isinstance(lgb, str)) else None,
        "stack_meta": meta if (stack_available and not isinstance(meta, str)) else None,
        "stack_calibrator": stack_calibrator if stack_available else None,
        "stack_feature_order": list(FEATURE_COLUMNS),
        # Train-set lookups used to build the Issue-1 latency / bank-rate
        # features. Persisted so INFERENCE reproduces the same values the model
        # was trained on (no train/serve skew for these two features).
        "fraud_latency_by_type": fraud_latency_by_type,
        "bank_fraud_rate": bank_fraud_rate,
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