'''Two-Stage Predictive Engine for CashGuard AI

Stage 1 — XGBoost classifier over the ATM-day feature matrix
    (the same FEATURE_COLUMNS produced by ``backend.ml.features.build_features``).
Stage 2 — Platt (sigmoid) calibration fitted on a held-out chronological tail,
    so ``predict_proba`` returns honest probabilities instead of raw booster
    scores.

``TwoStageModel`` is a drop-in sklearn-style estimator (fit / predict /
predict_proba) used by evaluation scripts such as ``scripts/cross_val_auc_ci.py``.

The ``compute_*`` helpers below are the engineered-feature transformers named
in the design note. They are defensive: any column they need that is missing
from the input frame yields a zero-filled series rather than a crash.
'''

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

from ..config import SEED

# ---------------------------------------------------------------------------
# Engineered feature transformers (self-contained; no circular imports)
# ---------------------------------------------------------------------------


def _city_column(df: pd.DataFrame) -> str | None:
    for cand in ("city", "victim_city"):
        if cand in df.columns:
            return cand
    return None


def _token_column(df: pd.DataFrame) -> str | None:
    for cand in ("linked_account_token", "victim_account_token", "account_token"):
        if cand in df.columns:
            return cand
    return None


def compute_complaint_surge_ratio(df: pd.DataFrame) -> pd.Series:
    """Complaints in the last 24h vs the trailing 7-day daily mean, per city-day.

    >1.0 means complaint volume is surging relative to the recent baseline.
    """
    city_col = _city_column(df)
    if city_col is None or "day" not in df.columns:
        return pd.Series(0.0, index=df.index)

    counts = (
        df.groupby([city_col, "day"]).size().rename("n").reset_index()
    )
    counts = counts.sort_values("day")
    counts["baseline_7d"] = (
        counts.groupby(city_col)["n"]
        .transform(lambda s: s.shift(1).rolling(7, min_periods=1).mean())
    )
    counts["surge"] = counts["n"] / counts["baseline_7d"].clip(lower=1.0)
    mapper = counts.set_index([city_col, "day"])["surge"]
    keys = list(zip(df[city_col], df["day"]))
    return pd.Series(
        [mapper.get(k, 1.0) for k in keys], index=df.index, dtype=float
    ).fillna(1.0)


def compute_cross_city_mule_spread(df: pd.DataFrame) -> pd.Series:
    """Number of distinct cities each linked account token appears in.

    A token cashing out across many cities is a mule-network signal.
    """
    city_col = _city_column(df)
    token_col = _token_column(df)
    if city_col is None or token_col is None:
        return pd.Series(0.0, index=df.index)

    spread = df.groupby(token_col)[city_col].nunique()
    return df[token_col].map(spread).fillna(0.0).astype(float)


def compute_time_to_withdrawal_hist(df: pd.DataFrame) -> pd.Series:
    """Mean hours from complaint filing to the linked withdrawal, per city-day.

    Short cash-out latency is the operational window the system races against.
    Rows without both timestamps get the global mean (0.0 if unknowable).
    """
    if not {"filing_timestamp", "withdrawal_timestamp"}.issubset(df.columns):
        return pd.Series(0.0, index=df.index)

    delta_h = (
        df["withdrawal_timestamp"] - df["filing_timestamp"]
    ).dt.total_seconds() / 3600.0
    valid = delta_h.between(0, 168)  # 0..7 days is the plausible cash-out band
    if not valid.any():
        return pd.Series(0.0, index=df.index)
    return delta_h.where(valid).fillna(delta_h[valid].mean()).astype(float)


def compute_atm_cold_start_flag(df: pd.DataFrame) -> pd.Series:
    """1 while an ATM is inside its first COLD_START_DAYS observed days.

    New/quiet ATMs have no behavioural baseline, so the model must not
    over-trust their rolling features.
    """
    if "atm_id" not in df.columns or "day" not in df.columns:
        return pd.Series(0.0, index=df.index)

    COLD_START_DAYS = 7
    order = df.sort_values("day")
    nth_day = order.groupby("atm_id")["day"].rank(method="dense")
    flag = (nth_day <= COLD_START_DAYS).astype(float)
    return flag.reindex(df.index).fillna(0.0)


def compute_complaint_amount_cluster(df: pd.DataFrame) -> pd.Series:
    """Size of the amount-cluster each complaint row sits in, per city-day.

    Counts complaints in the same city-day whose amount is within +/-10% of
    the row's amount — many near-identical amounts is a coordinated-campaign
    fingerprint. Falls back to the city-day complaint count when no amount
    column exists.
    """
    city_col = _city_column(df)
    amount_col = next(
        (c for c in ("amount_lost", "amount") if c in df.columns), None
    )
    if city_col is None or "day" not in df.columns:
        return pd.Series(0.0, index=df.index)

    if amount_col is None:
        return df.groupby([city_col, "day"])[city_col].transform("size").astype(float)

    def _cluster_size(g: pd.DataFrame) -> pd.Series:
        amt = g[amount_col].to_numpy(dtype=float)
        if len(amt) < 2:
            return pd.Series(np.ones(len(g)), index=g.index)
        m = np.abs(amt[:, None] - amt[None, :]) <= 0.10 * np.clip(np.abs(amt[:, None]), 1.0, None)
        return pd.Series(m.sum(axis=1), index=g.index)

    return (
        df.groupby([city_col, "day"], group_keys=False)
        .apply(_cluster_size)
        .reindex(df.index)
        .astype(float)
    )


def enrich_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add the five engineered features to a raw complaint/withdrawal frame."""
    df = df.copy()
    df["complaint_surge_ratio"] = compute_complaint_surge_ratio(df)
    df["cross_city_mule_spread"] = compute_cross_city_mule_spread(df)
    df["time_to_withdrawal_hist"] = compute_time_to_withdrawal_hist(df)
    df["atm_cold_start_flag"] = compute_atm_cold_start_flag(df)
    df["complaint_amount_cluster"] = compute_complaint_amount_cluster(df)
    return df


# ---------------------------------------------------------------------------
# Stage 1 - city-level surge classifier
# ---------------------------------------------------------------------------

_CITY_PARAMS = {
    "n_estimators": 150,
    "max_depth": 4,
    "learning_rate": 0.04,
    "subsample": 0.85,
    "colsample_bytree": 0.8,
    "scale_pos_weight": 3.5,
    "eval_metric": "auc",
}


def train_city_classifier(
    city_features: pd.DataFrame,
    city_targets: np.ndarray,
    params: Dict[str, Any] | None = None,
) -> XGBClassifier:
    """Train the city-level surge classifier.

    city_features: rows are (city, day) with engineered features.
    city_targets:  binary labels — 1 if any fraud ATM in that city the next 24h.
    """
    p = dict(_CITY_PARAMS)
    if params:
        p.update(params)
    model = XGBClassifier(random_state=SEED, **p)
    model.fit(city_features, city_targets)
    return model


def predict_city_proba(model: XGBClassifier, city_features: pd.DataFrame) -> np.ndarray:
    """Return probability of surge for each city-day row."""
    return model.predict_proba(city_features)[:, 1]


# ---------------------------------------------------------------------------
# Stage 2 - ATM-level ranker (calibrated)
# ---------------------------------------------------------------------------

_ATM_PARAMS = {
    "n_estimators": 250,
    "max_depth": 5,
    "learning_rate": 0.03,
    "subsample": 0.8,
    "colsample_bytree": 0.75,
    "scale_pos_weight": 5.0,
    "eval_metric": "aucpr",
}


def train_atm_ranker(
    atm_features: pd.DataFrame,
    atm_targets: np.ndarray,
    params: Dict[str, Any] | None = None,
) -> LogisticRegression:
    """Train the ATM-level XGBoost ranker and fit a Platt calibrator on a
    held-out 20% chronological tail."""
    p = dict(_ATM_PARAMS)
    if params:
        p.update(params)
    base = XGBClassifier(random_state=SEED, **p)
    split_idx = int(0.8 * len(atm_features))
    X_train, X_cal = atm_features.iloc[:split_idx], atm_features.iloc[split_idx:]
    y_train, y_cal = atm_targets[:split_idx], atm_targets[split_idx:]
    base.fit(X_train, y_train)
    raw_cal = base.predict_proba(X_cal)[:, 1]
    calibrator = LogisticRegression().fit(raw_cal.reshape(-1, 1), y_cal)
    return calibrator


def predict_atm_risk(ranker: LogisticRegression, atm_features: pd.DataFrame, base_model: XGBClassifier) -> np.ndarray:
    """Calibrated risk for each ATM-day row (raw booster score -> Platt)."""
    raw = base_model.predict_proba(atm_features)[:, 1]
    return ranker.predict_proba(raw.reshape(-1, 1))[:, 1]


def score_two_stage(
    atm_features: pd.DataFrame,
    atm_targets: np.ndarray,
    params: Dict[str, Any] | None = None,
) -> pd.Series:
    """Fit the ATM ranker + Platt stage and return calibrated risk per row."""
    split_idx = int(0.8 * len(atm_features))
    base = XGBClassifier(
        random_state=SEED,
        **{**_ATM_PARAMS, **(params or {})},
    )
    base.fit(atm_features.iloc[:split_idx], atm_targets[:split_idx])
    calibrator = train_atm_ranker(
        atm_features.iloc[:split_idx], atm_targets[:split_idx], params
    )
    return pd.Series(
        predict_atm_risk(calibrator, atm_features, base), index=atm_features.index
    )


# ---------------------------------------------------------------------------
# sklearn-style estimator used by cross-validation scripts
# ---------------------------------------------------------------------------


class TwoStageModel:
    """Two-stage estimator over the ATM-day feature matrix.

    Stage 1 fits an XGBoost classifier on the leading (1 - calibration_frac)
    of the rows. Stage 2 fits a Platt (sigmoid) calibrator on the remaining
    chronological tail. ``predict_proba`` returns calibrated probabilities;
    if either split is single-class (tiny/imbalanced folds) the calibrator is
    skipped and raw probabilities are returned — CV never crashes on a fold.
    """

    def __init__(
        self,
        params: Dict[str, Any] | None = None,
        calibration_frac: float = 0.2,
        random_state: int = SEED,
    ):
        self.params = params
        self.calibration_frac = calibration_frac
        self.random_state = random_state
        self.model_: XGBClassifier | None = None
        self.calibrator_: LogisticRegression | None = None

    def fit(self, X: pd.DataFrame, y) -> "TwoStageModel":
        p = {
            "n_estimators": 300,
            "max_depth": 6,
            "learning_rate": 0.07,
            "subsample": 0.85,
            "colsample_bytree": 0.8,
            "tree_method": "hist",
            "eval_metric": "aucpr",
        }
        if self.params:
            p.update(self.params)
        y = np.asarray(y)

        split = int(len(X) * (1.0 - self.calibration_frac))
        X_fit, X_cal = X.iloc[:split], X.iloc[split:]
        y_fit, y_cal = y[:split], y[split:]

        self.model_ = XGBClassifier(random_state=self.random_state, **p)
        self.model_.fit(X_fit, y_fit)

        if (
            len(X_cal) > 0
            and len(np.unique(y_fit)) == 2
            and len(np.unique(y_cal)) == 2
        ):
            raw_cal = self.model_.predict_proba(X_cal)[:, 1]
            self.calibrator_ = LogisticRegression().fit(
                raw_cal.reshape(-1, 1), y_cal
            )
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self.model_ is None:
            raise RuntimeError("TwoStageModel.fit must be called before predict_proba")
        raw = self.model_.predict_proba(X)[:, 1]
        if self.calibrator_ is not None:
            pos = self.calibrator_.predict_proba(raw.reshape(-1, 1))[:, 1]
        else:
            pos = raw
        return np.column_stack([1.0 - pos, pos])

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


# ---------------------------------------------------------------------------
# Entry point used by training scripts
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Two-stage model module loaded. No direct execution defined.")
