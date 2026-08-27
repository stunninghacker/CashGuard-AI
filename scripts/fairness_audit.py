"""Fairness group audit — jurisdiction + complaint-density + volume groups.

Recreates artifacts/deep_eval/fairness_groups.json from the CURRENT data + model.
Group dimensions: jurisdiction (city), complaint-activity tercile (low/mid/high
complaint areas), and ATM traffic-volume tercile (low/mid/high volume ATMs).
"""
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.database import engine
from backend.eval.deep_evaluation import load_split_cached
from backend.ml.features import load_dataframes
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

comp, wd, atms = load_dataframes(engine)
city_complaints = comp.groupby("victim_city")["victim_city"].count()
atm_volume = wd.groupby("atm_id")["atm_id"].count()
terc = lambda s: pd.qcut(s, 3, labels=["low", "mid", "high"], duplicates="drop")
complaint_terc = terc(city_complaints)
volume_terc = terc(atm_volume)

def group_row(group_name, mask):
    yc, sc = yte[mask], score[mask]
    if mask.sum() == 0:
        return None
    thr = 0.7
    return {
        "group": group_name,
        "rows": int(mask.sum()),
        "positive_rate": round(float(yc.mean()), 4),
        "alert_rate_0p7": round(float((sc >= thr).mean()), 4),
        "false_positive_rate_0p7": round(float(((sc >= thr) & (yc == 0)).mean()), 4),
        "precision_0p7": round(float(yc[sc >= thr].mean()), 4) if (sc >= thr).any() else None,
        "recall_0p7": round(float((sc >= thr)[yc == 1].mean()), 4),
    }

rows = []
for city in sorted(meta_te["city"].unique()):
    r = group_row(f"jurisdiction:{city}", meta_te["city"].values == city)
    if r:
        rows.append(r)

for level in ["low", "mid", "high"]:
    cities = [c for c in complaint_terc.index if complaint_terc[c] == level]
    m = meta_te["city"].isin(cities).values if len(cities) else np.zeros(len(meta_te), dtype=bool)
    r = group_row(f"complaint_area:{level}", m)
    if r:
        rows.append(r)

for level in ["low", "mid", "high"]:
    atms_l = volume_terc[volume_terc == level].index
    m = meta_te["atm_id"].isin(atms_l).values if len(atms_l) else np.zeros(len(meta_te), dtype=bool)
    r = group_row(f"atm_volume:{level}", m)
    if r:
        rows.append(r)

r_all = group_row("all", np.ones(len(yte), dtype=bool))
out = [r_all] + rows
OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"saved {OUT} — {len(out)} groups")
for r in out:
    print(f"  {r['group']:<24} FPR {r['false_positive_rate_0p7']:.4f}  alert {r['alert_rate_0p7']:.4f}  prec {r['precision_0p7']}")