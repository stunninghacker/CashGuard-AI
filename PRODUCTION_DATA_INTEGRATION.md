# PRODUCTION_DATA_INTEGRATION.md — Data Contracts (Phase 12)

This prototype does **NOT** claim access to NCRP / CFCFRMS / bank / NPCI APIs.
What exists: explicit provider interfaces + the synthetic implementation as the
default, so a production team swaps implementations, not architecture.

## Provider interfaces

| Provider | Consumed by | Default impl | Production impl (not built) |
|---|---|---|---|
| `ComplaintDataProvider` | complaints table / features | `synthetic_data.generate_all` | NCRP export/API |
| `ATMDataProvider` | atms table | `synthetic_data.generate_atms` | Bank ATM network feeds |
| `WithdrawalDataProvider` | withdrawals table | `synthetic_data.generate_withdrawals` | Bank/NPCI transaction feeds |
| `OutcomeDataProvider` | alert_outcomes | closed-loop evaluator (synthetic label) | Investigation-confirmed outcomes |

All data access flows through `backend/repositories.py` — the single swap point
(already the case in code).

## Expected fields & types (contract)

| Table | Field | Type | Required |
|---|---|---|---|
| complaints | complaint_id | str | yes |
| complaints | filing_timestamp | datetime | yes |
| complaints | complaint_type | enum(phishing, investment_fraud, job_fraud, upi_fraud, digital_arrest, sextortion) | yes |
| complaints | victim_city / district / state | str | yes |
| complaints | amount_lost | float INR | yes |
| complaints | linked_account_token / linked_phone_token | str (pseudonymized) | yes |
| atms | atm_id, bank_name, branch_name, city, district, state, pin, police_station_area | str | yes |
| atms | latitude, longitude | float | yes |
| withdrawals | transaction_id, timestamp, atm_id, account_token, amount, channel | str/datetime/float | yes |
| withdrawals | is_fraud_withdrawal | bool | training/eval only |

## Operational assumptions (marked as ASSUMPTIONS, not facts)

- **Ingestion frequency**: NCRP complaint batch 15 min – hourly (assumed);
  withdrawal feed near-real-time (assumed); ATM master daily (assumed).
- **Authentication**: mTLS / service-to-service tokens for bank and MHA APIs
  (assumption; actual mechanisms are MHA/bank-internal).
- **Rate limits**: to be agreed with each data owner; the prototype's in-app
  rate limiter is for the demo only.
- **Data validation**: each provider must emit a schema-validated batch with a
  `data_through` timestamp; invalid batches are rejected and logged, never
  silently dropped.
- **Failure handling**: provider outage → risk engine runs on the last good
  snapshot, alerts carry `data_freshness_hours`, and stale-data alerts are
  auto-labelled HOLD ACTION (prototype implements the freshness flag).
- **Privacy**: providers deliver pseudonymized tokens, not raw identifiers
  (see PRIVACY_MODEL.md).

## Architecture status matrix (explicit, never mixed)

| Component | Status | Evidence / notes |
|---|---|---|
| Synthetic generator (NCRP-style complaints, bank feeds) | **IMPLEMENTED** | backend/data/synthetic_data.py |
| FastAPI + SQLAlchemy repository layer | **IMPLEMENTED** | routes + repositories.py (single data door) |
| JWT + bcrypt auth, RBAC, row-level scoping | **IMPLEMENTED** | security.py; 14 regression tests pass |
| Alert engine + dedup + WebSocket push | **IMPLEMENTED** | scheduler/services/realtime |
| Tamper-evident SHA-256 audit chain | **IMPLEMENTED** | ledger endpoints; tamper demo verified |
| Short-TTL single-flight inference cache | **IMPLEMENTED** | services.py; 8-user concurrency 5.5s |
| DEMO_MODE deterministic fallback (no model needed) | **IMPLEMENTED** | kill-tested with model file deleted |
| NCRP portal ingestion | **SIMULATED** (adapter + schema contract) → **PLANNED** (authorized access) | repositories swap point; REAL_DATA_VALIDATION_PROTOCOL.md |
| CFCFRMS fund-block / recovery integration | **SIMULATED** (mock webhook receiver, queue) → **PLANNED** (real API) | mock-i4c-inbox verified with real HTTP POSTs |
| Bank/NPCI withdrawal feeds | **SIMULATED** (generator) → **PLANNED** | schema-compatible ETL path |
| MHA/I4C identity (OAuth2.0/OIDC, SSO) | **PLANNED** | integration point marked in security.py |
| PostgreSQL | **PLANNED** (one config value; not measured here) | LOAD_TEST.md documents why |
| Redis/distributed cache | **PLANNED** (same single-flight semantics) | LOAD_TEST.md |
| Notification gateway (NIC SMS / SendGrid / webhook) | **SIMULATED** (mock channels) → **PLANNED** | alerts/notifier.py swap point |
| Permissioned-ledger anchoring | **PLANNED** (Tier 2) | NOVELTY.md |

Nothing marked PLANNED is claimed as working.
