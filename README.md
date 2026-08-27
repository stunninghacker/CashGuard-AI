# ðŸ›¡ï¸ CashGuard AI â€” Predictive Analytics Framework for Cybercrime Cash-Withdrawal Hotspots

**Smart India Hackathon 2026 Â· Ministry of Home Affairs Â· I4C, CIS Division Â· Theme: Blockchain & Cybersecurity**

> An AI/ML-driven framework that analyzes cybercrime complaint data (NCRP/CFCFRMS) and
> ATM withdrawal patterns to **predict where fraudsters will withdraw cash in the next 24 hours** â€”
> and turns that forecast into **actionable intelligence** for police, banks, and I4C.

---

## 1. Problem Statement (Short Version)

India's National Cyber Crime Reporting Portal receives ~8,000 complaints/day. Most financial
fraud losses become **irrecoverable once cash is withdrawn** from ATMs/branches. Existing systems
are **reactive** â€” police and banks act *after* funds move. This framework makes the response
**proactive**: predict likely cash-withdrawal locations + time windows, deploy police teams and
alert banks **before** the withdrawal happens.

## 2. What This Prototype Demonstrates (End-to-End)

| # | Stage | What happens |
|---|-------|--------------|
| 1 | **Synthetic Data** | 12,000+ complaints, 900 ATMs (5 **fictional** cities), 200,000 withdrawals (10% fraud) â€” every generator parameter source-tagged (`verified_pattern` vs `assumption_general_literature`) in `calibration_config.yaml` + `CALIBRATION_NOTES.md` |
| 2 | **ML Engine** | XGBoost + Platt calibration â€” P(fraud withdrawal at ATM in next 24h) â€” **ROC-AUC 0.96, Precision@20/50/100 = 100%** on held-out time; **robustness check** (precision@K stable under Â±30% calibration perturbation, see `artifacts/robustness_check.png`) |
| 3 | **Risk Heatmap Dashboard** | Leaflet GIS map, ATMs colored by risk, fictional jurisdiction fields, top-K hotspot lists, **drill-down filters by city / time (as-of replay) / crime category** |
| 4 | **Role-based Views** | ðŸš” Police (hotspots + alert actions + **3-field evidence panel** + intelligence reports), ðŸ¦ Bank (own ATMs + suggested actions), ðŸ›ï¸ I4C-beta (aggregate stats + audit chain) |
| 5 | **Alert Engine** | APScheduler hourly cycle â†’ threshold 0.7 â†’ alerts + mock SMS/email logs + **I4C dispatch webhook log** (all labelled "Simulated"), acknowledge/actioned workflow, **hash-chained audit trail** (Blockchain & Cybersecurity theme) |

## 3. Architecture

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  DATA LAYER         â”‚   â”‚  ML / PREDICTIVE     â”‚   â”‚  SERVICE & API      â”‚
â”‚  synthetic_data.py  â”‚â”€â”€â–¶â”‚  ENGINE              â”‚â”€â”€â–¶â”‚  FastAPI /api/*     â”‚
â”‚  (or NCRP/CFCFRMS   â”‚   â”‚  features.py         â”‚   â”‚  repositories.py    â”‚
â”‚   & bank APIs)      â”‚   â”‚  train.py (XGBoost)  â”‚   â”‚  services.py        â”‚
â”‚  SQLite/PostgreSQL  â”‚   â”‚  inference.py        â”‚   â”‚  alerts/ scheduler  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                                               â”‚
                          â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                          â”‚  FRONTEND (vanilla JS + Leaflet)               â”‚
                          â”‚  Police Â· Bank Â· I4C dashboards                â”‚
                          â”‚  SMS/email mock logs â†’ real gateways in prod   â”‚
                          â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

Key design decision: **data access is isolated in a repository layer** (`backend/repositories.py`).
Swapping the SQLite store for PostgreSQL (change `DATABASE_URL`) or for live
NCRP/CFCFRMS/bank APIs (rewrite repositories only) requires **zero changes** to routes, ML, or UI.

## 4. Quickstart (Local)

### Prerequisites
- Python 3.10â€“3.12 (tested on 3.12)
- Internet access for CDN assets (Leaflet) on first dashboard load

### Step 1 â€” Install
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows     (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
```

### Step 2 â€” One-Command Demo (generates data + trains + serves)
```bash
python run.py
```
Open **http://localhost:8000** â€” select your role and explore. API docs: http://localhost:8000/docs

### Step 3 â€” Step-by-Step (what `run.py` does internally)
```bash
python scripts/generate_data.py        # prints CALIBRATION SUMMARY (source-tagged params),
                                       # then ~12k complaints, 900 ATMs, 200k withdrawals
python scripts/train_model.py          # trains XGBoost + Platt calibration -> artifacts/model.joblib
python scripts/cache_demo_mode.py      # pre-computes the DEMO_MODE "golden path" fallback cache
python scripts/robustness_check.py     # (one-time, ~5 min) Â±30% perturbation -> robustness_check.png
python -m uvicorn backend.api.main:app --port 8000
```

### Docker (optional)
```bash
docker compose up --build      # full pipeline inside a container, http://localhost:8000
```

## 5. Demo Script (5 Minutes for Judges)

Full click-by-click walkthrough + failure contingency: **`DEMO_SCRIPT.md`**.

**Four demo users (bcrypt + JWT auth, Phase 3):**

| Username | Password | Role | Scope |
|---|---|---|---|
| `officer.statea` | `PoliceStateA!1` | POLICE_STATE | State-A |
| `officer.district1` | `District1!1` | POLICE_DISTRICT | Northsagar |
| `bank.hdfc` | `HdfcBank!1` | BANK | HDFC Bank |
| `i4c.admin` | `I4cAdmin!1` | I4C_ADMIN | national |

1. `python run.py` — watch the calibration summary, then training (with
   **baseline lift + lead-time** metrics).
2. Open **http://localhost:8000** → sign in as a police officer (row-level RBAC
   means a district officer only sees their district).
3. **Map + drill-downs**: category chips, date replay, state→city→bank cascade,
   observed-heat vs forecast-risk toggles.
4. **⚡ Run Alert Cycle** → live **WebSocket** push → alert feed → **Details** →
   3-field evidence panel (verified/assumed disclosure, CFCFRMS freeze intel,
   NOT-SHAP contributions) → **PDF Intelligence Report**.
5. **Bank login** → only HDFC ATMs + **Fund-Block queue** + **recovery funnel**.
6. **I4C login** → national stats, **recovery funnel headline**, **I4C Inbox**
   (real webhook → local mock receiver), **Verify Ledger** + **tamper demo**,
   Situational Report PDF.

**Fallback**: `DEMO_MODE=true` serves the pre-computed golden path — same UI,
zero live inference (see DEMO_SCRIPT.md §3).

## 6. Data Schema (jurisdiction-aware)

| Table | Key fields | Source in production |
|-------|-----------|----------------------|
| `complaints` | complaint_id, filing_timestamp, complaint_type, victim_city/district/**state**/pin, amount_lost, linked_account_id, linked_phone, status | NCRP portal |
| `atms` | atm_id, bank_name, branch_name, city, district, **state**, pin, **police_station_area**, lat, lon | Bank ATM network feeds |
| `withdrawals` | transaction_id, timestamp, atm_id, account_id, amount, channel, is_fraud_withdrawal | Bank/NPCI transaction feeds |
| `alerts` | alert_id, created_at, atm_id, risk_score, recommended_action, **state/district/police_station_area**, status, sms_log, email_log | Generated by this engine |

Jurisdiction fields (`state`, `district`, `police_station_area`) populate on every
ATM/alert from Phase 1 onward â€” full inter-agency routing logic is explicitly
future work (see `LIMITATIONS.md` Â§2).

## 7. ML Approach

**Task**: for each ATM and each day â†’ predict P(fraud withdrawal in next 24h).
**Forecast convention**: the model scores the window `[next midnight, next midnight + 24h)`
using **everything known up to now** â€” "based on today's complaints and cash-outs, where
do fraudsters withdraw tomorrow?" â€” mirroring daily LEA deployment planning. The 24h
horizon is justified by the RBI 2026 1-hour lag-credit hold on P2P UPI credits above
â‚¹10,000 (compresses the fraud-to-cashout window).
**Features (24)**: complaint counts 24h/7d per city & district, hours since last complaint,
complaint-type distribution, withdrawals 1h/6h/24h per ATM, amount sum, distinct accounts,
mule-account share, historical fraud at the ATM, distance to complaint centroid & city center,
day-of-week/weekend/trend, **plus IBA behavioural-signature features** â€” transaction
frequency, counterparty (mule) count, fund velocity (INR/h), activity spike flag.
**All features use data strictly before the prediction day (no leakage)** â€” and mule
accounts in the generator carry normal banking history so "linked account present" is not
a trivially lagged fraud label.
**Split**: chronological 70/30. **Model**: XGBoost (hist, early stopping, AUC-PR eval) +
Platt sigmoid calibration (the 0.7 alert threshold is a true probability).
**Metrics**: ROC-AUC 0.96, Precision@20/50/100 = 1.0 (operational: police deploy to top-K).
**Robustness**: precision@K unchanged under Â±30% perturbation of clustering/timing/behaviour
parameters (`artifacts/robustness_check.png`).

**Explainability** (evidence panel): global XGBoost `feature_importances_` + instance
percentile vs. the training set â€” **explicitly NOT SHAP**. Every contributing signal is
source-tagged `verified_pattern` / `assumption_general_literature` in the alert detail view
(see `CALIBRATION_NOTES.md`).

## 8. Security (prototype-grade, honest)

- **Role-scoped bearer tokens** (`backend/security.py`): `POST /api/auth/login` issues an
  HMAC-SHA256 signed, expiring token; mutation endpoints (alert status, alert creation,
  training, reports, audit) enforce role via FastAPI dependencies â€” verified live
  (401 without token, 403 for wrong role).
- Read endpoints are open in this prototype for demo fluidity; production replaces
  `security.py` with OAuth2.0/JWT against MHA/I4C identity providers (integration point
  marked in code).
- Env vars for DB URL, model path, `AUTH_SECRET`, `DEMO_MODE`; Dockerfile provided.

## 9. Production Integration Path (Real Data)

1. **NCRP/CFCFRMS**: replace `synthetic_data.generate_all()` with ETL/API pulls
   (`repositories.py` integration point is marked in code).
2. **Banks**: wire `withdrawals` & `atms` tables to bank/NPCI feeds (same schema).
3. **Notifications**: swap mock gateways in `backend/alerts/notifier.py` for NIC SMS /
   SendGrid / I4C webhook â€” one file.
4. **Auth**: replace `backend/security.py` with OAuth2/JWT middleware against MHA/I4C
   identity providers (route dependencies already role-scoped).
5. **Storage**: set `DATABASE_URL=postgresql://...` â€” no code changes.
6. **Deployment**: Dockerfile provided; scale inference with FastAPI + uvicorn workers.

## 10. Future Scope

- Real-data pilots with I4C/MHA and partner banks; model monitoring & drift detection
- **Anchor the audit hash chain to a permissioned blockchain/ledger** (the prototype's
  SHA-256 chain already provides tamper-evidence â€” the SIH "Blockchain & Cybersecurity"
  theme is implemented live; ledger anchoring is the production upgrade)
- Federated learning across banks without sharing raw transaction data
- Hourly granularity (currently daily), sub-city geo grids, district-level routing
- True SHAP per-instance attribution (evidence panel currently uses global importance
  + instance percentile, honestly labelled)
- Inter-agency routing/handoff (depends on non-public MHA/I4C protocols)
- Fairness/bias audits to avoid over-policing specific areas

## 11. Honesty & Honesty Documents (read these before quoting metrics)

| Document | Purpose |
|----------|---------|
| `CALIBRATION_NOTES.md` | Every generator parameter + source tag + citation (I4C Suspect Registry, IBA, RBI 2026 rule) |
| `LIMITATIONS.md` | ONE consolidated file: evaluation ceiling, jurisdiction limits, explainability method, operational caveats |
| `DEMO_SCRIPT.md` | Click-by-click walkthrough + DEMO_MODE fallback plan + evaluation-honesty opening line |

## 12. API Reference (Summary)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/auth/login` `/auth/refresh` `/auth/me` | bcrypt + JWT (access/refresh), role+scope |
| GET | `/complaints?city=&state=&type=&date_from=` | Complaint records (role-scoped, tokenized PII) |
| GET | `/atms?city=&bank_name=` `/atms/banks` | ATM network (role-scoped) |
| GET | `/withdrawals?atm_id=&fraud_only=` | Withdrawals (PII-safe tokens) |
| GET | `/risk-scores?city=&as_of=` `/hotspots?k=&category=` | P(fraud in next 24h), role-scoped |
| GET | `/alerts` POST `/alerts` POST `/alerts/run-now` | Alert list / create / demo cycle |
| GET | `/alerts/{id}/evidence` | 3-field evidence + CFCFRMS freeze intel |
| POST | `/alerts/{id}/status` | acknowledge / actioned (ledger-logged) |
| POST | `/reports/hotspot/{alert_id}` `/reports/situational` | PDF intelligence reports |
| GET | `/reports/{id}` `/reports/{id}/download` | Report payload / PDF |
| GET | `/recovery/recommendations` `/recovery/funnel` | Fund-block queue + recovery funnel |
| POST | `/recovery/{id}/status` | freeze_requested / held / recovered |
| GET | `/ledger` `/ledger/verify` | Tamper-evident hash chain + integrity |
| POST | `/ledger/tamper-demo` | DEMO ONLY: flip a block (ALLOW_TAMPER_DEMO=true) |
| WS | `/ws/alerts` | Live push (alerts / status / recovery) |
| POST | `/mock-i4c-inbox` GET `/mock-i4c-inbox` | REAL webhook receiver (local, mock) + inbox |
| POST | `/ingest/stream/start` `/stop` | StreamSimulatorAdapter (live ingestion demo) |
| POST | `/train` GET `/train/status` | Retrain (I4C_ADMIN) / metrics |
| GET | `/stats/summary` | I4C national aggregate + category drill-down |

## 13. Project Layout

```
CashGuard AI/
â”œâ”€â”€ run.py                    # one-command bootstrap (gen â†’ train â†’ serve)
â”œâ”€â”€ requirements.txt / .env.example / Dockerfile / docker-compose.yml
â”œâ”€â”€ CALIBRATION_NOTES.md      # parameter sourcing: verified vs assumed, with citations
â”œâ”€â”€ LIMITATIONS.md            # consolidated honesty document (read first)
â”œâ”€â”€ DEMO_SCRIPT.md            # judge walkthrough + DEMO_MODE fallback plan
â”œâ”€â”€ backend/
â”‚   â”œâ”€â”€ config.py             # env-driven configuration (+ DEMO_MODE flag)
â”‚   â”œâ”€â”€ database.py           # SQLAlchemy engine (SQLite â‡„ PostgreSQL)
â”‚   â”œâ”€â”€ models.py             # ORM: complaints / atms / withdrawals / alerts (jurisdiction-aware)
â”‚   â”œâ”€â”€ repositories.py       # ONLY data-access layer (API-swap point)
â”‚   â”œâ”€â”€ services.py           # risk scoring, alert cycle, evidence panel, stats
â”‚   â”œâ”€â”€ schemas.py            # Pydantic contracts
â”‚   â”œâ”€â”€ data/calibration_config.yaml  # ALL generator params, source-tagged
â”‚   â”œâ”€â”€ data/synthetic_data.py# calibrated generator (fictional locations)
â”‚   â”œâ”€â”€ ml/features.py        # 24 leak-free features incl. behavioural signature
â”‚   â”œâ”€â”€ ml/train.py           # XGBoost + Platt calibration + quantiles + precision@K
â”‚   â”œâ”€â”€ ml/inference.py       # live risk scoring (+ feature rows for evidence)
â”‚   â”œâ”€â”€ alerts/notifier.py    # mock SMS/email (+ prod integration points)
â”‚   â”œâ”€â”€ alerts/scheduler.py   # APScheduler alert engine
â”‚   â””â”€â”€ api/                  # FastAPI app + REST routes
â”œâ”€â”€ frontend/                 # dashboard (HTML/CSS/JS + Leaflet, no build step)
â”œâ”€â”€ scripts/                  # generate_data Â· train_model Â· robustness_check Â· cache_demo_mode Â· run_scheduler
â”œâ”€â”€ artifacts/                # model.joblib Â· metrics.json Â· robustness_check.png
â”œâ”€â”€ data/                     # cashguard.db Â· CSVs Â· demo_cache/ (golden path)
â””â”€â”€ presentation/PITCH.md     # 5-minute judge pitch outline
```

> âš ï¸ **Ethics & safety**: all data is synthetic; live UI locations are fictionalized;
> real district names appear only in CALIBRATION_NOTES.md as methodology citations.
> In production, operate strictly within program scope, minimize footprint, and never
> exfiltrate real victim data â€” PoCs only.
