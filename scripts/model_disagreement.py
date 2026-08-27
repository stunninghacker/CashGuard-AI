"""Model B (statistical baseline) + A-vs-B disagreement artifact.

Recreates artifacts/model_b.joblib + artifacts/deep_eval/model_disagreement.json
from the CURRENT data. Trains a logistic baseline on a hand-picked behavioural
feature set; compares against the production XGBoost on the held-out split.
"""
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier
import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.database import engine
from backend.eval.deep_evaluation import load_split_cached
from backend.ml.inference import load_pipeline

ROOT = Path(__file__).resolve().parent.parent
OUT_MODEL = ROOT / "artifacts" / "model_b.joblib"
OUT_JSON = ROOT / "artifacts" / "deep_eval" / "model_disagreement.json"

B_FEATURES = [
    "withdrawals_24h", "n_complaints_city_7d", "n_complaints_city_24h",
    "counterparty_count_24h", "dist_to_complaint_centroid_km",
]

X, meta, y, m_tr, m_val, m_te = load_split_cached(engine)
feat = [c for c in X.columns if not c.startswith("meta_")]
Xf = X[feat]
yte = np.asarray(y[m_te], dtype=float)

pipe = load_pipeline()
model_a = pipe["model"]
cal_a = pipe["calibrator"]

b = LogisticRegression(max_iter=2000, C=0.5)
b.fit(Xf[B_FEATURES][m_tr], y[m_tr])

raw_a = model_a.predict_proba(Xf[m_te])[:, 1]
score_a = cal_a.predict_proba(raw_a.reshape(-1, 1))[:, 1]
score_b = b.predict_proba(Xf[B_FEATURES][m_te])[:, 1]

from sklearn.metrics import roc_auc_score
auc_a = roc_auc_score(yte, score_a)
auc_b = roc_auc_score(yte, score_b)
diff = np.abs(score_a - score_b)

joblib.dump(b, OUT_MODEL)
out = {
    "model_a": "xgboost",
    "model_b": "logistic-statistical-baseline",
    "model_a_roc_auc": round(auc_a, 4),
    "model_b_roc_auc": round(auc_b, 4),
    "median_abs_disagreement": round(float(np.median(diff)), 4),
    "p95_abs_disagreement": round(float(np.percentile(diff, 95)), 4),
    "disagreement_rule": "Confidence downgraded one level when |A-B| > 0.20; HOLD ACTION when |A-B| > 0.35.",
    "b_features": B_FEATURES,
    "label": "CONTROLLED SYNTHETIC EVALUATION",
}
OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"A AUC {auc_a:.4f} | B AUC {auc_b:.4f} | med |A-B| {np.median(diff):.4f} | p95 {np.percentile(diff, 95):.4f}")
print(f"saved {OUT_MODEL} + {OUT_JSON}")