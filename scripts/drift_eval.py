"""Drift evaluation (Phase 6): 10 adversarial worlds + drift-confidence rule.

Reuses the generator with scenario overrides (temp DBs, reduced size for speed).
Produces artifacts/deep_eval/drift.json + MODEL_DRIFT.md content.
Rule: if a world's ROC-AUC < 0.85 or threshold precision < 0.75 -> confidence
flagged "REDUCED" for that drift signature (surfaced with the forecast).
"""
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.config import ARTIFACT_DIR  # noqa: E402
from backend.database import Base  # noqa: E402
from backend.eval.deep_evaluation import _deep_merge, OUT, load_split, std_block, train_score  # noqa: E402
from backend.data.synthetic_data import generate_all, load_calibration_config  # noqa: E402

T0 = time.time()


def log(msg):
    print(f"[drift {time.time() - T0:5.0f}s] {msg}", flush=True)


def main():
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
        "fraud_rate_shift": {"dataset": {"fraud_share": 0.18}},
        "mule_network_topology": {"scenario": {"mule_same_atm_prob": 0.75, "mule_burst_prob": 0.1, "random_atm_fraud_prob": 0.3}},
        "coordinated_adaptation": {"scenario": {"blocked_burst_prob": 0.3, "hot_atm_use_prob": 0.75, "mule_burst_prob": 0.6}},
    }
    rows = []
    tmp = Path(tempfile.mkdtemp(prefix="cg_drift_"))
    try:
        for name, overrides in worlds.items():
            cfg = _deep_merge(base, overrides)
            cfg["dataset"]["n_atms_per_city"] = 60
            cfg["dataset"]["n_withdrawals"] = 60000
            cfg["dataset"]["n_complaints"] = 5000
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
                b["drift_flag"] = "REDUCED" if (b["roc_auc"] < 0.85 or (b["threshold_precision_0p7"] or 0) < 0.75) else "OK"
                rows.append(b)
                log(f"{name}: AUC {b['roc_auc']} P@1000 {b['precision_at_1000']} -> {b['drift_flag']}")
            finally:
                engine.dispose()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for r in rows:
        r["label"] = "CONTROLLED SYNTHETIC EVALUATION"
    (OUT / "drift.json").write_text(json.dumps(rows, indent=2))
    summary = {
        "rule": "Drift-confidence: REDUCED if world ROC-AUC < 0.85 or threshold precision < 0.75. REDUCED confidence is surfaced with the forecast (no aggressive recommendations).",
        "worlds": [{"world": r.get("world"), "roc_auc": r.get("roc_auc"), "precision_at_1000": r.get("precision_at_1000"),
                    "threshold_precision": r.get("threshold_precision_0p7"), "drift_flag": r.get("drift_flag")} for r in rows],
    }
    (OUT / "drift_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()