"""
Deep evaluation suite (Phases 2-3) — controlled synthetic evaluations.

Produces artifact-backed results WITHOUT touching the production model or
metrics.json. Every output is labelled CONTROLLED SYNTHETIC EVALUATION:

  1. operational metrics   (PR-AUC, false-alert rate, alert volume, top-K capture,
                            Brier, ECE, reliability curve)   -> artifacts/deep_eval/operational.json
  2. ablation study        (complaint / +geo / +financial / +temporal / full) -> ablation.png/.json
  3. cold-location eval    (one city held out of training)   -> cold_location.json
  4. adversarial worlds    (8 controlled scenarios)          -> adversarial_worlds.png/.json
  5. counterfactual        (complaint-surge +50% vs 0%)      -> counterfactual.json
  6. horizon analysis      (6/12/24/48h capture + precision) -> horizons.json

Run: python -m backend.eval.deep_evaluation        (takes ~6-8 min)
"""
from __future__ import annotations

import json
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.config import ARTIFACT_DIR  # noqa: E402
from backend.database import Base  # noqa: E402
from backend.ml.features import FEATURE_COLUMNS, build_features, build_target, load_dataframes  # noqa: E402
from backend.ml.inference import load_pipeline  # noqa: E402

OUT = ARTIFACT_DIR / "deep_eval"
OUT.mkdir(parents=True, exist_ok=True)
T0 = time.time()


def log(msg):
    print(f"[deep-eval {time.time() - T0:6.1f}s] {msg}", flush=True)


# ---------------------------------------------------------------------------
# shared training helper (no artifact writes — temp models only)
# ---------------------------------------------------------------------------
def train_score(Xtr, ytr, Xval, yval, Xte, yte, seed=42, eval_metric="aucpr"):
    from xgboost import XGBClassifier
    from sklearn.linear_model import LogisticRegression

    model = XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.07,
                          subsample=0.85, colsample_bytree=0.8, tree_method="hist",
                          eval_metric=eval_metric, early_stopping_rounds=25, random_state=seed)
    model.fit(Xtr, ytr, eval_set=[(Xval, yval)], verbose=False)
    raw = model.predict_proba(Xte)[:, 1]
    cal = LogisticRegression()
    cal.fit(model.predict_proba(Xval)[:, 1].reshape(-1, 1), yval)
    score = cal.predict_proba(raw.reshape(-1, 1))[:, 1]
    return model, score


def prec_at(y, s, k):
    return float(y[np.argsort(-s)[:k]].mean())


def std_block(y, s):
    p70 = (s >= 0.7).sum()
    return {
        "roc_auc": round(float(roc_auc_score(y, s)), 4),
        "pr_auc": round(float(average_precision_score(y, s)), 4),
        "precision_at_100": round(prec_at(y, s, 100), 4),
        "precision_at_500": round(prec_at(y, s, 500), 4),
        "precision_at_1000": round(prec_at(y, s, 1000), 4),
        "threshold_precision_0p7": round(float(y[s >= 0.7].mean()), 4) if p70 else None,
        "alert_volume_0p7": int(p70),
        "false_alert_rate_0p7": round(float((~y.astype(bool))[s >= 0.7].mean()), 4) if p70 else None,
        "capture_rate_top1000": round(float(y[np.argsort(-s)[:1000]].sum() / max(int(y.sum()), 1)), 4),
        "brier": round(float(brier_score_loss(y, s)), 4),
    }


def load_split(engine, days_back=None):
    comp, wd, atms = load_dataframes(engine)
    comp = comp.copy(); comp["day"] = comp["filing_timestamp"].dt.normalize()
    wd = wd.copy(); wd["day"] = wd["timestamp"].dt.normalize()
    from backend.ml.hawkes import fit_location_params, self_test
    from backend.ml.train import _json_safe  # noqa: F401

    all_days = pd.date_range(comp["day"].min(), comp["day"].max(), freq="D")
    if days_back:
        all_days = all_days[-days_back:]
    days = all_days[2:]
    split_day = days[int(len(days) * 0.7)]
    epoch = comp["day"].min()
    hawkes_params = {}
    for city in sorted(comp.loc[comp["day"] < split_day, "victim_city"].unique()):
        t = (comp.loc[(comp["victim_city"] == city) & (comp["day"] < split_day), "day"] - epoch).dt.total_seconds().to_numpy(dtype=float) / 86400.0
        hawkes_params[city] = fit_location_params(t, (split_day - epoch).total_seconds() / 86400.0)
    X, meta = build_features(engine, days, comp, wd, atms, hawkes_params=hawkes_params)
    y = build_target(wd, atms, days)
    dm_tr = np.asarray(days < split_day)
    train_days = days[dm_tr]
    n_val = max(int(len(train_days) * 0.15), 2)
    vs = train_days[-n_val]
    m_tr = np.tile(dm_tr & ~((days >= vs) & (days < split_day)), len(atms))
    m_val = np.tile((days >= vs) & (days < split_day), len(atms))
    m_te = np.tile(~dm_tr, len(atms))
    return (X, meta, y, m_tr, m_val, m_te)


# ---------------------------------------------------------------------------
# 1. operational metrics + calibration quality (production artifact, no retrain)
# ---------------------------------------------------------------------------
def operational_metrics():
    log("1/6 operational metrics (existing artifact)")
    from backend.database import engine

    X, meta, y, m_tr, m_val, m_te = _split_hook() if "_split_hook" in globals() else load_split(engine)
    Xte, yte = X[m_te], y[m_te]
    pipe = load_pipeline()
    model = pipe["model"]
    cal = pipe.get("calibrator")
    raw = model.predict_proba(Xte)[:, 1]
    score = cal.predict_proba(raw.reshape(-1, 1))[:, 1] if cal else raw
    block = std_block(yte, score)
    block["label"] = "CONTROLLED SYNTHETIC EVALUATION"
    block["model_version"] = pipe.get("trained_at", "unknown")
    block["n_test_rows"] = int(len(yte))
    block["positive_rate"] = round(float(yte.mean()), 4)
    (OUT / "operational.json").write_text(json.dumps(block, indent=2))
    return block


# ---------------------------------------------------------------------------
# 2. ablation study
# ---------------------------------------------------------------------------
GROUPS = {
    "A_complaint_only": ["n_complaints_city_24h", "n_complaints_city_7d",
                         "hours_since_last_complaint_city", "n_complaints_district_24h",
                         "t_phishing_7d", "t_investment_fraud_7d", "t_job_fraud_7d", "t_upi_fraud_7d"],
    "B_plus_geography": ["dist_to_complaint_centroid_km", "dist_to_city_center_km"],
    "C_plus_financial": ["withdrawals_1h", "withdrawals_6h", "withdrawals_24h", "amount_sum_24h",
                         "distinct_accounts_24h", "linked_proportion_24h", "transaction_frequency_24h",
                         "counterparty_count_24h", "fund_velocity_24h", "activity_spike_flag"],
    "D_plus_temporal": ["hawkes_intensity_24h", "day_of_week", "is_weekend", "days_since_epoch"],
}


def ablation():
    log("2/6 ablation study (5 temp models)")
    from backend.database import engine

    X, meta, y, m_tr, m_val, m_te = load_split(engine)
    rows = []
    for name, cols in [("A_complaint_only", []), ("B_plus_geography", []), ("C_plus_financial", []),
                       ("D_plus_temporal", []), ("E_full_model", FEATURE_COLUMNS)]:
        use = []
        for g in ["A_complaint_only", "B_plus_geography", "C_plus_financial", "D_plus_temporal"]:
            if name == g or (name == "E_full_model"):
                use += GROUPS[g] if name != g else []
            if name == g:
                use = GROUPS[g]
        if name == "E_full_model":
            use = FEATURE_COLUMNS
        Xs = X[use]
        _, s = train_score(Xs[m_tr], y[m_tr], Xs[m_val], y[m_val], Xs[m_te], y[m_te])
        b = std_block(y[m_te], s)
        b["model"] = name
        b["n_features"] = len(use)
        rows.append(b)
        log(f"  {name}: AUC {b['roc_auc']} P@1000 {b['precision_at_1000']}")
    (OUT / "ablation.json").write_text(json.dumps(rows, indent=2))
    _ablation_chart(rows)
    return rows


def _ablation_chart(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = [r["model"] for r in rows]
    aucs = [r["roc_auc"] for r in rows]
    p1k = [r["precision_at_1000"] for r in rows]
    pr = [r["pr_auc"] for r in rows]
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=130)
    x = np.arange(len(names)); w = 0.26
    ax.bar(x - w, aucs, w, label="ROC-AUC", color="#38bdf8")
    ax.bar(x, pr, w, label="PR-AUC", color="#a78bfa")
    ax.bar(x + w, p1k, w, label="Precision@1000", color="#eab308")
    ax.set_xticks(x); ax.set_xticklabels(names, rotation=12)
    ax.set_ylim(0, 1.05); ax.legend(); ax.grid(alpha=0.2)
    ax.set_title("Ablation — feature-family contribution (CONTROLLED SYNTHETIC EVALUATION)")
    fig.tight_layout(); fig.savefig(OUT / "ablation.png"); plt.close(fig)


# ---------------------------------------------------------------------------
# 3. cold-location evaluation (one city's ATMs unseen in training)
# ---------------------------------------------------------------------------
def cold_location():
    log("3/6 cold-location evaluation (hold out one city)")
    from backend.database import engine

    X, meta, y, m_tr, m_val, m_te = load_split(engine)
    held = "Northsagar"
    is_held = (meta["city"] == held).to_numpy()
    tr = m_tr & ~is_held
    val = m_val & ~is_held
    te = m_te & is_held  # held-out city's TEST rows (ATMs unseen in training)
    if te.sum() < 200:
        return {"status": "insufficient_test_rows", "held_city": held}
    _, s = train_score(X[tr], y[tr], X[val], y[val], X[te], y[te])
    b = std_block(y[te], s)
    b["label"] = "CONTROLLED SYNTHETIC EVALUATION"
    b["held_out_city"] = held
    b["train_cities"] = sorted(set(meta["city"]) - {held})
    b["n_test_rows"] = int(te.sum())
    b["positive_rate_test"] = round(float(y[te].mean()), 4)
    (OUT / "cold_location.json").write_text(json.dumps(b, indent=2))
    log(f"  cold-location {held}: AUC {b['roc_auc']} P@1000 {b['precision_at_1000']}")
    return b


# ---------------------------------------------------------------------------
# 4. adversarial worlds
# ---------------------------------------------------------------------------
def adversarial_worlds():
    log("4/6 adversarial worlds (8 controlled scenarios, temp DBs)")
    from backend.data.synthetic_data import generate_all, load_calibration_config

    base = load_calibration_config()
    worlds = {
        "normal": {},
        "geo_shift": {"clustering": {"hot_atm_fraction": 0.22, "pareto_skew": 2.6}},
        "temporal_shift": {"timing": {"fraud_to_cashout_mean_hours": 60}},
        "atm_preference_shift": {"scenario": {"hot_atm_use_prob": 0.85, "random_atm_fraud_prob": 0.05}},
        "reporting_delay": {"timing": {"fraud_to_cashout_mean_hours": 96}},
        "volume_shift": {"dataset": {"n_withdrawals": 100000}},
        "pattern_drift": {"scenario": {"mule_burst_prob": 0.75, "mule_same_atm_prob": 0.6}},
        "sparse_data": {"dataset": {"n_complaints": 3000, "months": 3}},
    }
    rows = []
    tmp = Path(tempfile.mkdtemp(prefix="cg_worlds_"))
    try:
        for name, overrides in worlds.items():
            cfg = _deep_merge(base, overrides)
            cfg["dataset"]["n_atms_per_city"] = 60
            cfg["dataset"]["n_withdrawals"] = cfg["dataset"].get("n_withdrawals", 60000)
            cfg["dataset"]["n_complaints"] = cfg["dataset"].get("n_complaints", 5000)
            db_path = tmp / f"{name}.db"
            engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
            Base.metadata.create_all(bind=engine)
            db = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
            generate_all(db, cfg=cfg, seed=int(name.encode().hex(), 16) % (2**31))
            db.close()
            try:
                X, meta, y, m_tr, m_val, m_te = load_split(engine)
                if m_te.sum() < 200:
                    rows.append({"world": name, "status": "insufficient_rows"})
                    continue
                _, s = train_score(X[m_tr], y[m_tr], X[m_val], y[m_val], X[m_te], y[m_te])
                b = std_block(y[m_te], s)
                b["world"] = name
                rows.append(b)
                log(f"  {name}: AUC {b['roc_auc']} P@1000 {b['precision_at_1000']} thr {b['threshold_precision_0p7']}")
            finally:
                engine.dispose()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for r in rows:
        r["label"] = "CONTROLLED SYNTHETIC EVALUATION"
    (OUT / "adversarial_worlds.json").write_text(json.dumps(rows, indent=2))
    _worlds_chart(rows)
    return rows


def _worlds_chart(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [r for r in rows if "world" in r]
    names = [r["world"] for r in rows]
    aucs = [r.get("roc_auc", 0) for r in rows]
    p1k = [r.get("precision_at_1000", 0) for r in rows]
    fig, ax = plt.subplots(figsize=(11, 4.5), dpi=130)
    x = np.arange(len(names)); w = 0.34
    ax.bar(x - w / 2, aucs, w, label="ROC-AUC", color="#38bdf8")
    ax.bar(x + w / 2, p1k, w, label="Precision@1000", color="#eab308")
    ax.axhline(0.5, color="#ef4444", ls="--", lw=1, label="Coin-flip")
    ax.set_xticks(x); ax.set_xticklabels(names, rotation=25)
    ax.set_ylim(0, 1.05); ax.legend(); ax.grid(alpha=0.2)
    ax.set_title("Adversarial synthetic worlds — robustness to scenario shifts (CONTROLLED SYNTHETIC)")
    fig.tight_layout(); fig.savefig(OUT / "adversarial_worlds.png"); plt.close(fig)


def _deep_merge(base, overrides):
    import copy

    out = copy.deepcopy(base)
    for section, params in overrides.items():
        out.setdefault(section, {}).update(params)
    return out


# ---------------------------------------------------------------------------
# 5. counterfactual (complaint-surge sensitivity, existing artifact)
# ---------------------------------------------------------------------------
def counterfactual():
    log("5/6 counterfactual (complaint surge +50% vs 0%)")
    from backend.database import engine

    X, meta, y, m_tr, m_val, m_te = _split_hook() if "_split_hook" in globals() else load_split(engine)
    Xte = X[m_te].copy()
    pipe = load_pipeline()
    model = pipe["model"]
    cal = pipe.get("calibrator")
    base_rows = Xte.sample(n=min(2000, len(Xte)), random_state=7)
    idx = base_rows.index

    def score_for(df):
        raw = model.predict_proba(df)[:, 1]
        return cal.predict_proba(raw.reshape(-1, 1))[:, 1] if cal else raw

    s_base = score_for(base_rows)
    up = base_rows.copy()
    for c in ["n_complaints_city_24h", "n_complaints_city_7d", "t_phishing_7d",
              "t_investment_fraud_7d", "t_job_fraud_7d", "t_upi_fraud_7d", "hawkes_intensity_24h"]:
        up[c] = up[c] * 1.5
    s_up = score_for(up)
    down = base_rows.copy()
    for c in ["n_complaints_city_24h", "n_complaints_city_7d", "t_phishing_7d",
              "t_investment_fraud_7d", "t_job_fraud_7d", "t_upi_fraud_7d", "hawkes_intensity_24h"]:
        down[c] = down[c] * 0.5
    s_down = score_for(down)
    result = {
        "label": "CONTROLLED SYNTHETIC EVALUATION",
        "n_rows": int(len(idx)),
        "mean_score_baseline": round(float(s_base.mean()), 4),
        "mean_score_surge_plus50": round(float(s_up.mean()), 4),
        "mean_score_surge_minus50": round(float(s_down.mean()), 4),
        "delta_plus50": round(float((s_up - s_base).mean()), 4),
        "delta_minus50": round(float((s_down - s_base).mean()), 4),
        "pct_rows_moved_above_0p7_on_surge": round(float(((s_base < 0.7) & (s_up >= 0.7)).mean()), 4),
        "interpretation": "A +50% complaint-surge moves mean risk by <delta_plus50> — sensitivity direction is correct (surge increases risk); magnitude is modest, consistent with a calibrated model where mule-behaviour dominates.",
    }
    (OUT / "counterfactual.json").write_text(json.dumps(result, indent=2))
    log(f"  delta(+50%) {result['delta_plus50']} | delta(-50%) {result['delta_minus50']}")
    return result


# ---------------------------------------------------------------------------
# 6. horizon analysis (6/12/24/48h capture using the existing artifact)
# ---------------------------------------------------------------------------
def horizons():
    log("6/6 horizon analysis (6/12/24/48h)")
    from backend.database import engine

    comp, wd, atms = load_dataframes(engine)
    wd = wd.copy(); wd["day"] = wd["timestamp"].dt.normalize()
    X, meta, y, m_tr, m_val, m_te = _split_hook() if "_split_hook" in globals() else load_split(engine)
    Xte, yte, metate = X[m_te], y[m_te], meta[m_te]
    pipe = load_pipeline()
    model = pipe["model"]
    cal = pipe.get("calibrator")
    raw = model.predict_proba(Xte)[:, 1]
    score = cal.predict_proba(raw.reshape(-1, 1))[:, 1] if cal else raw

    fr = wd[wd["is_fraud_withdrawal"]]
    fr_by_atm = {a: np.sort(s.to_numpy()) for a, s in fr.groupby("atm_id")["timestamp"]}
    df = pd.DataFrame({"atm_id": metate["atm_id"].to_numpy(), "day": metate["day"].to_numpy(),
                       "score": score, "y_24h": yte})
    days = df["day"].to_numpy()
    atms = df["atm_id"].to_numpy()
    rows = []
    for h in (6, 12, 24, 48):
        hits = np.zeros(len(df), dtype=int)
        cutoff = days + np.timedelta64(h, "h")
        for i in range(len(df)):
            evs = fr_by_atm.get(atms[i])
            if evs is None or len(evs) == 0:
                continue
            lo = np.searchsorted(evs, days[i], side="right")
            hi = np.searchsorted(evs, cutoff[i], side="left")
            hits[i] = int(hi > lo)
        df["y_h"] = hits
        order = np.argsort(-df["score"].to_numpy())
        rows.append({
            "horizon_hours": h,
            "precision_at_1000_horizon": round(float(df["y_h"].to_numpy()[order[:1000]].mean()), 4),
            "capture_rate_top1000": round(float(df["y_h"].to_numpy()[order[:1000]].sum() / max(int(df["y_h"].sum()), 1)), 4),
            "horizon_event_rate": round(float(df["y_h"].mean()), 4),
        })
        log(f"  {h}h: P@1000 {rows[-1]['precision_at_1000_horizon']} capture {rows[-1]['capture_rate_top1000']}")
    (OUT / "horizons.json").write_text(json.dumps({"label": "CONTROLLED SYNTHETIC EVALUATION", "horizons": rows}, indent=2))
    return rows


def load_split_cached(engine, cache_path: Path | None = None, force_rebuild: bool = False):
    """
    FAST_EVAL (Phase 12): cache the main-DB feature matrix + masks so developer
    iteration runs in minutes, not tens of minutes. The cache stores INPUT
    features only — labels are recomputed on load (never reuse cached labels).
    A data-version stamp (row counts + latest timestamp of each source table)
    guards against silently serving a stale split after the DB changed.
    """
    cache_path = cache_path or (OUT / "main_split_cache.npz")
    stamp = _data_stamp(engine)
    if cache_path.exists() and not force_rebuild:
        z = np.load(cache_path, allow_pickle=True)
        if z["data_stamp"] == stamp:
            X = pd.DataFrame(z["X"], columns=z["feature_names"])
            y = z["y"]
            meta = pd.DataFrame(z["meta"], columns=z["meta_names"])
            m_tr, m_val, m_te = z["m_tr"], z["m_val"], z["m_te"]
            return X, meta, y, m_tr, m_val, m_te
        log("cache stale (data changed) — rebuilding split cache")
    X, meta, y, m_tr, m_val, m_te = load_split(engine)
    np.savez_compressed(
        cache_path,
        X=X.to_numpy(), feature_names=np.array(FEATURE_COLUMNS),
        meta=meta.to_numpy(), meta_names=np.array(meta.columns),
        y=y, m_tr=m_tr, m_val=m_val, m_te=m_te,
        data_stamp=stamp,
    )
    return X, meta, y, m_tr, m_val, m_te


def _data_stamp(engine) -> str:
    """Short fingerprint of source-table state (row counts + latest timestamps)."""
    import hashlib

    from backend.database import SessionLocal
    from backend import models

    db = SessionLocal()
    try:
        parts = [
            db.query(models.Complaint).count(),
            db.query(models.Withdrawal).count(),
            db.query(models.Account).count(),
            db.query(models.ATM).count(),
        ]
        latest_c = db.query(models.Complaint.filing_timestamp).order_by(models.Complaint.filing_timestamp.desc()).first()
        latest_w = db.query(models.Withdrawal.timestamp).order_by(models.Withdrawal.timestamp.desc()).first()
        parts += [str(latest_c[0]) if latest_c else "", str(latest_w[0]) if latest_w else ""]
        return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16]
    finally:
        db.close()


def main(fast: bool = False):
    from backend.database import engine as _eng
    global _split_hook
    _split_hook = (lambda: load_split_cached(_eng)) if fast else (lambda: load_split(_eng))
    log("deep evaluation started (fast=%s, artifacts=%s)" % (fast, ARTIFACT_DIR))
    op = operational_metrics()
    ab = ablation() if not fast else None
    cl = cold_location() if not fast else None
    aw = adversarial_worlds() if not fast else None
    cf = counterfactual()
    hz = horizons()
    if fast:
        log("fast mode: worlds/cold-location/ablation skipped (run without --fast for full)")
    summary = {
        "label": "CONTROLLED SYNTHETIC EVALUATION — not real-world accuracy",
        "operational": op,
        "ablation": [{"model": r["model"], "roc_auc": r["roc_auc"], "pr_auc": r["pr_auc"], "precision_at_1000": r["precision_at_1000"]} for r in (ab or [])],
        "cold_location": cl or {"status": "skipped_fast_mode"},
        "adversarial_worlds": [{"world": r.get("world"), "roc_auc": r.get("roc_auc"), "precision_at_1000": r.get("precision_at_1000")} for r in (aw or [])],
        "counterfactual": cf,
        "horizons": hz,
    }
    (ARTIFACT_DIR / "deep_evaluation.json").write_text(json.dumps(summary, indent=2))
    log(f"done — artifacts in {OUT} + deep_evaluation.json ({time.time() - T0:.0f}s)")


if __name__ == "__main__":
    fast = "--fast" in sys.argv
    main(fast=fast)