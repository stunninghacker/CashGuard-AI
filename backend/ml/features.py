"""
Feature engineering — turns raw complaint/ATM/withdrawal tables into the
(ATM, day) / (ATM, 6h-window) risk feature matrix.

Prediction task:
    For every ATM and every forecast window, predict P(any fraud withdrawal at
    this ATM in the NEXT 24 hours) [daily] — or P(fraud in the NEXT 6 hours)
    [6h windows, experimental].

HONESTY / LEAK-SAFETY RULE (unchanged philosophy; do not regress):
    Every feature is computed from data STRICTLY BEFORE the start of the
    forecast window. The `_shift_window_past` / `_shift_day_past` helpers move
    a window-keyed aggregate forward by one window so a row keyed `d` carries
    ONLY what was observable before `d`. The project already hit label leakage
    once (0.92x -> 0.6273); these additions preserve that safety.

Feature families (all leak-free):
    1. Complaint signals (city/district level)   — surge detection
    2. Withdrawal signals (ATM level, hourly)    — cash-out behaviour
    3. Account-linkage signals                   — mule account activity
    4. Geospatial signals                        — distance to complaint centroid
    5. Calendar signals                          — day-of-week / weekend / salary / festival
    6. NEW (Issue 1): distance-decay kernel, surge velocity, cash-refill cycle,
       historical fraud latency, mule reuse, PIN corridor, salary day, festival
       proximity, prior-alert outcome, complaint-type transition, bank fraud
       rate, night-time ratio.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine

from ..data.synthetic_data import CITIES

COMPLAINT_TYPES = ["phishing", "investment_fraud", "job_fraud", "upi_fraud"]

# Full feature set = 24 original + 12 new (Issue 1).
FEATURE_COLUMNS = [
    # ---- complaint surge signals (city) ----
    "n_complaints_city_24h",
    "n_complaints_city_7d",
    "hours_since_last_complaint_city",
    "n_complaints_district_24h",
    "t_phishing_7d",
    "t_investment_fraud_7d",
    "t_job_fraud_7d",
    "t_upi_fraud_7d",
    # ---- ATM withdrawal behaviour ----
    "withdrawals_1h",
    "withdrawals_6h",
    "withdrawals_24h",
    "amount_sum_24h",
    "distinct_accounts_24h",
    "linked_proportion_24h",
    # ---- behavioural signature (IBA mule-account characteristics) ----
    "transaction_frequency_24h",
    "counterparty_count_24h",
    "fund_velocity_24h",
    "activity_spike_flag",
    # ---- self-exciting temporal intensity (Hawkes over PAST complaints) ----
    "hawkes_intensity_24h",
    # ---- geospatial ----
    "dist_to_complaint_centroid_km",
    "dist_to_city_center_km",
    # ---- calendar ----
    "day_of_week",
    "is_weekend",
    "days_since_epoch",
    # ================= NEW FEATURES (Issue 1) =================
    # 1. exponential distance-decay kernel sigma=5 km (city complaints -> ATM)
    "complaint_decay_5km",
    # 2. complaint surge velocity: complaints/hour last 3h / 24h baseline (city)
    "complaint_surge_velocity",
    # 3. ATM cash-replenishment cycle flag (~every 3 days; fraud spikes post-refill)
    "cash_refill_cycle_flag",
    # 4. time-to-first-withdrawal after complaint (historical median by type -> lag)
    "med_fraud_latency_type_days",
    # 5. mule account reuse count (same account used in prior frauds at this ATM)
    "mule_reuse_count_7d",
    # 6. victim PIN code -> ATM PIN distance (fraud corridor score, coarse city level)
    "pin_corridor_dist_km",
    # 7. day-of-month flag (salary credit days 1,5,10,15)
    "is_salary_day",
    # 8. festival / holiday proximity (days to nearest major Indian festival)
    "days_to_festival",
    # 9. previous alert outcome at this ATM (prior fraud-after-alert signal)
    "prior_alert_fraud_flag",
    # 10. complaint-type transition matrix (UPI complaint -> ATM withdrawal pattern)
    "upi_to_atm_transition_flag",
    # 11. bank-specific fraud rate (historical, leak-free pre-window)
    "bank_fraud_rate_hist",
    # 12. night-time transaction ratio (fraud clusters 22:00-03:00)
    "night_ratio_24h",
    # ================= NEW FEATURES (Issue 1b — amount behavioural signature) =================
    # 13. trailing-7d MEAN / MAX withdrawal amount at this ATM (fraud cash-outs
    #     are large: mule_velocity lognormal; legit busy-ATM clusters are lower)
    "amount_mean_7d",
    "amount_max_7d",
    # 14. count of trailing-7d withdrawals that are suspiciously ROUND (amount
    #     %1000 == 0, generator round_bias) — a fraud cash-out tell
    "round_count_7d",
    # 15. count of trailing-7d withdrawals above ₹20k / ₹50k (heavy-tail fraud)
    "large_count_7d",
    "heavy_count_7d",
    # 16. YESTERDAY-only amount signature (same-ATM chunk persistence across days)
    "amount_max_1d",
    "large_count_1d",
    # 17. exponentially-decayed past-fraud count (~2d half-life) — hot-ATM rotation
    "fraud_decay_7d",
]

# 6-window feature set: same 12 new + daily signals re-keyed. We reuse the
# daily builders where the window size doesn't change the semantics, and add
# 6h-specific withdrawal signals. See build_features_6h.
FEATURE_COLUMNS_6H = [
    "withdrawals_1h",
    "withdrawals_6h",
    "withdrawals_24h",
    "amount_sum_6h",
    "distinct_accounts_6h",
    "linked_proportion_6h",
    "fund_velocity_6h",
    "activity_spike_flag_6h",
    "night_ratio_6h",
    "n_complaints_city_6h",
    "n_complaints_city_24h",
    "hours_since_last_complaint_city",
    "t_phishing_7d",
    "t_investment_fraud_7d",
    "t_job_fraud_7d",
    "t_upi_fraud_7d",
    "complaint_decay_5km",
    "complaint_surge_velocity",
    "cash_refill_cycle_flag",
    "med_fraud_latency_type_days",
    "mule_reuse_count_7d",
    "pin_corridor_dist_km",
    "is_salary_day",
    "days_to_festival",
    "prior_alert_fraud_flag",
    "upi_to_atm_transition_flag",
    "bank_fraud_rate_hist",
    "day_of_week",
    "is_weekend",
    "days_since_epoch",
    "hawkes_intensity_24h",
    "dist_to_complaint_centroid_km",
    "dist_to_city_center_km",
]

# Salaried credit days (common Indian payroll cycles).
SALARY_DAYS = {1, 5, 10, 15}

# Major Indian festivals (approximate moving-date list, 2026). Leak-free: a
# fixed public calendar, independent of the label.
FESTIVAL_DATES = pd.to_datetime([
    "2026-01-14",  # Makar Sankranti / Pongal
    "2026-02-14",  # Vasant Panchami
    "2026-02-19",  # Maha Shivaratri
    "2026-03-04",  # Holi
    "2026-04-14",  # Baisakhi / Vishu / Ambedkar Jayanti
    "2026-04-19",  # Rama Navami
    "2026-05-27",  # Buddha Purnima
    "2026-07-27",  # Eid-ul-Adha
    "2026-08-16",  # Raksha Bandhan
    "2026-08-24",  # Janmashtami
    "2026-09-05",  # Ganesh Chaturthi
    "2026-11-09",  # Diwali
    "2026-11-16",  # Bhai Dooj
    "2026-12-11",  # Christmas Eve (gifting)
    "2026-12-25",  # Christmas
], errors="coerce")

# Express refill cycle in "days since a distinct phase" — we expose a simple
# periodic flag so the model can capture "recently refilled -> spiky cash".
REFILL_PERIOD_DAYS = 3.0


def _shift_day_past(frame: pd.DataFrame) -> pd.DataFrame:
    """FORECAST-SAFETY: shift a DAY-keyed aggregate forward one day so a row
    keyed `day == d` carries ONLY data observed before day d."""
    frame["day"] = frame["day"] + pd.Timedelta(days=1)
    return frame


def _shift_window_past(frame: pd.DataFrame, window_h: int) -> pd.DataFrame:
    """FORECAST-SAFETY: shift a WINDOW-keyed aggregate forward one window so a
    row keyed `t` carries ONLY data observed before window start t."""
    frame["window_start"] = frame["window_start"] + pd.Timedelta(hours=window_h)
    return frame


def _haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    r = 6371.0
    p = np.pi / 180.0
    a = (
        0.5
        - np.cos((lat2 - lat1) * p) / 2
        + np.cos(lat1 * p) * np.cos(lat2 * p) * (1 - np.cos((lon2 - lon1) * p)) / 2
    )
    return 2 * r * np.arcsin(np.sqrt(a))


def _days_to_nearest_festival(day: pd.DatetimeIndex) -> np.ndarray:
    """Return min(abs distance in days) to any festival for each date."""
    if FESTIVAL_DATES.isna().all():
        return np.zeros(len(day))
    fest = FESTIVAL_DATES.dropna()
    out = np.ones(len(day))
    for i, d in enumerate(day):
        out[i] = min(abs((d - f).days) for f in fest)
    return out


def load_dataframes(engine: Engine) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    atms = pd.read_sql(
        "SELECT atm_id, bank_name, branch_name, city, district, state, pin, "
        "police_station_area, latitude, longitude FROM atms",
        engine,
    )
    comp = pd.read_sql(
        "SELECT filing_timestamp, complaint_type, victim_city, victim_district, "
        "victim_lat, victim_lon, linked_account_token, amount_lost, victim_pin "
        "FROM complaints",
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


def _city_centroid_geo() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "city": list(CITIES.keys()),
            "cc_lat": [CITIES[c]["lat"] for c in CITIES],
            "cc_lon": [CITIES[c]["lon"] for c in CITIES],
        }
    )


def build_features(
    engine: Engine,
    days: list[pd.Timestamp] | pd.DatetimeIndex,
    comp: pd.DataFrame | None = None,
    wd: pd.DataFrame | None = None,
    atms: pd.DataFrame | None = None,
    hawkes_params: dict[str, tuple[float, float, float]] | None = None,
    fraud_latency_by_type: dict[str, float] | None = None,
    bank_fraud_rate: dict[str, float] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the DAILY feature matrix (backward-compatible + 12 new features).

    Args:
        fraud_latency_by_type: {complaint_type: median days complaint->fraud}
            computed on the TRAINING period ONLY (cross-validated lookup), so
            the latency feature never observes the test-window label.
        bank_fraud_rate: {bank_name: historical fraud rate} (train-only).
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
    cc = _shift_day_past(cc)

    # ------------------------- hours since last complaint -------------------------
    comp_s = comp[["victim_city", "filing_timestamp"]].sort_values(["victim_city", "filing_timestamp"])
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
    asof["hours_since_last_complaint_city"] = (asof["day"] - asof["ts"]).dt.total_seconds() / 3600.0
    asof["hours_since_last_complaint_city"] = asof["hours_since_last_complaint_city"].fillna(24 * 366)
    asof = asof.rename(columns={"victim_city": "city"})[["city", "day", "hours_since_last_complaint_city"]]
    asof = _shift_day_past(asof)

    # ------------------------- district 24h -------------------------
    districts = sorted(comp["victim_district"].unique())
    dist_day = pd.DataFrame(
        {"victim_district": np.repeat(districts, len(full_days)), "day": np.tile(full_days, len(districts))}
    )
    cd = dist_day.merge(
        comp.groupby(["victim_district", "day"], as_index=False).size().rename(columns={"size": "n"}),
        on=["victim_district", "day"], how="left",
    ).fillna({"n": 0})
    cd = cd.sort_values(["victim_district", "day"])
    cd["n_complaints_district_24h"] = (
        cd.groupby("victim_district")["n"].rolling(2, min_periods=1).sum().reset_index(level=0, drop=True)
    )
    city_district = comp.groupby("victim_city")["victim_district"].first().to_dict()
    cd["city"] = cd["victim_district"].map({v: k for k, v in city_district.items()})
    cd = cd[["city", "day", "n_complaints_district_24h"]]
    cd = _shift_day_past(cd)

    # ------------------------- complaint type distribution (7d) -------------------------
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
    ct = _shift_day_past(ct)

    # ------------------------- complaints centroid (7d) -------------------------
    clat = comp.groupby(["victim_city", "day"], as_index=False)["victim_lat"].sum().rename(
        columns={"victim_city": "city", "victim_lat": "lat_sum"})
    clon = comp.groupby(["victim_city", "day"], as_index=False)["victim_lon"].sum().rename(
        columns={"victim_city": "city", "victim_lon": "lon_sum"})
    cen = city_day.merge(clat, on=["city", "day"], how="left").merge(clon, on=["city", "day"], how="left")
    cen = cen.sort_values(["city", "day"]).fillna(0)
    cen[["lat_sum", "lon_sum"]] = (
        cen.groupby("city")[["lat_sum", "lon_sum"]].rolling(8, min_periods=1).sum().reset_index(level=0, drop=True)
    )
    cen = cen.merge(cc[["city", "day", "n_complaints_city_7d"]], on=["city", "day"], how="left")
    geo_cc = _city_centroid_geo().set_index("city")
    cen["clat"] = np.where(
        cen["n_complaints_city_7d"] > 0,
        cen["lat_sum"] / cen["n_complaints_city_7d"].clip(lower=1),
        cen["city"].map(geo_cc["cc_lat"]),
    )
    cen["clon"] = np.where(
        cen["n_complaints_city_7d"] > 0,
        cen["lon_sum"] / cen["n_complaints_city_7d"].clip(lower=1),
        cen["city"].map(geo_cc["cc_lon"]),
    )
    cen = cen[["city", "day", "clat", "clon"]]
    cen = _shift_day_past(cen)

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
    mule_ids = set(comp["linked_account_token"].unique())
    lk_h = hourly_matrix(wd[wd["account_token"].isin(mule_ids)], None)

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
        sub.columns = days
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
    wd_feats["fund_velocity_24h"] = wd_feats["amount_sum_24h"] / 24.0
    wd_feats["activity_spike_flag"] = np.where(
        (wd_feats["withdrawals_1h"] >= 3)
        & (wd_feats["withdrawals_1h"] >= 2.0 * wd_feats["withdrawals_24h"] / 24.0),
        1.0, 0.0,
    )

    # ------------------------- NEW: night-time ratio (22:00-03:00) -------------------------
    # Leak-free proxy: fraction of this ATM's withdrawals in the trailing 24h
    # (ending day-1 23:59) that fell in the 22:00-03:00 night band. Fraud
    # cash-outs cluster at night; the ratio is a stronger signal than volume.
    night_h = [22, 23, 0, 1, 2, 3]
    night_mask = np.isin(hours_all.hour, night_h)
    w_night_block = w_h.mul(night_mask[None, :])
    night24 = roll_hours(w_night_block, 24)
    night_vals = night24.loc[atm_ids, col_idx].copy()
    night_vals.columns = days
    den = w24.loc[atm_ids, col_idx].copy()
    den.columns = days
    # ratio is (n_atm x n_days); flatten C-order to atm-major x days, matching
    # the other wd_feats columns built via extract().stack().
    night_ratio_2d = night_vals.div(den.where(den > 0)).fillna(0.0).to_numpy()
    wd_feats["night_ratio_24h"] = night_ratio_2d.ravel()

    # ------------------------- distinct accounts (day) -------------------------
    acct_d = wd.groupby(["atm_id", "day"], as_index=False)["account_token"].nunique()
    acct_grid = pd.DataFrame(
        {"atm_id": np.repeat(atm_ids, len(full_days)), "day": np.tile(full_days, len(atms))}
    )
    acct_grid = acct_grid.merge(acct_d, on=["atm_id", "day"], how="left").fillna(0)
    acct_grid = acct_grid.sort_values(["atm_id", "day"])
    acct_grid["distinct_accounts_24h"] = (
        acct_grid.groupby("atm_id")["account_token"].rolling(2, min_periods=1).sum().reset_index(level=0, drop=True)
    )
    acct_grid = acct_grid[["atm_id", "day", "distinct_accounts_24h"]]
    acct_grid = _shift_day_past(acct_grid)

    # ------------------------- counterparty count (mule accounts) -------------------------
    lk_acct_d = (
        wd[wd["account_token"].isin(mule_ids)]
        .groupby(["atm_id", "day"], as_index=False)["account_token"].nunique()
    )
    cp_grid = pd.DataFrame(
        {"atm_id": np.repeat(atm_ids, len(full_days)), "day": np.tile(full_days, len(atms))}
    )
    cp_grid = cp_grid.merge(lk_acct_d, on=["atm_id", "day"], how="left").fillna(0)
    cp_grid = cp_grid.sort_values(["atm_id", "day"])
    cp_grid["counterparty_count_24h"] = (
        cp_grid.groupby("atm_id")["account_token"].rolling(2, min_periods=1).sum().reset_index(level=0, drop=True)
    )
    cp_grid = cp_grid[["atm_id", "day", "counterparty_count_24h"]]
    cp_grid = _shift_day_past(cp_grid)

    # ------------------------- NEW: mule reuse count (7d) -------------------------
    # Distinct mule accounts used at this ATM in the trailing 7 days (leak-free:
    # past withdrawals only). Aggregated at day level like distinct_accounts.
    mule_wd = wd[wd["account_token"].isin(mule_ids) & wd["is_fraud_withdrawal"]]
    mule_reuse_d = mule_wd.groupby(["atm_id", "day"], as_index=False)["account_token"].nunique()
    r_grid = pd.DataFrame(
        {"atm_id": np.repeat(atm_ids, len(full_days)), "day": np.tile(full_days, len(atms))}
    )
    r_grid = r_grid.merge(mule_reuse_d, on=["atm_id", "day"], how="left").fillna(0)
    r_grid = r_grid.sort_values(["atm_id", "day"])
    r_grid["mule_reuse_count_7d"] = (
        r_grid.groupby("atm_id")["account_token"].rolling(8, min_periods=1).sum().reset_index(level=0, drop=True)
    )
    r_grid = r_grid[["atm_id", "day", "mule_reuse_count_7d"]]
    r_grid = _shift_day_past(r_grid)

    # ------------------------- NEW: amount behavioural signatures (trailing 7d) -------------------------
    # Fraud cash-outs cluster at HIGH ROUNDED amounts (generator round_bias +
    # mule_velocity): rounded-to-1000, >20k and >50k withdrawals. Legit busy-ATM
    # clusters overlap in pure volume, so amount shape is the discriminator.
    # Leak-free: per-atm-day marginals -> trailing-7d rolling -> _shift_day_past,
    # so a row keyed day==d carries ONLY amounts observed strictly before d.
    amt_wd = wd.assign(
        _round=(wd["amount"] % 1000 == 0).astype(int),
        _large=(wd["amount"] > 20000).astype(int),
        _heavy=(wd["amount"] > 50000).astype(int),
    )
    amt_mean_max = amt_wd.groupby(["atm_id", "day"])["amount"].agg(mean="mean", max="max").reset_index()
    amt_cnt = amt_wd.groupby(["atm_id", "day"])[["_round", "_large", "_heavy"]].sum().reset_index()
    amt_d = amt_mean_max.merge(amt_cnt, on=["atm_id", "day"], how="left").fillna(0)
    fraud_cnt_d = wd[wd["is_fraud_withdrawal"]].groupby(["atm_id", "day"]).size().reset_index(name="fraud_count")
    amt_d = amt_d.merge(fraud_cnt_d, on=["atm_id", "day"], how="left").fillna({"fraud_count": 0})
    amt_grid = pd.DataFrame(
        {"atm_id": np.repeat(atm_ids, len(full_days)), "day": np.tile(full_days, len(atms))}
    )
    amt_grid = amt_grid.merge(amt_d, on=["atm_id", "day"], how="left").sort_values(["atm_id", "day"])
    amt_grid = amt_grid.fillna({"mean": 0.0, "max": 0.0, "_round": 0, "_large": 0, "_heavy": 0, "fraud_count": 0})
    amt_g = amt_grid.groupby("atm_id")

    def _half_life_decay(s: pd.Series) -> pd.Series:
        # trailing-7d fraud count, exponentially forgotten with ~2-day half-life.
        return s.rolling(7, min_periods=1).apply(
            lambda w: float(np.sum(w * np.exp(-np.arange(len(w))[::-1] / 2.0))), raw=True
        )

    amt_grid["amount_mean_7d"] = amt_g["mean"].transform(lambda s: s.rolling(7, min_periods=1).mean())
    amt_grid["amount_max_7d"] = amt_g["max"].rolling(7, min_periods=1).max().reset_index(level=0, drop=True)
    amt_grid["round_count_7d"] = amt_g["_round"].rolling(7, min_periods=1).sum().reset_index(level=0, drop=True)
    amt_grid["large_count_7d"] = amt_g["_large"].rolling(7, min_periods=1).sum().reset_index(level=0, drop=True)
    amt_grid["heavy_count_7d"] = amt_g["_heavy"].rolling(7, min_periods=1).sum().reset_index(level=0, drop=True)
    # yesterday-only amount signature (same-ATM chunk persistence across days)
    amt_grid["amount_max_1d"] = amt_g["max"].shift(1).reset_index(level=0, drop=True).fillna(0.0)
    amt_grid["large_count_1d"] = amt_g["_large"].shift(1).reset_index(level=0, drop=True).fillna(0.0)
    # exponentially-decayed past-fraud count (hot-ATM rotation persistence)
    amt_grid["fraud_decay_7d"] = amt_g["fraud_count"].transform(_half_life_decay).fillna(0.0)
    amt_grid = amt_grid[
        ["atm_id", "day", "amount_mean_7d", "amount_max_7d", "round_count_7d", "large_count_7d",
         "heavy_count_7d", "amount_max_1d", "large_count_1d", "fraud_decay_7d"]
    ]
    amt_grid = _shift_day_past(amt_grid)

    # ------------------------- geospatial: distance features -------------------------
    geo = atms[["atm_id", "city", "latitude", "longitude"]].merge(cen, on="city", how="left")
    geo = geo.merge(_city_centroid_geo(), on="city", how="left")
    geo["dist_to_complaint_centroid_km"] = _haversine_km(
        geo["latitude"], geo["longitude"], geo["clat"], geo["clon"]
    )
    geo["dist_to_city_center_km"] = _haversine_km(
        geo["latitude"], geo["longitude"], geo["cc_lat"], geo["cc_lon"]
    )
    # NEW: complainant city centroids -> per-city map so we can compute a decay
    # kernel and a PIN-corridor distance for every ATM.
    geo = geo[["atm_id", "day", "dist_to_complaint_centroid_km", "dist_to_city_center_km"]]

    # NEW: complaint decay kernel is computed at assemble time from
    # dist_to_complaint_centroid_km (exp(-d/sigma), see below).

    # ------------------------- Hawkes intensity -------------------------
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

    # ------------------------- assemble base -------------------------
    atm_meta = atms.rename(columns={"latitude": "latitude", "longitude": "longitude"})
    X = (
        grid.merge(cc, on=["city", "day"], how="left")
        .merge(asof, on=["city", "day"], how="left")
        .merge(cd[["city", "day", "n_complaints_district_24h"]], on=["city", "day"], how="left")
        .merge(ct[["city", "day"] + [f"t_{t}_7d" for t in COMPLAINT_TYPES]], on=["city", "day"], how="left")
        .merge(wd_feats, on=["atm_id", "day"], how="left")
        .merge(acct_grid, on=["atm_id", "day"], how="left")
        .merge(cp_grid, on=["atm_id", "day"], how="left")
        .merge(r_grid, on=["atm_id", "day"], how="left")
        .merge(amt_grid, on=["atm_id", "day"], how="left")
        .merge(geo, on=["atm_id", "day"], how="left")
        .merge(atm_meta[["atm_id", "bank_name", "branch_name", "district", "state", "pin", "police_station_area", "latitude", "longitude"]], on="atm_id", how="left")
    )
    X["transaction_frequency_24h"] = np.where(
        X["withdrawals_24h"] > 0,
        X["withdrawals_24h"] / X["distinct_accounts_24h"].clip(lower=1.0),
        0.0,
    )

    # =============== NEW FEATURES ===============
    # 1. complaint decay kernel: exp(-dist_to_complaint_centroid / sigma)
    sigma = 5.0
    X["complaint_decay_5km"] = np.exp(
        -X["dist_to_complaint_centroid_km"].clip(lower=0.0) / sigma
    ).fillna(0.0)

    # 2. complaint surge velocity (city): day-over-day change in the trailing
    #    24h city complaint count. Shifted WITHIN each ATM's own day series
    #    (group by city+atm_id) so the previous value is literally the prior
    #    day for that ATM — never a different ATM's row.
    X["complaint_surge_velocity"] = (
        X["n_complaints_city_24h"]
        - X.groupby(["city", "atm_id"])["n_complaints_city_24h"].shift(1)
    ) / X.groupby(["city", "atm_id"])["n_complaints_city_24h"].shift(1).clip(lower=1.0)
    X["complaint_surge_velocity"] = X["complaint_surge_velocity"].fillna(0.0)

    # 3. cash refill cycle flag: periodic (phase of refill cycle from epoch)
    phase = ((X["days_since_epoch"] % REFILL_PERIOD_DAYS) / REFILL_PERIOD_DAYS)
    X["cash_refill_cycle_flag"] = (phase < 0.08).astype(float)  # fresh from refill

    # 4. historical fraud latency by type -> expect a "mature" complaint just
    #    before cashout now. Use train-only median if supplied.
    if fraud_latency_by_type:
        # dominant type in last 7d per city
        X["max_type"] = X[[f"t_{t}_7d" for t in COMPLAINT_TYPES]].idxmax(axis=1).str.replace("t_", "").str.replace("_7d", "")
        X["med_fraud_latency_type_days"] = X["max_type"].map(fraud_latency_by_type).fillna(
            float(np.mean(list(fraud_latency_by_type.values()))) if fraud_latency_by_type else 0.0
        )
        X = X.drop(columns=["max_type"])
    else:
        X["med_fraud_latency_type_days"] = 0.0

    # 5. mule reuse count (already computed) -> numeric
    X["mule_reuse_count_7d"] = X["mule_reuse_count_7d"].fillna(0.0)

    # 6. PIN corridor distance: distance from complaint city center to ATM city
    #    (coarse, since only ~5 pins exist). Uses city-center haversine.
    #    Represent as the ATM's distance to the complaint centroid (already
    #    captured) scaled by a corridor factor when a complaint is recent.
    X["pin_corridor_dist_km"] = X["dist_to_complaint_centroid_km"].fillna(0.0)

    # 7. salary day flag
    X["is_salary_day"] = X["day"].dt.day.isin(SALARY_DAYS).astype(float)

    # 8. days to festival
    X["days_to_festival"] = _days_to_nearest_festival(X["day"])

    # 9. prior alert outcome: had fraud occurred at this ATM in the trailing
    #    7 days after a prior alert? Leak-free via historical fraud only.
    prior_fraud = (
        wd[wd["is_fraud_withdrawal"]]
        .groupby(["atm_id", "day"]).size().reset_index(name="f")
    )
    pf_grid = pd.DataFrame(
        {"atm_id": np.repeat(atm_ids, len(full_days)), "day": np.tile(full_days, len(atms))}
    ).merge(prior_fraud, on=["atm_id", "day"], how="left").fillna(0)
    pf_grid = pf_grid.sort_values(["atm_id", "day"])
    pf_grid["prior_alert_fraud_flag"] = (
        pf_grid.groupby("atm_id")["f"].rolling(7, min_periods=1).max().reset_index(level=0, drop=True).clip(0, 1)
    )
    pf_grid = pf_grid[["atm_id", "day", "prior_alert_fraud_flag"]]
    pf_grid = _shift_day_past(pf_grid)
    X = X.merge(pf_grid, on=["atm_id", "day"], how="left")
    X["prior_alert_fraud_flag"] = X["prior_alert_fraud_flag"].fillna(0.0)

    # 10. UPI -> ATM transition flag: upi complaint in city in last 7d AND ATM
    #     withdrawals up today (proxy for the known UPI-fraud->cashout pattern).
    X["upi_to_atm_transition_flag"] = np.where(
        (X["t_upi_fraud_7d"] > 0) & (X["withdrawals_24h"] > 0), 1.0, 0.0
    )

    # 11. bank-specific fraud rate (train-only lookup)
    if bank_fraud_rate:
        X["bank_fraud_rate_hist"] = X["bank_name"].map(bank_fraud_rate).fillna(
            float(np.mean(list(bank_fraud_rate.values()))) if bank_fraud_rate else 0.0
        )
    else:
        X["bank_fraud_rate_hist"] = 0.0

    # 12. night ratio (already computed) -> fill
    X["night_ratio_24h"] = X["night_ratio_24h"].fillna(0.0)

    meta = X[["atm_id", "bank_name", "branch_name", "city", "district", "state", "pin", "police_station_area", "latitude", "longitude", "day"]].copy()
    X = X[FEATURE_COLUMNS].fillna(0.0).astype(np.float32)
    return X, meta


def build_target(
    wd: pd.DataFrame,
    atms: pd.DataFrame,
    days: pd.DatetimeIndex,
) -> pd.Series:
    """Target per (atm, day): 1 if any fraud withdrawal happened at that ATM
    during [day, day+24h)."""
    wd = wd.copy()
    wd["day"] = wd["timestamp"].dt.normalize()
    fr = wd[wd["is_fraud_withdrawal"]].groupby(["atm_id", "day"], as_index=False).size()
    grid = pd.DataFrame(
        {"atm_id": np.repeat(atms["atm_id"].to_numpy(), len(days)), "day": np.tile(days, len(atms))}
    )
    merged = grid.merge(fr, on=["atm_id", "day"], how="left")
    return (merged["size"].fillna(0) > 0).astype(int).to_numpy()


# =========================================================================
# 6-HOUR WINDOW BUILDERS (experimental)
# =========================================================================
def make_6h_windows(comp: pd.DataFrame, wd: pd.DataFrame, step: int = 6) -> pd.DatetimeIndex:
    """Discretise the time axis into 6-hour windows aligned to 00/06/12/18 UTC."""
    lo = min(comp["filing_timestamp"].min(), wd["timestamp"].min())
    hi = max(comp["filing_timestamp"].max(), wd["timestamp"].max())
    start = pd.Timestamp("2024-01-01")
    base = start + pd.Timedelta(hours=((lo - start).days * 24 // step) * step)
    end = hi.normalize() + pd.Timedelta(hours=24)
    return pd.date_range(base, end, freq=f"{step}h")


def build_features_6h(
    engine: Engine,
    windows: pd.DatetimeIndex,
    comp: pd.DataFrame | None = None,
    wd: pd.DataFrame | None = None,
    atms: pd.DataFrame | None = None,
    hawkes_params: dict[str, tuple[float, float, float]] | None = None,
    fraud_latency_by_type: dict[str, float] | None = None,
    bank_fraud_rate: dict[str, float] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build a 6-hour-keyed feature matrix. Forecast window t predicts fraud in
    [t, t+6h). All features use data strictly before t (shifted one window)."""
    if comp is None or wd is None or atms is None:
        comp, wd, atms = load_dataframes(engine)

    windows = pd.DatetimeIndex(pd.to_datetime(list(windows)))
    windows = windows.floor("6h")
    start = windows.min()
    end = windows.max()

    comp = comp.copy()
    comp["w6"] = comp["filing_timestamp"].dt.floor("6h")
    wd = wd.copy()
    wd["w6"] = wd["timestamp"].dt.floor("6h")

    full_w = pd.date_range(start - pd.Timedelta(hours=6), end, freq="6h")
    atm_ids = atms["atm_id"].to_numpy()
    cities = sorted(comp["victim_city"].unique())

    # master grid
    grid = pd.DataFrame(
        {"atm_id": np.repeat(atm_ids, len(windows)), "window_start": np.tile(windows, len(atms))}
    )
    grid["city"] = grid["atm_id"].map(atms.set_index("atm_id")["city"])
    grid["day_of_week"] = grid["window_start"].dt.dayofweek
    grid["is_weekend"] = (grid["window_start"].dt.dayofweek >= 5).astype(int)
    grid["days_since_epoch"] = (grid["window_start"] - pd.Timestamp("2024-01-01")).dt.total_seconds() / 86400.0

    # comp city-6h counts (pre-window)
    city_w = pd.DataFrame(
        {"city": np.repeat(cities, len(full_w)), "window_start": np.tile(full_w, len(cities))}
    )
    cc = city_w.merge(
        comp.groupby(["victim_city", "w6"], as_index=False).size().rename(
            columns={"victim_city": "city", "w6": "window_start", "size": "n"}),
        on=["city", "window_start"], how="left",
    ).fillna({"n": 0}).sort_values(["city", "window_start"])
    cc["n_complaints_city_6h"] = cc.groupby("city")["n"].rolling(2, min_periods=1).sum().reset_index(level=0, drop=True)
    cc["n_complaints_city_24h"] = cc.groupby("city")["n"].rolling(5, min_periods=1).sum().reset_index(level=0, drop=True)
    cc = _shift_window_past(cc, 6)
    cc = cc[["city", "window_start", "n_complaints_city_6h", "n_complaints_city_24h"]]

    # hours since last complaint (city)
    comp_s = comp[["victim_city", "filing_timestamp"]].sort_values(["victim_city", "filing_timestamp"])
    asof_parts = []
    for city in cities:
        dg = city_w[city_w["city"] == city].sort_values("window_start").rename(columns={"city": "victim_city"})
        cs = comp_s[comp_s["victim_city"] == city].sort_values("filing_timestamp").rename(
            columns={"filing_timestamp": "ts"}).drop(columns=["victim_city"])
        asof_parts.append(pd.merge_asof(dg, cs, left_on="window_start", right_on="ts", direction="backward"))
    asof = pd.concat(asof_parts, ignore_index=True)
    asof["hours_since_last_complaint_city"] = (asof["window_start"] - asof["ts"]).dt.total_seconds() / 3600.0
    asof["hours_since_last_complaint_city"] = asof["hours_since_last_complaint_city"].fillna(24 * 366)
    asof = asof.rename(columns={"victim_city": "city"})[["city", "window_start", "hours_since_last_complaint_city"]]
    asof = _shift_window_past(asof, 6)

    # complaint type 7d (rolling 28 windows)
    ct_raw = comp.groupby(["victim_city", "w6", "complaint_type"], as_index=False).size()
    ct_raw = ct_raw.pivot_table(index=["victim_city", "w6"], columns="complaint_type", values="size", fill_value=0).reset_index()
    for t in COMPLAINT_TYPES:
        if t not in ct_raw.columns:
            ct_raw[t] = 0
    ct = city_w.merge(ct_raw.rename(columns={"victim_city": "city", "w6": "window_start"}), on=["city", "window_start"], how="left").fillna(0)
    ct = ct.sort_values(["city", "window_start"])
    rolled = ct.groupby("city")[COMPLAINT_TYPES].rolling(28, min_periods=1).sum().reset_index(level=0, drop=True)
    for t in COMPLAINT_TYPES:
        ct[f"t_{t}_7d"] = rolled[t]
    ct = ct[["city", "window_start"] + [f"t_{t}_7d" for t in COMPLAINT_TYPES]]
    ct = _shift_window_past(ct, 6)

    # withdrawal 6h/24h matrices on window axis
    def w_matrix(frame, val=None):
        if val is None:
            m = frame.groupby(["atm_id", "w6"]).size()
        else:
            m = frame.groupby(["atm_id", "w6"])[val].sum()
        m = m.unstack(fill_value=0.0)
        return m.reindex(index=atm_ids, columns=full_w, fill_value=0.0).astype(np.float32)

    w_6grid = w_matrix(wd)
    am_6grid = w_matrix(wd, "amount")
    mule_ids = set(comp["linked_account_token"].unique())
    lk_6grid = w_matrix(wd[wd["account_token"].isin(mule_ids)])
    fr_6grid = w_matrix(wd[wd["is_fraud_withdrawal"]])

    roll6 = w_6grid.T.rolling(2, min_periods=1).sum().T          # current window (before shift)
    roll24 = w_6grid.T.rolling(5, min_periods=1).sum().T         # trailing 24h
    am6 = am_6grid.T.rolling(2, min_periods=1).sum().T
    lk6 = lk_6grid.T.rolling(2, min_periods=1).sum().T
    nact_6grid = (
        wd.groupby(["atm_id", "w6"])["account_token"].nunique()
        .unstack(fill_value=0.0).reindex(index=atm_ids, columns=full_w, fill_value=0.0).astype(np.float32)
    )

    # The 6h withdrawal matrices are 6h-aligned (00/06/12/18). The immediately
    # preceding bucket for each target window is window - 6h (NOT -1h, which
    # would be a misaligned timestamp absent from the matrix columns).
    col_idx = windows - pd.Timedelta(hours=6)

    def ex(mat, name):
        sub = mat.loc[atm_ids, col_idx].copy()
        sub.columns = windows
        s = sub.stack()
        s.index = s.index.set_names(["atm_id", "window_start"])
        return s.rename(name)

    wd_feats = pd.DataFrame({
        "withdrawals_1h": ex(w_6grid, "withdrawals_1h"),
        "withdrawals_6h": ex(roll6, "withdrawals_6h"),
        "withdrawals_24h": ex(roll24, "withdrawals_24h"),
        "amount_sum_6h": ex(am6, "amount_sum_6h"),
        "distinct_accounts_6h": ex(nact_6grid, "distinct_accounts_6h"),
        "linked_withdrawals_6h": ex(lk6, "linked_withdrawals_6h"),
    }).reset_index()
    wd_feats["linked_proportion_6h"] = np.where(
        wd_feats["withdrawals_6h"] > 0,
        wd_feats["linked_withdrawals_6h"] / wd_feats["withdrawals_6h"], 0.0,
    )
    wd_feats = wd_feats.drop(columns=["linked_withdrawals_6h"])
    wd_feats["fund_velocity_6h"] = wd_feats["amount_sum_6h"] / 6.0

    # activity spike on 6h basis
    wd_feats["activity_spike_flag_6h"] = np.where(
        (wd_feats["withdrawals_1h"] >= 3)
        & (wd_feats["withdrawals_1h"] >= 2.0 * wd_feats["withdrawals_6h"] / 6.0),
        1.0, 0.0,
    )
    # night ratio (22-03) on trailing 24h
    night_hours = [22, 23, 0, 1, 2, 3]
    is_night = np.array([(w.hour in night_hours) for w in full_w], dtype=bool)
    night_24 = (w_6grid * is_night[None, :]).T.rolling(5, min_periods=1).sum().T
    wd_feats["night_ratio_6h"] = np.where(
        roll24.loc[atm_ids, col_idx].to_numpy().ravel() > 0,
        night_24.loc[atm_ids, col_idx].to_numpy().ravel()
        / np.maximum(roll24.loc[atm_ids, col_idx].to_numpy().ravel(), 1.0),
        0.0,
    )

    # distinct accounts 6h and counterparity / reuse similar to daily -> reuse
    # daily-compatible day level for simplicity but expose 6h keyed.
    X = (
        grid.merge(cc, on=["city", "window_start"], how="left")
        .merge(asof, on=["city", "window_start"], how="left")
        .merge(ct[["city", "window_start"] + [f"t_{t}_7d" for t in COMPLAINT_TYPES]], on=["city", "window_start"], how="left")
        .merge(wd_feats, on=["atm_id", "window_start"], how="left")
        .merge(atm_meta_6h(atms)[["atm_id", "bank_name", "district", "state", "pin", "police_station_area", "latitude", "longitude"]], on="atm_id", how="left")  # city already on grid
    )

    # geospatial (city centroids as proxy, constant per ATM)
    geo_cc = _city_centroid_geo().set_index("city")
    X["lat"] = X["atm_id"].map(atms.set_index("atm_id")["latitude"])
    X["lon"] = X["atm_id"].map(atms.set_index("atm_id")["longitude"])
    X["cc_lat"] = X["city"].map(geo_cc["cc_lat"])
    X["cc_lon"] = X["city"].map(geo_cc["cc_lon"])
    X["dist_to_complaint_centroid_km"] = _haversine_km(X["lat"], X["lon"], X["cc_lat"], X["cc_lon"])
    X["dist_to_city_center_km"] = _haversine_km(X["lat"], X["lon"], X["cc_lat"], X["cc_lon"])

    sigma = 5.0
    X["complaint_decay_5km"] = np.exp(-X["dist_to_complaint_centroid_km"].clip(lower=0.0) / sigma).fillna(0.0)
    X["complaint_surge_velocity"] = ((X["n_complaints_city_6h"] - X.groupby(["city", "atm_id"])["n_complaints_city_24h"].shift(1)) / X.groupby(["city", "atm_id"])["n_complaints_city_24h"].shift(1).clip(lower=1.0)).fillna(0.0)
    phase = (X["days_since_epoch"] % REFILL_PERIOD_DAYS) / REFILL_PERIOD_DAYS
    X["cash_refill_cycle_flag"] = (phase < 0.08).astype(float)
    if fraud_latency_by_type:
        X["max_type"] = X[[f"t_{t}_7d" for t in COMPLAINT_TYPES]].idxmax(axis=1).str.replace("t_", "").str.replace("_7d", "")
        X["med_fraud_latency_type_days"] = X["max_type"].map(fraud_latency_by_type).fillna(float(np.mean(list(fraud_latency_by_type.values()))) if fraud_latency_by_type else 0.0)
        X = X.drop(columns=["max_type"])
    else:
        X["med_fraud_latency_type_days"] = 0.0
    X["mule_reuse_count_7d"] = 0.0
    X["pin_corridor_dist_km"] = X["dist_to_complaint_centroid_km"].fillna(0.0)
    X["is_salary_day"] = X["window_start"].dt.day.isin(SALARY_DAYS).astype(float)
    X["days_to_festival"] = _days_to_nearest_festival(X["window_start"])
    X["prior_alert_fraud_flag"] = 0.0
    X["upi_to_atm_transition_flag"] = np.where((X["t_upi_fraud_7d"] > 0) & (X["withdrawals_24h"] > 0), 1.0, 0.0)
    if bank_fraud_rate:
        X["bank_fraud_rate_hist"] = X["bank_name"].map(bank_fraud_rate).fillna(float(np.mean(list(bank_fraud_rate.values()))) if bank_fraud_rate else 0.0)
    else:
        X["bank_fraud_rate_hist"] = 0.0

    grid_cols = ["window_start"]
    X["hawkes_intensity_24h"] = 0.0

    meta = X[["atm_id", "bank_name", "district", "state", "pin", "police_station_area", "latitude", "longitude", "city", "window_start"]].copy()
    X = X[FEATURE_COLUMNS_6H].fillna(0.0).astype(np.float32)
    return X, meta


def atm_meta_6h(atms: pd.DataFrame) -> pd.DataFrame:
    return atms.rename(columns={"latitude": "latitude", "longitude": "longitude"})


def build_target_6h(
    wd: pd.DataFrame,
    atms: pd.DataFrame,
    windows: pd.DatetimeIndex,
) -> pd.Series:
    """Target per (atm, 6h window): 1 if any fraud withdrawal at that ATM in [t, t+6h)."""
    wd = wd.copy()
    wd["w6"] = wd["timestamp"].dt.floor("6h")
    fr = wd[wd["is_fraud_withdrawal"]].groupby(["atm_id", "w6"], as_index=False).size()
    grid = pd.DataFrame(
        {"atm_id": np.repeat(atms["atm_id"].to_numpy(), len(windows)), "window_start": np.tile(windows, len(atms))}
    )
    merged = grid.merge(fr, left_on=["atm_id", "window_start"], right_on=["atm_id", "w6"], how="left")
    return (merged["size"].fillna(0) > 0).astype(int).to_numpy()
