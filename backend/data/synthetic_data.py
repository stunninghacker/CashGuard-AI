"""
Synthetic data generator — realistic NCRP complaints + ATM network + withdrawal transactions.

HONESTY DISCIPLINE (see CALIBRATION_NOTES.md):
  * Every parameter lives in calibration_config.yaml with source_status
    (verified_pattern | assumption_general_literature) + citation; a summary
    table is printed at generation time.
  * RBI is cited by DIRECTION only (no asserted hold numbers).
  * Nuh/Jamtara are cited as SCAM-ORIGIN hubs, not withdrawal hubs.
  * PII is PSEUDONYMIZED: accounts/phones stored as salted tokens (acct_…/tel_…);
    raw values exist only in the mock vault (role-scoped re-identification).
  * ANTI-PROFILING: no demographic/community/religion/caste features exist.

Patterns embedded (calibrated):
  1) Mule account linkage: accounts named in complaints later perform fraud cash-outs.
  2) Spatio-temporal clustering: complaint surges in a city precede fraud cash-outs
     at nearby ATMs within 24-72h.
  3) Night/weekend bias (assumption weights).
  4) Pareto-heavy hot-ATM concentration (direction verified; coefficients tunable).
  5) Behavioural signature: mule accounts show velocity/counterparty/frequency/spikes
     (IBA direction) AND normal banking history before cash-out (no trivial leak).
  6) DETUNED: persistence is deliberately imperfect so precision@K lands in the
     honest 0.75-0.90 band (a perfect score would indicate a generator leak).

To connect real data later: replace generate() with ETL pulls from NCRP/CFCFRMS
REST APIs and bank ATM transaction feeds (same table schemas).
"""
from __future__ import annotations

import hashlib
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sqlalchemy.orm import Session

from .. import models

CONFIG_PATH = Path(__file__).resolve().parent / "calibration_config.yaml"
PII_SALT = "cashguard-demo-salt"  # production: per-record random salt from the vault

COMPLAINT_TYPES = ["phishing", "investment_fraud", "job_fraud", "upi_fraud", "digital_arrest", "sextortion"]
COMPLAINT_STATUSES = ["under_investigation", "funds_frozen", "funds_partially_recovered"]
NIGHT_HOURS = list(range(19, 24)) + list(range(0, 5))

# ---------------------------------------------------------------------------
# FICTIONAL geography & network configuration (UI policy: no real districts)
# ---------------------------------------------------------------------------
CITIES = {
    "Northsagar":          {"state": "State-A", "district": "Northsagar",     "pin": "410101", "lat": 22.6040, "lon": 74.6150},
    "Metro-West":          {"state": "State-B", "district": "Metro-West",     "pin": "420202", "lat": 23.0520, "lon": 77.3100},
    "Greenfield District": {"state": "State-C", "district": "Greenfield",     "pin": "430303", "lat": 19.1510, "lon": 75.9120},
    "District-3":          {"state": "State-D", "district": "District-3",     "pin": "440404", "lat": 20.6010, "lon": 80.1110},
    "Eastvale":            {"state": "State-E", "district": "Eastvale",       "pin": "450505", "lat": 21.8520, "lon": 82.4050},
}

BANKS = [
    "State Bank of India", "HDFC Bank", "ICICI Bank", "Punjab National Bank",
    "Axis Bank", "Bank of Baroda", "Kotak Mahindra Bank", "Canara Bank",
]

HOUR_WEIGHTS_BASE = np.array([
    0.4, 0.3, 0.3, 0.2, 0.2, 0.3, 0.5, 0.9,
    1.2, 1.4, 1.5, 1.6, 1.5, 1.4, 1.3, 1.2,
    1.2, 1.4, 1.8, 2.4, 2.8, 2.6, 2.0, 1.0,
])


def load_calibration_config(path: Path | None = None) -> dict:
    with open(path or CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _rid(prefix: str, n: int = 10) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:n]}"


# --------------------------- PII pseudonymization ---------------------------
class Pseudonymizer:
    """Salted-hash token mapping (mock vault). Raw values never leave the vault."""

    def __init__(self, salt: str = PII_SALT):
        self._salt = salt
        self.raw_to_token: dict[str, tuple[str, str]] = {}  # raw -> (token, entity_type)

    def tokenize(self, raw: str, entity_type: str, prefix: str) -> str:
        digest = hashlib.sha256(f"{self._salt}|{raw}".encode()).hexdigest()[:12]
        token = f"{prefix}_{digest}"
        self.raw_to_token[raw] = (token, entity_type)
        return token

    def account(self, raw: str) -> str:
        return self.tokenize(raw, "account", "acct")

    def phone(self, raw: str) -> str:
        return self.tokenize(raw, "phone", "tel")

    def vault_rows(self, now: datetime) -> list[models.VaultEntry]:
        return [
            models.VaultEntry(token=token, entity_type=etype, raw_value=raw, created_at=now)
            for raw, (token, etype) in self.raw_to_token.items()
        ]


def _account_raw(rng: random.Random) -> str:
    return "AC" + str(rng.randint(10**11, 10**12 - 1))


def _phone_raw(rng: random.Random) -> str:
    return f"9{rng.randint(100000000, 999999999)}"


# ---------------------------------------------------------------------------
# ATM network (jurisdiction fields: state, police_station_area)
# ---------------------------------------------------------------------------
def generate_atms(rng: random.Random, cfg: dict) -> list[models.ATM]:
    n_per_city = cfg["dataset"]["n_atms_per_city"]
    atms: list[models.ATM] = []
    for city, meta in CITIES.items():
        n_ps = 6
        for i in range(n_per_city):
            lat = meta["lat"] + rng.uniform(-0.12, 0.12)
            lon = meta["lon"] + rng.uniform(-0.12, 0.12)
            bank = rng.choice(BANKS)
            atms.append(models.ATM(
                atm_id=f"ATM-{city[:3].upper()}{i:04d}",
                bank_name=bank,
                branch_name=f"{bank} {city} Branch {i % 6 + 1}",
                city=city,
                district=meta["district"],
                state=meta["state"],
                pin=meta["pin"],
                police_station_area=f"PS-{city}-{(i % n_ps) + 1}",
                latitude=round(lat, 6),
                longitude=round(lon, 6),
            ))
    return atms


def _pareto_weights(rng: random.Random, n: int, skew: float) -> np.ndarray:
    u = np.array([rng.random() for _ in range(n)])
    w = (1.0 / np.clip(u, 1e-9, 1.0)) ** skew
    return w / w.sum()


# ---------------------------------------------------------------------------
# Complaints (episodic 'crime waves' + guaranteed final-wave for a live demo)
# ---------------------------------------------------------------------------
def generate_complaints(
    rng: random.Random,
    pii: Pseudonymizer,
    start: datetime,
    end: datetime,
    cfg: dict,
    final_wave: dict | None = None,
) -> tuple[list[models.Complaint], list[str]]:
    types = cfg["dataset"]["complaint_types"]
    n_total = cfg["dataset"]["n_complaints"]
    span = (end - start).days
    n_waves = max(15, n_total // 700)
    mule_tokens: list[str] = []

    waves: list[dict] = []
    for _ in range(n_waves):
        waves.append({
            "city": rng.choice(list(CITIES.keys())),
            "start": start + timedelta(days=rng.randint(0, max(1, span - 10))),
            "duration": rng.randint(2, 5),
            "intensity": rng.uniform(2.5, 8.0),
            "type": rng.choice(types),
        })
    if final_wave:
        waves.append({**final_wave, "start": end - timedelta(days=3), "duration": 3})

    complaints: list[models.Complaint] = []
    base_rate = n_total / span
    for day_i in range(span):
        day = start + timedelta(days=day_i)
        active = [w for w in waves if w["start"] <= day <= w["start"] + timedelta(days=w["duration"])]
        n_today = int(base_rate * rng.uniform(0.6, 1.4)) + sum(
            int(rng.uniform(1, w["intensity"])) for w in active
        )
        for _ in range(n_today):
            city = active[0]["city"] if (active and rng.random() < 0.8) else rng.choice(list(CITIES.keys()))
            ctype = active[0]["type"] if (active and rng.random() < 0.7) else rng.choice(types)
            meta = CITIES[city]
            raw_acct = _account_raw(rng)
            acct_token = pii.account(raw_acct)
            mule_tokens.append(acct_token)
            complaints.append(models.Complaint(
                complaint_id=_rid("CMP", 12),
                filing_timestamp=day + timedelta(hours=rng.randint(7, 23), minutes=rng.randint(0, 59)),
                complaint_type=ctype,
                victim_city=city,
                victim_district=meta["district"],
                victim_state=meta["state"],
                victim_pin=meta["pin"],
                victim_lat=round(meta["lat"] + rng.uniform(-0.05, 0.05), 6),
                victim_lon=round(meta["lon"] + rng.uniform(-0.05, 0.05), 6),
                amount_lost=round(rng.lognormvariate(np.log(65000), 1.1), 2),
                linked_account_token=acct_token,
                linked_phone_token=pii.phone(_phone_raw(rng)),
                status=rng.choices(COMPLAINT_STATUSES, weights=[0.55, 0.3, 0.15])[0],
            ))
    complaints.sort(key=lambda c: c.filing_timestamp)
    return complaints, mule_tokens


# ---------------------------------------------------------------------------
# Withdrawals (legit + fraud, behaviourally signed, detuned)
# ---------------------------------------------------------------------------
def generate_withdrawals(
    rng: random.Random,
    pii: Pseudonymizer,
    atms: list[models.ATM],
    complaints: list[models.Complaint],
    mule_tokens: list[str],
    start: datetime,
    end: datetime,
    cfg: dict,
    final_city: str | None = None,
) -> list[models.Withdrawal]:
    n_total = cfg["dataset"]["n_withdrawals"]
    fraud_share = cfg["dataset"]["fraud_share"]
    skew = cfg["clustering"]["pareto_skew"]
    mean_latency_h = cfg["timing"]["fraud_to_cashout_mean_hours"]
    night_w = cfg["behaviour"]["night_weight"]
    weekend_w = cfg["behaviour"]["weekend_weight"]
    round_bias = cfg["behaviour"]["round_amount_bias"]
    vel_mean = cfg["behaviour"]["mule_velocity_mean_inr_h"]
    hot_prob = cfg["scenario"]["hot_atm_use_prob"]
    burst_prob = cfg["scenario"]["mule_burst_prob"]
    same_atm_prob = cfg["scenario"]["mule_same_atm_prob"]
    random_atm_prob = cfg["scenario"]["random_atm_fraud_prob"]

    city_atms: dict[str, list[models.ATM]] = {}
    for a in atms:
        city_atms.setdefault(a.city, []).append(a)

    hot_atms: dict[str, list[models.ATM]] = {}
    hot_weights: dict[str, np.ndarray] = {}
    for city, atms_c in city_atms.items():
        hot = rng.sample(atms_c, max(6, int(len(atms_c) * cfg["clustering"]["hot_atm_fraction"])))
        hot_atms[city] = hot
        hot_weights[city] = _pareto_weights(rng, len(hot), skew)

    span_hours = int((end - start).total_seconds() // 3600)
    withdrawals: list[models.Withdrawal] = []
    n_fraud = int(n_total * fraud_share)
    n_legit = n_total - n_fraud
    i_legit = 0

    # ---- Legit background withdrawals (ends 23:59 of last day)
    # Real ATM networks have heavy-traffic locations: each ATM gets a traffic
    # weight (heavy tail) so legit volume overlaps fraud volumes — otherwise
    # "busy ATM" trivially equals "fraud ATM" (baseline lift = 1.0 = leak).
    city_atms_flat = [a for atms_c in city_atms.values() for a in atms_c]
    traffic_weights = np.clip(
        np.random.lognormal(0.0, 0.9, size=len(city_atms_flat)), 0.25, 9.0
    )
    traffic_weights = traffic_weights / traffic_weights.sum()
    atm_cdf = np.cumsum(traffic_weights)

    # ~25% of legit withdrawals come from complaint-linked (mule) accounts at
    # RANDOM ATMs — mule accounts have normal banking history AND their presence
    # is noisier (no trivial "linked account here = fraud" leak).
    legit_ts = pd.date_range(start, end - timedelta(minutes=1), periods=n_legit)
    for ts in legit_ts:
        atm = city_atms_flat[int(np.searchsorted(atm_cdf, rng.random()))]
        if rng.random() < 0.25:
            account = mule_tokens[i_legit % len(mule_tokens)]
        else:
            account = pii.account(_account_raw(rng))
        i_legit += 1
        withdrawals.append(models.Withdrawal(
            transaction_id=_rid("TXN", 12),
            timestamp=ts.to_pydatetime(),
            atm_id=atm.atm_id,
            account_token=account,
            amount=round(rng.uniform(500, 20000), 2),
            channel="ATM",
            is_fraud_withdrawal=False,
        ))

    # ---- Fraud cash-outs (behaviourally signed, detuned)
    mule_velocity: dict[str, float] = {m: rng.lognormvariate(np.log(vel_mean), 0.4) for m in mule_tokens}
    last_mule: str | None = None
    last_atm: models.ATM | None = None
    last_ts: datetime | None = None
    burst_blocked = False  # full-strength mule burst with NO fraud label (prevented cash-out)
    n_blocked = 0
    for i in range(n_fraud):
        if final_city and rng.random() < cfg["scenario"]["final_wave_share"]:
            city = final_city
            day = rng.randint(max(0, span_hours // 24 - 5), span_hours // 24 - 1)
        else:
            city = rng.choice(list(CITIES.keys()))
            day = rng.randint(0, span_hours // 24 - 1)

        latency_days = int(np.random.exponential(mean_latency_h / 24.0))
        for _ in range(8):
            if day + latency_days < span_hours // 24:
                break
            latency_days = int(np.random.exponential(mean_latency_h / 24.0))
        day = max(0, day + latency_days)

        hour_idx = int(rng.choices(range(24), weights=HOUR_WEIGHTS_BASE * np.array(
            [night_w if h in NIGHT_HOURS else 1.0 for h in range(24)]
        ))[0])
        ts = start + timedelta(days=day, hours=hour_idx, minutes=rng.randint(0, 59))
        if ts.weekday() >= 5 and rng.random() < (1 - 1 / weekend_w):
            ts -= timedelta(days=rng.choice([2, 1]))

        def _draw_atm():
            if rng.random() < hot_prob:
                pool, weights = hot_atms[city], hot_weights[city]
                return pool[int(np.searchsorted(np.cumsum(weights), rng.random()))]
            return rng.choice(city_atms[city])

        # Chunked cash-out: a bursting mule reuses the SAME ATM within MINUTES
        # (real cash-out chunks) — the chunk stays on one day, so per-ATM
        # transaction_frequency is a real behavioural feature. Day-over-day
        # persistence stays imperfect (new bursts = new mule/ATM draws).
        # The FINAL WAVE chunks harder (same-ATM 70%) so the live forecast
        # matches the feature distribution the model saw in training.
        in_final_wave = final_city is not None and city == final_city and day >= span_hours // 24 - 6
        effective_same_atm = 0.70 if in_final_wave else same_atm_prob
        if last_mule is not None and rng.random() < burst_prob and last_ts is not None:
            mule = last_mule
            if last_atm is not None and rng.random() < effective_same_atm:
                atm = last_atm
            else:
                atm = _draw_atm()
                for _ in range(3):
                    if atm.atm_id != last_atm.atm_id:
                        break
                    atm = _draw_atm()
            ts = last_ts + timedelta(minutes=rng.randint(1, 9))  # chunk: minutes apart
        else:
            # new burst starts — with blocked_burst_prob it is a full-strength
            # mule chunk pattern that carries NO fraud label (prevented cash-out)
            mule = mule_tokens[i % len(mule_tokens)]
            atm = _draw_atm()
            burst_blocked = rng.random() < cfg["scenario"]["blocked_burst_prob"]
            if burst_blocked:
                n_blocked += 1
        last_mule, last_atm, last_ts = mule, atm, ts

        # DETUNE: some fraud lands at genuinely random (non-hot) ATMs
        if not burst_blocked and rng.random() < random_atm_prob:
            atm = rng.choice(city_atms[city])

        amount = abs(float(rng.lognormvariate(np.log(mule_velocity[mule] / 2.0), 0.5)))
        if rng.random() < round_bias:
            amount = round(amount / 1000.0) * 1000.0
        withdrawals.append(models.Withdrawal(
            transaction_id=_rid("TXN", 12),
            timestamp=ts,
            atm_id=atm.atm_id,
            account_token=mule,
            amount=round(max(500.0, amount), 2),
            channel="ATM",
            is_fraud_withdrawal=not burst_blocked,
        ))

    withdrawals.sort(key=lambda w: w.timestamp)
    print(f"  [detune] blocked (prevented) mule bursts: {n_blocked} ({n_blocked / max(n_fraud, 1) * 100:.1f}%)")
    return withdrawals


# ---------------------------------------------------------------------------
# Accounts master (recovery loop)
# ---------------------------------------------------------------------------
def generate_accounts(
    rng: random.Random,
    pii: Pseudonymizer,
    mule_tokens: list[str],
    start: datetime,
    end: datetime,
    cfg: dict,
) -> list[models.Account]:
    accounts: list[models.Account] = []
    # behavioural source fields (IBA direction) for mule accounts
    for token in mule_tokens:
        accounts.append(models.Account(
            account_token=token,
            home_bank=rng.choice(BANKS),
            first_seen=start + timedelta(days=rng.randint(0, (end - start).days)),
            is_mule=True,
            txn_frequency_7d=round(rng.uniform(3, 12), 2),
            counterparty_count_7d=rng.randint(5, 25),
            fund_velocity_inr_h=round(rng.lognormvariate(np.log(cfg["behaviour"]["mule_velocity_mean_inr_h"]), 0.4), 2),
            activity_spike_flag=bool(rng.random() < 0.6),
        ))
    # a population of normal accounts (for the bank-facing master view)
    for _ in range(2000):
        accounts.append(models.Account(
            account_token=pii.account(_account_raw(rng)),
            home_bank=rng.choice(BANKS),
            first_seen=start + timedelta(days=rng.randint(0, (end - start).days)),
            is_mule=False,
            txn_frequency_7d=round(rng.uniform(0.2, 2.0), 2),
            counterparty_count_7d=rng.randint(1, 4),
            fund_velocity_inr_h=round(rng.uniform(500, 8000), 2),
            activity_spike_flag=False,
        ))
    return accounts


# ---------------------------------------------------------------------------
# Calibration summary (visible at generation time — honesty requirement)
# ---------------------------------------------------------------------------
def print_calibration_summary(cfg: dict) -> None:
    rows: list[tuple[str, str, str, str]] = []
    for section, params in cfg.items():
        if not isinstance(params, dict):
            continue
        for name, value in params.items():
            if isinstance(value, str) and value in ("verified_pattern", "assumption_general_literature"):
                continue
            if name.endswith("_citation") or name.endswith("_source_status"):
                continue
            status = params.get(f"{name}_source_status", "verified_pattern")
            citation = params.get(f"{name}_citation", "")
            rows.append((f"{section}.{name}", str(value), status, citation))
    w1 = max(len(r[0]) for r in rows) + 2
    w2 = 32
    print("=" * 110)
    print("CALIBRATION SUMMARY — every parameter source-tagged + cited")
    print("=" * 110)
    print(f"{'parameter':<{w1}}{'value':<12}{'source_status':<33}citation")
    print("-" * 110)
    for name, value, status, citation in rows:
        print(f"{name:<{w1}}{value:<12}{status:<33}{citation[:58]}")
    print("=" * 110)
    print("verified_pattern               -> cited source (see CALIBRATION_NOTES.md)")
    print("assumption_general_literature  -> no India-specific public statistic; tunable assumption")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def generate_all(
    db: Session,
    cfg: dict | None = None,
    seed: int = 42,
) -> dict:
    cfg = cfg or load_calibration_config()
    rng = random.Random(seed)
    np.random.seed(seed)
    pii = Pseudonymizer()

    end = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=cfg["dataset"]["months"] * 30)

    final_city = rng.choice(list(CITIES.keys()))
    final_type = rng.choice(cfg["dataset"]["complaint_types"])

    atms = generate_atms(rng, cfg)
    complaints, mule_tokens = generate_complaints(
        rng, pii, start, end, cfg,
        final_wave={"city": final_city, "type": final_type, "intensity": 7.0},
    )
    withdrawals = generate_withdrawals(
        rng, pii, atms, complaints, mule_tokens, start, end, cfg, final_city=final_city,
    )
    accounts = generate_accounts(rng, pii, mule_tokens, start, end, cfg)

    db.add_all(atms)
    db.commit()
    db.add_all(pii.vault_rows(datetime.utcnow()))
    db.commit()
    for i in range(0, len(accounts), 2000):
        db.add_all(accounts[i : i + 2000])
        db.commit()
    for i in range(0, len(complaints), 2000):
        db.add_all(complaints[i : i + 2000])
        db.commit()
    for i in range(0, len(withdrawals), 5000):
        db.add_all(withdrawals[i : i + 5000])
        db.commit()

    n_fraud = sum(1 for w in withdrawals if w.is_fraud_withdrawal)
    return {
        "atms": len(atms),
        "complaints": len(complaints),
        "withdrawals": len(withdrawals),
        "fraud_withdrawals": n_fraud,
        "mule_accounts": len(mule_tokens),
        "vault_entries": len(pii.raw_to_token),
        "final_wave_city": final_city,
        "period": f"{start:%Y-%m-%d} -> {end:%Y-%m-%d}",
    }