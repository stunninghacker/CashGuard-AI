# cross_val_auc_ci.py
"""5-fold cross-validation for the CashGuard two-stage model.

Builds the same ATM-day feature matrix / target used by training
(backend.ml.features.build_features + build_target), then runs stratified
5-fold CV with the TwoStageModel estimator (XGBoost + Platt calibration).
Reports per-fold AUC, mean, std and the 95% CI, and writes
`artifacts/evaluation/auc_ci.json`.
"""

import json
import pathlib
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

# Project imports
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.database import engine  # noqa: E402
from backend.ml.two_stage_model import TwoStageModel  # noqa: E402
from backend.ml.features import build_features, build_target, load_dataframes  # noqa: E402

K_FOLDS = 5
RANDOM_STATE = 42
OUTPUT_JSON = ROOT / "artifacts" / "evaluation" / "auc_ci.json"
OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)


def build_xy():
    """Return (X, y) over the full dataset — mirrors scripts/train_model.py."""
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
    days = all_days[2:]  # skip warm-up days (rolling features need history)

    X, _meta = build_features(engine, days, comp, wd, atms)  # hawkes: zeros w/o fitted params
    y = build_target(wd, atms, days)
    return X, y


def main():
    X, y = build_xy()
    y = np.asarray(y)
    print(f"Dataset: {len(X):,} ATM-day rows, {int(y.sum()):,} positives "
          f"({y.mean():.4%})")

    skf = StratifiedKFold(n_splits=K_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    aucs = []
    for fold, (train_idx, test_idx) in enumerate(skf.split(X, y), start=1):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        model = TwoStageModel()
        model.fit(X_train, y_train)
        prob = model.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, prob)
        aucs.append(auc)
        print(f"Fold {fold}: AUC = {auc:.4f}")

    mean_auc = float(np.mean(aucs))
    std_auc = float(np.std(aucs, ddof=1))
    ci_low = mean_auc - 1.96 * std_auc / np.sqrt(K_FOLDS)
    ci_high = mean_auc + 1.96 * std_auc / np.sqrt(K_FOLDS)
    summary = {
        "k_folds": K_FOLDS,
        "n_rows": int(len(X)),
        "n_positives": int(y.sum()),
        "fold_aucs": [round(v, 4) for v in aucs],
        "mean_auc": round(mean_auc, 4),
        "std_auc": round(std_auc, 4),
        "ci_95": [round(ci_low, 4), round(ci_high, 4)],
    }
    OUTPUT_JSON.write_text(json.dumps(summary, indent=2))
    print("\n---\nAUC 5-fold CV summary:")
    print(f"Mean AUC: {mean_auc:.4f} ± {std_auc:.4f}")
    print(f"95% CI: [{ci_low:.4f}, {ci_high:.4f}]")
    print(f"Written to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
