"""Fairness group audit — per-jurisdiction alert metrics on the held-out split.

Recreates artifacts/deep_eval/fairness_groups.json from the CURRENT data + model.
"""
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.database import engine
from backend.eval.deep_evaluation import load_split_cached
from backend.ml.inference import load_pipeline

OUT = Path(__file__).resolve().parent.parent / "artifacts" / "deep_eval" / "fairness_groups.json"

pipe = load_pipeline()
model, cal = pipe["model"], pipe["calibrator"]
X, meta, y, m_tr, m_val, m_te = load_split_cached(engine)
feat = [c for c in X.columns if not c.startswith("meta_")]
Xte, yte = X[feat][m_te], np.asarray(y[m_te], dtype=float)
meta_te = meta[m_te] if isinstance(meta, pd.DataFrame) else None
raw = model.predict_proba(Xte)[:, 1]
score = cal.predict_proba(raw.reshape(-1, 1))[:, 1]

rows = []
for city in sorted(meta_te["city"].unique()):
    m = meta_te["city"].values == city
    yc, sc = yte[m], score[m]
    thr = 0.7
    rows.append({
        "jurisdiction_group": city,
        "rows": int(m.sum()),
        "positive_rate": round(float(yc.mean()), 4),
        "alert_rate_0p7": round(float((sc >= thr).mean()), 4),
        "false_positive_rate_0p7": round(float(((sc >= thr) & (yc == 0)).mean()), 4),
        "precision_0p7": round(float(yc[sc >= thr].mean()), 4) if (sc >= thr).any() else None,
        "recall_0p7": round(float((sc >= thr)[yc == 1].mean()), 4),
    })
out = [{
    "jurisdiction_group": "all_jurisdictions",
    "rows": int(len(yte)),
    "positive_rate": round(float(yte.mean()), 4),
    "alert_rate_0p7": round(float((score >= 0.7).mean()), 4),
    "false_positive_rate_0p7": round(float(((score >= 0.7) & (yte == 0)).mean()), 4),
    "precision_0p7": round(float(yte[score >= 0.7].mean()), 4) if (score >= 0.7).any() else None,
    "recall_0p7": round(float((score >= 0.7)[yte == 1].mean()), 4),
}] + rows
OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"saved {OUT} — {len(rows) + 1} groups")
for r in out:
    print(f"  {r['jurisdiction_group']:<20} FPR {r['false_positive_rate_0p7']:.4f}  alert {r['alert_rate_0p7']:.4f}  prec {r['precision_0p7']}")