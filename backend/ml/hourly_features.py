"""Hourly-resolution feature builder (sub-daily mode, HOURLY_MODE flag) — vectorized."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .features import load_dataframes

HOURLY_FEATURE_COLUMNS = [
    "withdrawals_1h", "withdrawals_6h", "withdrawals_24h", "amount_sum_24h",
    "amount_mean_24h", "distinct_accounts_24h", "counterparty_count_24h",
    "linked_proportion_24h", "transaction_frequency_24h",
    "n_complaints_city_24h", "n_complaints_city_7d",
    "hour_of_day", "is_night",
]


def build_hourly_features(engine, start_day, days: int, atms_subset=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Vectorized per-ATM hourly features over [start_day, start_day+days)."""
    comp, wd, atms = load_dataframes(engine)
    linked_tokens = set(comp["linked_account_token"].dropna().unique())

    start = pd.Timestamp(start_day)
    end = start + pd.Timedelta(days=days)
    wd = wd.copy()
    comp = comp.copy()
    wd["ts"] = pd.to_datetime(wd["timestamp"])
    comp["ts"] = pd.to_datetime(comp["filing_timestamp"])
    if atms_subset is not None:
        atms = atms[atms["atm_id"].isin(atms_subset)]
        wd = wd[wd["atm_id"].isin(atms_subset)]

    hours = pd.date_range(start, end, freq="h")[:-1]

    # --- withdrawal aggregates per (atm, hour) ---
    wd = wd[(wd["ts"] >= start - pd.Timedelta(days=7)) & (wd["ts"] < end)]
    wd["linked"] = wd["account_token"].isin(linked_tokens).astype(int)
    hourly_w = (
        wd.set_index("ts")
        .groupby("atm_id")["amount"]
        .resample("h")
        .agg(["count", "sum"])
        .rename(columns={"count": "n", "sum": "amt"})
    )
    wd_l = wd.set_index("ts").groupby("atm_id")["linked"].resample("h").sum()
    wd_a = wd.set_index("ts").groupby("atm_id")["account_token"].resample("h").nunique()

    idx = pd.MultiIndex.from_product([sorted(atms["atm_id"].unique()), hours], names=["atm_id", "ts"])
    W = pd.DataFrame(index=idx)
    W["n"] = hourly_w["n"].reindex(idx, fill_value=0)
    W["amt"] = hourly_w["amt"].reindex(idx, fill_value=0)
    W["linked"] = wd_l.reindex(idx, fill_value=0)
    W["nacc"] = wd_a.reindex(idx, fill_value=0)
    W["w1"] = W["n"]
    W["w6"] = W["n"].groupby("atm_id").transform(lambda s: s.rolling(6, min_periods=1).sum())
    W["w24"] = W["n"].groupby("atm_id").transform(lambda s: s.rolling(24, min_periods=1).sum())
    W["amt24"] = W["amt"].groupby("atm_id").transform(lambda s: s.rolling(24, min_periods=1).sum())
    W["nacc24"] = W["nacc"].groupby("atm_id").transform(lambda s: s.rolling(24, min_periods=1).sum())
    W["lnk24"] = W["linked"].groupby("atm_id").transform(lambda s: s.rolling(24, min_periods=1).sum())

    # --- city complaint aggregates per hour ---
    comp = comp[(comp["ts"] >= start - pd.Timedelta(days=7)) & (comp["ts"] < end)]
    city_h = comp.groupby(["victim_city", pd.Grouper(key="ts", freq="h")]).size().unstack(level=0).reindex(hours, fill_value=0)
    city_c24 = city_h.rolling(24, min_periods=1).sum()
    city_c7 = city_h.rolling(168, min_periods=1).sum()

    city_map = atms.set_index("atm_id")["city"].to_dict()
    rows = []
    for atm in sorted(atms["atm_id"].unique()):
        city = city_map[atm]
        w = W.loc[atm]
        c24 = city_c24[city].reindex(hours).fillna(0).to_numpy()
        c7 = city_c7[city].reindex(hours).fillna(0).to_numpy()
        n24 = w["w24"].to_numpy()
        rows.append(pd.DataFrame({
            "atm_id": atm,
            "hour": hours,
            "withdrawals_1h": w["w1"].to_numpy(),
            "withdrawals_6h": w["w6"].to_numpy(),
            "withdrawals_24h": n24,
            "amount_sum_24h": w["amt24"].to_numpy(),
            "amount_mean_24h": np.divide(w["amt24"].to_numpy(), np.maximum(n24, 1)),
            "distinct_accounts_24h": w["nacc24"].to_numpy(),
            "counterparty_count_24h": w["nacc24"].to_numpy(),
            "linked_proportion_24h": np.divide(w["lnk24"].to_numpy(), np.maximum(w["nacc24"].to_numpy(), 1)),
            "transaction_frequency_24h": n24 / 24.0,
            "n_complaints_city_24h": c24,
            "n_complaints_city_7d": c7,
            "hour_of_day": hours.hour.to_numpy(),
            "is_night": ((hours.hour >= 19) | (hours.hour < 5)).astype(int),
        }))
    df = pd.concat(rows, ignore_index=True)
    meta = df[["atm_id", "hour"]].reset_index(drop=True)
    X = df[HOURLY_FEATURE_COLUMNS].reset_index(drop=True)
    return X, meta


def build_hourly_target(engine, meta: pd.DataFrame) -> np.ndarray:
    """Label: any confirmed fraud withdrawal at this ATM within 24h of the hour."""
    _, wd, _ = load_dataframes(engine)
    wd = wd[wd["is_fraud_withdrawal"].astype(bool)].copy()
    wd["ts"] = pd.to_datetime(wd["timestamp"])
    y = np.zeros(len(meta), dtype=float)
    hours = pd.to_datetime(meta["hour"])
    for i, (atm, hour) in enumerate(zip(meta["atm_id"], hours)):
        f = wd[(wd["atm_id"] == atm) & (wd["ts"] >= hour) & (wd["ts"] < hour + pd.Timedelta(hours=24))]
        y[i] = 1.0 if len(f) else 0.0
    return y