"""Multi-horizon forecast evaluation (2/6/12/24/48h) — vectorized.

Uses the EXISTING 24h-trained model and evaluates capture/precision of fraud
within each horizon of the forecast point. Honest: short horizons are expected
to be weaker; the artifact drives the dashboard's "FORECAST HORIZON / MODEL
CONFIDENCE AT THIS HORIZON" panel and the INSUFFICIENT-CONFIDENCE rule.

Run: python scripts/horizon_eval.py
Out: artifacts/deep_eval/horizons.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score  # noqa: E402

from backend.database import engine  # noqa: E402
from backend.eval.deep_evaluation import load_split, OUT  # noqa: E402
from backend.ml.features import load_dataframes  # noqa: E402
from backend.ml.inference import load_pipeline  # noqa: E402

HORIZONS = [2, 6, 12, 24, 48, 72]


def confidence_label(h: dict) -> str:
    """Dashboard rule: model confidence at this horizon (synthetic evaluation)."""
    p = h["precision_at_1000_horizon"]
    if p >= 0.70:
        return "HIGH"
    if p >= 0.45:
        return "MEDIUM"
    return "INSUFFICIENT CONFIDENCE — HOLD ACTION for horizon-based recommendations"


def main():
    print("multi-horizon evaluation (2/6/12/24/48h)...")
    X, meta, y, m_tr, m_val, m_te = load_split(engine)
    Xte, yte, metate = X[m_te], y[m_te], meta[m_te]
    pipe = load_pipeline()
    model = pipe["model"]
    cal = pipe.get("calibrator")
    raw = model.predict_proba(Xte)[:, 1]
    score = cal.predict_proba(raw.reshape(-1, 1))[:, 1] if cal else raw

    fr = load_dataframes(engine)[1]
    fr = fr[fr["is_fraud_withdrawal"].astype(bool)].copy()
    fr_by_atm = {a: np.sort(s.to_numpy()) for a, s in fr.groupby("atm_id")["timestamp"]}

    df = pd.DataFrame({
        "atm_id": metate["atm_id"].to_numpy(),
        "day": metate["day"].to_numpy(),
        "score": score,
    })
    days = df["day"].to_numpy()
    atms = df["atm_id"].to_numpy()
    rows = []
    for h in HORIZONS:
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
        yh = df["y_h"].to_numpy()
        top1000 = order[:1000]
        rows.append({
            "horizon_hours": h,
            "roc_auc": round(float(roc_auc_score(yh, df["score"].to_numpy())), 4),
            "pr_auc": round(float(average_precision_score(yh, df["score"].to_numpy())), 4),
            "brier": round(float(brier_score_loss(yh, df["score"].to_numpy())), 4),
            "precision_at_1000_horizon": round(float(yh[top1000].mean()), 4),
            "recall_at_1000_horizon": round(float(yh[top1000].sum() / max(int(yh.sum()), 1)), 4),
            "capture_rate_top1000": round(float(yh[top1000].sum() / max(int(yh.sum()), 1)), 4),
            "false_alert_rate_0p7_horizon": round(float((~yh.astype(bool))[score >= 0.7].mean()), 4) if (score >= 0.7).sum() else None,
            "horizon_event_rate": round(float(yh.mean()), 4),
            "calibration_note": "score is the 24h-calibrated probability; per-horizon Brier is reported against the horizon event label (event rate is low at short horizons, so Brier is dominated by the majority class — reported for completeness, interpreted alongside precision@K and event rate)",
            "confidence": confidence_label({"precision_at_1000_horizon": round(float(yh[top1000].mean()), 4)}),
        })
        print(f"  {h:>2}h: P@1000 {rows[-1]['precision_at_1000_horizon']} recall {rows[-1]['recall_at_1000_horizon']} PR {rows[-1]['pr_auc']} -> {rows[-1]['confidence']}")
    out = {"label": "CONTROLLED SYNTHETIC EVALUATION", "model": "24h-trained XGBoost, evaluated per horizon",
           "confidence_rule": "HIGH >=0.70 | MEDIUM >=0.45 | INSUFFICIENT otherwise (HOLD ACTION for horizon-based recs)",
           "horizons": rows}
    (OUT / "horizons.json").write_text(json.dumps(out, indent=2))
    print("saved:", OUT / "horizons.json")


if __name__ == "__main__":
    main()