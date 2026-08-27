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