"""
Feature engineering — turns raw complaint/ATM/withdrawal tables into the
(ATM, day) risk feature matrix.

Prediction task:
    For every ATM and every day, predict P(any fraud withdrawal at this ATM
    in the next 24 hours).

Feature families (all computed from data STRICTLY BEFORE the target day —
no leakage):
    1. Complaint signals (city/district level)   — surge detection
    2. Withdrawal signals (ATM level, hourly)    — cash-out behaviour
    3. Account-linkage signals                   — mule account activity
    4. Geospatial signals                        — distance to complaint centroid
    5. Calendar signals                          — day-of-week / weekend / trend

Production note: in a real deployment this module would read from a
warehouse fed by NCRP/CFCFRMS APIs + bank transaction feeds (same schemas).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine

from ..data.synthetic_data import CITIES

COMPLAINT_TYPES = ["phishing", "investment_fraud", "job_fraud", "upi_fraud"]

FEATURE_COLUMNS = [
    # complaint surge signals (city)
    "n_complaints_city_24h",
    "n_complaints_city_7d",
    "hours_since_last_complaint_city",
    "n_complaints_district_24h",
    "t_phishing_7d",
    "t_investment_fraud_7d",
    "t_job_fraud_7d",
    "t_upi_fraud_7d",
    # ATM withdrawal behaviour
    "withdrawals_1h",
    "withdrawals_6h",
    "withdrawals_24h",
    "amount_sum_24h",
    "distinct_accounts_24h",
    "linked_proportion_24h",
    # behavioural signature (IBA mule-account characteristics)
    "transaction_frequency_24h",   # withdrawals per distinct account
    "counterparty_count_24h",      # distinct mule accounts active at this ATM
    "fund_velocity_24h",           # INR/hour through this ATM
    "activity_spike_flag",         # sudden withdrawal surge vs. ATM baseline
    # self-exciting temporal intensity (Hawkes over PAST complaints only)
    "hawkes_intensity_24h",
    # geospatial
    "dist_to_complaint_centroid_km",
    "dist_to_city_center_km",
    # calendar
    "day_of_week",
    "is_weekend",
    "days_since_epoch",
]


def _haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Great-circle distance in km (vectorised)."""
    r = 6371.0
    p = np.pi / 180.0
    a = (
        0.5
        - np.cos((lat2 - lat1) * p) / 2
        + np.cos(lat1 * p) * np.cos(lat2 * p) * (1 - np.cos((lon2 - lon1) * p)) / 2
    )
    return 2 * r * np.arcsin(np.sqrt(a))


def load_dataframes(engine: Engine) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read the three raw tables into pandas (mirrors warehouse ETL output)."""
    atms = pd.read_sql(
        "SELECT atm_id, bank_name, branch_name, city, district, state, pin, "
        "police_station_area, latitude, longitude FROM atms",
        engine,
    )
    comp = pd.read_sql(
        "SELECT filing_timestamp, complaint_type, victim_city, victim_district, "
        "victim_lat, victim_lon, linked_account_token, amount_lost FROM complaints",
        engine,
        parse_dates=["filing_timestamp"],
    )
    wd = pd.read_sql(
        "SELECT timestamp, atm_id, account_token, amount, is_fraud_withdrawal FROM withdrawals",
        engine,
        parse_dates=["timestamp"],
    )
    wd["is_fraud_withdrawal"] = wd["is_fraud_withdrawal"].fillna(False).astype(bool)
    return comp, wd, atms


def build_features(
    engine: Engine,
    days: list[pd.Timestamp] | pd.DatetimeIndex,
    comp: pd.DataFrame | None = None,
    wd: pd.DataFrame | None = None,
    atms: pd.DataFrame | None = None,
    hawkes_params: dict[str, tuple[float, float, float]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build the feature matrix for the given days.

    Returns (X, meta) where X has FEATURE_COLUMNS (row per atm-day, aligned
    with the master grid order) and meta carries ATM identity/geography.
    """
    if comp is None or wd is None or atms is None:
        comp, wd, atms = load_dataframes(engine)

    days = pd.DatetimeIndex(pd.to_datetime(list(days))).normalize()
    start = days.min()
    end = days.max()

    comp = comp.copy()
    comp["day"] = comp["filing_timestamp"].dt.normalize()
    wd = wd.copy()
    wd["day"] = wd["timestamp"].dt.normalize()
    wd["hour"] = wd["timestamp"].dt.floor("h")

    # Full day range: earliest data day -> last REQUESTED day. Rolling windows
    # must extend past the last day that has records (e.g. forecasting tomorrow)
    # so counts over [day-1, day] are correct even when `day` itself is empty.
    full_days = pd.date_range(min(comp["day"].min(), wd["day"].min()), end, freq="D")

    # ------------------------- master grid -------------------------
    grid = pd.DataFrame(
        {
            "atm_id": np.repeat(atms["atm_id"].to_numpy(), len(days)),
            "day": np.tile(days, len(atms)),
        }
    )
    grid["city"] = grid["atm_id"].map(atms.set_index("atm_id")["city"])
    grid["day_of_week"] = grid["day"].dt.dayofweek
    grid["is_weekend"] = (grid["day"].dt.dayofweek >= 5).astype(int)
    # Fixed epoch reference so training & inference see the same scale.
    grid["days_since_epoch"] = (grid["day"] - pd.Timestamp("2024-01-01")).dt.days

    # ------------------------- complaints: city level -------------------------
    cities = sorted(comp["victim_city"].unique())
    city_day = pd.DataFrame(
        {
            "city": np.repeat(cities, len(full_days)),
            "day": np.tile(full_days, len(cities)),
        }
    )
    cc = city_day.merge(
        comp.groupby(["victim_city", "day"], as_index=False)
        .size()
        .rename(columns={"victim_city": "city", "size": "n"}),
        on=["city", "day"],
        how="left",
    ).fillna({"n": 0})
    cc = cc.sort_values(["city", "day"])
    cc["n_complaints_city_24h"] = (
        cc.groupby("city")["n"].rolling(2, min_periods=1).sum().reset_index(level=0, drop=True)
    )
    cc["n_complaints_city_7d"] = (
        cc.groupby("city")["n"].rolling(8, min_periods=1).sum().reset_index(level=0, drop=True)
    )
    cc = cc[["city", "day", "n_complaints_city_24h", "n_complaints_city_7d"]]

    # ------------------------- complaints: hours since last -------------------------
    comp_s = comp[["victim_city", "filing_timestamp"]].sort_values(["victim_city", "filing_timestamp"])
    # merge_asof requires the 'on' key sorted within each group — merge per city.
    asof_parts = []
    for city in cities:
        dg = city_day[city_day["city"] == city].sort_values("day").rename(columns={"city": "victim_city"})
        cs = (
            comp_s[comp_s["victim_city"] == city]
            .sort_values("filing_timestamp")
            .rename(columns={"filing_timestamp": "ts"})
            .drop(columns=["victim_city"])
        )
        part = pd.merge_asof(dg, cs, left_on="day", right_on="ts", direction="backward")
        asof_parts.append(part)
    asof = pd.concat(asof_parts, ignore_index=True)
    asof["hours_since_last_complaint_city"] = (
        (asof["day"] - asof["ts"]).dt.total_seconds() / 3600.0
    )
    asof["hours_since_last_complaint_city"] = asof["hours_since_last_complaint_city"].fillna(24 * 366)
    asof = asof.rename(columns={"victim_city": "city"})[["city", "day", "hours_since_last_complaint_city"]]

    # ------------------------- complaints: district 24h -------------------------
    districts = sorted(comp["victim_district"].unique())
    dist_day = pd.DataFrame(
        {
            "victim_district": np.repeat(districts, len(full_days)),
            "day": np.tile(full_days, len(districts)),
        }
    )
    cd = dist_day.merge(
        comp.groupby(["victim_district", "day"], as_index=False)
        .size()
        .rename(columns={"size": "n"}),
        on=["victim_district", "day"],
        how="left",
    ).fillna({"n": 0})
    cd = cd.sort_values(["victim_district", "day"])
    cd["n_complaints_district_24h"] = (
        cd.groupby("victim_district")["n"].rolling(2, min_periods=1).sum().reset_index(level=0, drop=True)
    )
    city_district = (
        comp.groupby("victim_city")["victim_district"].first().to_dict()
    )  # city -> district mapping
    cd["city"] = cd["victim_district"].map({v: k for k, v in city_district.items()})
    cd = cd[["city", "day", "n_complaints_district_24h"]]

    # ------------------------- complaints: type distribution (7d) -------------------------
    ct_raw = comp.groupby(["victim_city", "day", "complaint_type"], as_index=False).size()
    ct_raw = ct_raw.pivot_table(
        index=["victim_city", "day"], columns="complaint_type", values="size", fill_value=0
    ).reset_index()
    for t in COMPLAINT_TYPES:
        if t not in ct_raw.columns:
            ct_raw[t] = 0
    ct = city_day.merge(ct_raw.rename(columns={"victim_city": "city"}), on=["city", "day"], how="left").fillna(0)
    ct = ct.sort_values(["city", "day"])
    rolled = ct.groupby("city")[COMPLAINT_TYPES].rolling(8, min_periods=1).sum().reset_index(level=0, drop=True)
    for t in COMPLAINT_TYPES:
        ct[f"t_{t}_7d"] = rolled[t]
    ct = ct[["city", "day"] + [f"t_{t}_7d" for t in COMPLAINT_TYPES]]

    # ------------------------- complaints: centroid (7d) -------------------------
    clat = (
        comp.groupby(["victim_city", "day"], as_index=False)["victim_lat"]
        .sum()
        .rename(columns={"victim_city": "city", "victim_lat": "lat_sum"})
    )
    clon = (
        comp.groupby(["victim_city", "day"], as_index=False)["victim_lon"]
        .sum()
        .rename(columns={"victim_city": "city", "victim_lon": "lon_sum"})
    )
    cen = city_day.merge(clat, on=["city", "day"], how="left").merge(
        clon, on=["city", "day"], how="left"
    )
    cen = cen.sort_values(["city", "day"]).fillna(0)
    cen[["lat_sum", "lon_sum"]] = (
        cen.groupby("city")[["lat_sum", "lon_sum"]].rolling(8, min_periods=1).sum().reset_index(level=0, drop=True)
    )
    cen = cen.merge(cc[["city", "day", "n_complaints_city_7d"]], on=["city", "day"], how="left")
    cen["clat"] = np.where(cen["n_complaints_city_7d"] > 0, cen["lat_sum"] / cen["n_complaints_city_7d"].clip(lower=1), cen["city"].map({c: m["lat"] for c, m in CITIES.items()}))
    cen["clon"] = np.where(cen["n_complaints_city_7d"] > 0, cen["lon_sum"] / cen["n_complaints_city_7d"].clip(lower=1), cen["city"].map({c: m["lon"] for c, m in CITIES.items()}))
    cen = cen[["city", "day", "clat", "clon"]]

    # ------------------------- withdrawals: hourly ATM matrices -------------------------
    hours_all = pd.date_range(start - pd.Timedelta(hours=25), end + pd.Timedelta(hours=23), freq="h")
    atm_ids = atms["atm_id"].to_numpy()

    def hourly_matrix(series_frame, value_col: str | None):
        if value_col is None:
            m = series_frame.groupby(["atm_id", "hour"]).size()
        else:
            m = series_frame.groupby(["atm_id", "hour"])[value_col].sum()
        m = m.unstack(fill_value=0.0)
        return m.reindex(index=atm_ids, columns=hours_all, fill_value=0.0).astype(np.float32)

    w_h = hourly_matrix(wd, None)
    am_h = hourly_matrix(wd, "amount")
    lk_h = hourly_matrix(wd[wd["account_token"].isin(set(comp["linked_account_token"].unique()))], None)

    # Rolling sums along the time axis (pandas 3.x removed axis=1 in rolling,
    # so transpose -> roll over rows -> transpose back).
    def roll_hours(mat: pd.DataFrame, hours: int) -> pd.DataFrame:
        return mat.T.rolling(hours, min_periods=1).sum().T

    w1 = roll_hours(w_h, 1)
    w6 = roll_hours(w_h, 6)
    w24 = roll_hours(w_h, 24)
    am24 = roll_hours(am_h, 24)
    lk24 = roll_hours(lk_h, 24)

    col_idx = days - pd.Timedelta(hours=1)  # hour bucket immediately before each day start

    def extract(mat: pd.DataFrame, name: str) -> pd.Series:
        sub = mat.loc[atm_ids, col_idx].copy()
        sub.columns = days  # relabel the hour buckets as the days they predict
        s = sub.stack()
        s.index = s.index.set_names(["atm_id", "day"])
        return s.rename(name)

    wd_feats = pd.DataFrame(
        {
            "withdrawals_1h": extract(w1, "withdrawals_1h"),
            "withdrawals_6h": extract(w6, "withdrawals_6h"),
            "withdrawals_24h": extract(w24, "withdrawals_24h"),
            "amount_sum_24h": extract(am24, "amount_sum_24h"),
            "linked_withdrawals_24h": extract(lk24, "linked_withdrawals_24h"),
        }
    ).reset_index()
    wd_feats["linked_proportion_24h"] = np.where(
        wd_feats["withdrawals_24h"] > 0,
        wd_feats["linked_withdrawals_24h"] / wd_feats["withdrawals_24h"],
        0.0,
    )
    wd_feats = wd_feats.drop(columns=["linked_withdrawals_24h"])

    # ---- behavioural signature features (IBA mule-account characteristics) ----
    wd_feats["fund_velocity_24h"] = wd_feats["amount_sum_24h"] / 24.0  # INR/hour
    wd_feats["activity_spike_flag"] = np.where(
        (wd_feats["withdrawals_1h"] >= 3)
        & (wd_feats["withdrawals_1h"] >= 2.0 * wd_feats["withdrawals_24h"] / 24.0),
        1.0,
        0.0,
    )

    # ------------------------- withdrawals: distinct accounts (day level) -------------------------
    acct_d = wd.groupby(["atm_id", "day"], as_index=False)["account_token"].nunique()
    acct_grid = pd.DataFrame(
        {
            "atm_id": np.repeat(atm_ids, len(full_days)),
            "day": np.tile(full_days, len(atms)),
        }
    )
    acct_grid = acct_grid.merge(acct_d, on=["atm_id", "day"], how="left").fillna(0)
    acct_grid = acct_grid.sort_values(["atm_id", "day"])
    acct_grid["distinct_accounts_24h"] = (
        acct_grid.groupby("atm_id")["account_token"].rolling(2, min_periods=1).sum().reset_index(level=0, drop=True)
    )
    acct_grid = acct_grid[["atm_id", "day", "distinct_accounts_24h"]]

    # ------------------------- withdrawals: counterparty count (mule accounts, day level) -------------------------
    mule_ids = set(comp["linked_account_token"].unique())
    lk_acct_d = (
        wd[wd["account_token"].isin(mule_ids)]
        .groupby(["atm_id", "day"], as_index=False)["account_token"]
        .nunique()
    )
    cp_grid = pd.DataFrame(
        {
            "atm_id": np.repeat(atm_ids, len(full_days)),
            "day": np.tile(full_days, len(atms)),
        }
    )
    cp_grid = cp_grid.merge(lk_acct_d, on=["atm_id", "day"], how="left").fillna(0)
    cp_grid = cp_grid.sort_values(["atm_id", "day"])
    cp_grid["counterparty_count_24h"] = (
        cp_grid.groupby("atm_id")["account_token"].rolling(2, min_periods=1).sum().reset_index(level=0, drop=True)
    )
    cp_grid = cp_grid[["atm_id", "day", "counterparty_count_24h"]]

    # ------------------------- geospatial: distance features -------------------------
    geo = atms[["atm_id", "city", "latitude", "longitude"]].merge(
        cen, on="city", how="left"
    )
    geo = geo.merge(
        pd.DataFrame(
            {
                "city": list(CITIES.keys()),
                "cc_lat": [CITIES[c]["lat"] for c in CITIES],
                "cc_lon": [CITIES[c]["lon"] for c in CITIES],
            }
        ),
        on="city",
        how="left",
    )
    geo["dist_to_complaint_centroid_km"] = _haversine_km(
        geo["latitude"], geo["longitude"], geo["clat"], geo["clon"]
    )
    geo["dist_to_city_center_km"] = _haversine_km(
        geo["latitude"], geo["longitude"], geo["cc_lat"], geo["cc_lon"]
    )
    geo = geo[["atm_id", "day", "dist_to_complaint_centroid_km", "dist_to_city_center_km"]]

    # ------------------------- self-exciting (Hawkes) intensity -------------------------
    # λ(day) per CITY from PAST complaint timestamps only (strict mask tᵢ < day).
    # Params are fitted on the training period by train.py and stored in the
    # artifact; prediction-time safety is asserted by hawkes.self_test().
    if hawkes_params:
        from .hawkes import intensity_at

        epoch = comp["day"].min()
        full_day_vals = (full_days - epoch).total_seconds() / 86400.0
        hawkes_city_day: dict[str, np.ndarray] = {}
        for city, params in hawkes_params.items():
            events = comp.loc[comp["victim_city"] == city, "day"]
            event_vals = (events - epoch).dt.total_seconds().to_numpy(dtype=float) / 86400.0
            hawkes_city_day[city] = intensity_at(full_day_vals, event_vals, *params)
        hk = pd.DataFrame({"day": full_days})
        for city, vals in hawkes_city_day.items():
            hk[city] = vals
        hk_long = hk.melt(id_vars="day", var_name="city", value_name="hawkes_intensity_24h")
        grid = grid.merge(hk_long, on=["city", "day"], how="left")
    else:
        grid["hawkes_intensity_24h"] = 0.0

    # ------------------------- assemble -------------------------
    atm_meta = atms.rename(
        columns={
            "latitude": "latitude",
            "longitude": "longitude",
        }
    )
    X = (
        grid.merge(cc, on=["city", "day"], how="left")
        .merge(asof, on=["city", "day"], how="left")
        .merge(cd[["city", "day", "n_complaints_district_24h"]], on=["city", "day"], how="left")
        .merge(ct[["city", "day"] + [f"t_{t}_7d" for t in COMPLAINT_TYPES]], on=["city", "day"], how="left")
        .merge(wd_feats, on=["atm_id", "day"], how="left")
        .merge(acct_grid, on=["atm_id", "day"], how="left")
        .merge(cp_grid, on=["atm_id", "day"], how="left")
        .merge(geo, on=["atm_id", "day"], how="left")
        .merge(atm_meta[["atm_id", "bank_name", "branch_name", "district", "state", "pin", "police_station_area", "latitude", "longitude"]], on="atm_id", how="left")
    )
    # transaction frequency = withdrawals per distinct account (behavioural trait)
    X["transaction_frequency_24h"] = np.where(
        X["withdrawals_24h"] > 0,
        X["withdrawals_24h"] / X["distinct_accounts_24h"].clip(lower=1.0),
        0.0,
    )

    meta = X[["atm_id", "bank_name", "branch_name", "city", "district", "state", "pin", "police_station_area", "latitude", "longitude", "day"]].copy()
    X = X[FEATURE_COLUMNS].fillna(0.0).astype(np.float32)
    return X, meta


def build_target(
    wd: pd.DataFrame,
    atms: pd.DataFrame,
    days: pd.DatetimeIndex,
) -> pd.Series:
    """
    Target per (atm, day): 1 if any fraud withdrawal happened at that ATM
    during [day, day+24h) — i.e. the next 24 hours after the feature snapshot.
    """
    wd = wd.copy()
    wd["day"] = wd["timestamp"].dt.normalize()
    fr = wd[wd["is_fraud_withdrawal"]].groupby(["atm_id", "day"], as_index=False).size()
    grid = pd.DataFrame(
        {
            "atm_id": np.repeat(atms["atm_id"].to_numpy(), len(days)),
            "day": np.tile(days, len(atms)),
        }
    )
    merged = grid.merge(fr, on=["atm_id", "day"], how="left")
    return (merged["size"].fillna(0) > 0).astype(int).to_numpy()