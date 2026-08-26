"""
Robustness check (Tier 1, one-time static result).

Trains the SAME model on:
  A) the base calibration dataset
  B) a dataset with clustering/timing parameters perturbed ±30%

and reports precision@K / recall@K / AUC for both in a single table + chart
(artifacts/robustness_check.png). This is an honesty check: does the model's
top-K ranking survive when the generative assumptions move?

Usage:
    python scripts/robustness_check.py

Outputs:
    artifacts/robustness_check.png   (for the pitch deck)
    artifacts/robustness_check.json  (raw numbers)
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from backend.config import ARTIFACT_DIR, SEED  # noqa: E402
from backend.data.synthetic_data import generate_all, load_calibration_config  # noqa: E402
from backend.database import Base, engine as base_engine  # noqa: E402
from backend.ml.features import build_features, build_target, load_dataframes  # noqa: E402
from backend.ml.train import _precision_at_k, _recall_at_k  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

PERTURB_PATHS = [
    ("clustering", "pareto_skew"),
    ("clustering", "hot_atm_fraction"),
    ("behaviour", "night_weight"),
    ("behaviour", "weekend_weight"),
    ("behaviour", "round_amount_bias"),
    ("timing", "fraud_to_cashout_mean_hours"),
]


def perturbed_config(base: dict, factor: float) -> dict:
    cfg = copy.deepcopy(base)
    for section, param in PERTURB_PATHS:
        cfg[section][param] = max(0.01, cfg[section][param] * factor)
    return cfg


def train_evaluate(db_url: str, cfg: dict, label: str, seed: int) -> dict:
    """Generate + train + evaluate on a given DB file, return metrics."""
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Session()
    try:
        generate_all(db, cfg=cfg, seed=seed)
    finally:
        db.close()
    try:
        # training pipeline (same code path as scripts/train_model.py)
        from backend.ml.train import train  # noqa: E402  (imported late: xgboost is heavy)

        # out_dir per run: robustness runs must NEVER overwrite the main
        # artifacts/model.joblib used by the live demo.
        out_dir = Path(db_url.replace("sqlite:///", "").replace(".db", "_artifacts"))
        metrics = train(engine, seed=seed, out_dir=out_dir)
        metrics["label"] = label
        return metrics
    finally:
        engine.dispose()  # release the SQLite file so the temp dir can be cleaned


def _json_safe(o):
    """Sanitize non-finite floats -> None so robustness_check.json is always valid JSON."""
    import math

    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_json_safe(v) for v in o]
    return o


def main() -> None:
    base_cfg = load_calibration_config()

    with tempfile.TemporaryDirectory() as tmp:
        results = []
        for label, factor in [("Base calibration", 1.0), ("Perturbed -30%", 0.7), ("Perturbed +30%", 1.3)]:
            cfg = base_cfg if factor == 1.0 else perturbed_config(base_cfg, factor)
            db_url = f"sqlite:///{Path(tmp) / (label.split()[1].replace('%', 'p') + '.db')}"
            print(f">> {label}: generating + training ...")
            results.append(train_evaluate(db_url, cfg, label, seed=SEED))

    # ---- table + chart ----
    labels = [r["label"] for r in results]
    p20 = [r["precision_at_20"] for r in results]
    p500 = [r["precision_at_500"] for r in results]
    p1000 = [r["precision_at_1000"] for r in results]
    pthr = [r["precision_at_threshold_0p7"] for r in results]
    aucs = [r["roc_auc"] for r in results]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), dpi=130)
    x = np.arange(len(labels))
    width = 0.22
    # the informative (non-saturated) part of the curve: P@500/P@1000/threshold
    axes[0].bar(x - width, p500, width, label="Precision@500", color="#eab308")
    axes[0].bar(x, p1000, width, label="Precision@1000", color="#38bdf8")
    axes[0].bar(x + width, pthr, width, label="Precision@≥0.7", color="#a78bfa")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=12)
    axes[0].set_ylim(0, 1.05)
    axes[0].set_ylabel("Precision")
    axes[0].set_title("Non-saturated precision under ±30% calibration perturbation")
    axes[0].legend()
    axes[0].grid(alpha=0.2)

    axes[1].bar(x, aucs, width * 2, color="#22c55e")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=12)
    axes[1].set_ylim(0, 1.05)
    axes[1].set_ylabel("ROC-AUC")
    axes[1].set_title("ROC-AUC under ±30% calibration perturbation")
    axes[1].grid(alpha=0.2)

    fig.suptitle("Robustness check — synthetic labels, time-based split (honest disclosure: not real-world precision)", fontsize=10)
    fig.tight_layout()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    png = ARTIFACT_DIR / "robustness_check.png"
    fig.savefig(png)

    table = [
        {"label": r["label"], "precision_at_20": r["precision_at_20"],
         "precision_at_50": r["precision_at_50"], "precision_at_100": r["precision_at_100"],
         "precision_at_500": r["precision_at_500"], "precision_at_1000": r["precision_at_1000"],
         "precision_at_threshold_0p7": r["precision_at_threshold_0p7"],
         "roc_auc": r["roc_auc"], "positive_share": r["positive_share"]}
        for r in results
    ]
    (ARTIFACT_DIR / "robustness_check.json").write_text(json.dumps(_json_safe(table), indent=2))

    print("\nROBUSTNESS CHECK — precision@K across calibration perturbation:")
    print(f"{'dataset':<22}{'P@20':<8}{'P@50':<8}{'P@100':<9}{'P@500':<9}{'P@1000':<9}{'P(0.7)':<9}{'AUC':<8}")
    for r in results:
        print(f"{r['label']:<22}{r['precision_at_20']:<8}{r['precision_at_50']:<8}{r['precision_at_100']:<9}"
              f"{r['precision_at_500']:<9}{r['precision_at_1000']:<9}{r['precision_at_threshold_0p7']:<9}{r['roc_auc']:<8}")
    print(f"\nChart saved: {png}")


if __name__ == "__main__":
    main()