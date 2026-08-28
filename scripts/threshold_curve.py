"""Threshold explorer artifact: precision/recall/false-alert/volume at every
threshold on the held-out test split, so the dashboard can show the
operational cost of threshold choice live (artifact-backed, not recomputed
per request).

Run: python scripts/threshold_curve.py
Out: artifacts/deep_eval/threshold_curve.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from backend.database import engine  # noqa: E402
from backend.eval.deep_evaluation import OUT, load_split  # noqa: E402
from backend.ml.inference import load_pipeline  # noqa: E402

THRESHOLDS = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]


def main():
    X, meta, y, m_tr, m_val, m_te = load_split(engine)
    feat = [c for c in X.columns if not c.startswith("meta_")]
    Xte = X[feat][m_te]
    yte = np.asarray(y[m_te], dtype=float)
    pipe = load_pipeline()
    raw = pipe["model"].predict_proba(Xte)[:, 1]
    score = pipe["calibrator"].predict_proba(raw.reshape(-1, 1))[:, 1]

    rows = []
    for thr in THRESHOLDS:
        alert = score >= thr
        n_alert = int(alert.sum())
        tp = int((alert & (yte == 1)).sum())
        fp = int((alert & (yte == 0)).sum())
        fn = int((~alert & (yte == 1)).sum())
        rows.append({
            "threshold": thr,
            "alert_volume": n_alert,
            "alert_rate": round(float(alert.mean()), 4),
            "precision": round(tp / max(n_alert, 1), 4),
            "recall": round(tp / max(tp + fn, 1), 4),
            "false_alerts": fp,
            "false_alert_rate": round(fp / max(n_alert, 1), 4),
            "tier_hint": ("monitor" if thr < 0.7 else ("action" if thr < 0.85 else "dispatch")),
        })
        print(f"  thr {thr:.2f}: alerts {n_alert:>4}  precision {rows[-1]['precision']:.3f}  "
              f"recall {rows[-1]['recall']:.3f}  FAR {rows[-1]['false_alert_rate']:.3f}")

    out = {
        "label": "CONTROLLED SYNTHETIC EVALUATION - threshold explorer (artifact-backed)",
        "split": "held-out test (chronological)",
        "n_test_rows": int(len(yte)),
        "positive_rate": round(float(yte.mean()), 4),
        "curve": rows,
        "note": "The dashboard's threshold explorer reads this artifact; the operational threshold stays 0.7 unless ops re-derives it (REAL_DATA_VALIDATION_PROTOCOL.md).",
    }
    (OUT / "threshold_curve.json").write_text(json.dumps(out, indent=2))
    print("saved:", OUT / "threshold_curve.json")


if __name__ == "__main__":
    main()