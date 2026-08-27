# REAL_DATA_READINESS.md — What It Takes to Onboard Real Data (One Page)

**Transfer-readiness evidence** (`artifacts/deep_eval/transfer_readiness.json`):
the pipeline retrains on structurally different distributions (7 cities,
18% fraud, 3× mule velocity, faster latency) with **config-only changes, zero
code changes**, AUC degradation ≤ 0.006 worst-case. That is the honest
substitute for "we tested on real data": the pipeline generalizes across
distributions; what remains is calibration and threshold work, not rewrites.

## 1. The exact data contract (what banks/I4C must provide)

| Table | Required columns | Notes |
|---|---|---|
| `complaints` | complaint_id, filing_timestamp, complaint_type, victim_city, victim_district, victim_state, victim_pin, amount_lost, linked_account_token, linked_phone_token | Tokenized at ingestion (salted); raw values go only to the vault. Derived from NCRP/CFCFRMS records. |
| `atms` | atm_id, bank_name, branch_name, city, district, state, pin, police_station_area, latitude, longitude | Bank ATM-network master. |
| `withdrawals` | transaction_id, timestamp, atm_id, account_token, amount, channel | Bank/NPCI feed. `is_fraud_withdrawal` is the LABEL — provided only by investigation-confirmed outcomes, never by the model. |
| `accounts` | account_token, home_bank, first_seen, is_mule (optional), behavioural source fields | Optional; behavioural fields (frequency, counterparty count, velocity, spike) are derived in ETL if not provided. |

- **No demographics, no names, no phone numbers in raw form** — tokens or
  vault-gated identifiers only (DPDP_ACT_COMPLIANCE.md).
- Volumes: ~8,000 complaints/day and the corresponding withdrawal stream
  (≈ 200k rows/day at 10% fraud-density equivalent) are the sizing target.

## 2. Onboarding timeline (pre-registered)

| Week | Milestone |
|---|---|
| W1 | Schema validation + data-quality scorecards on a 2-week historical extract; quarantine logs reviewed |
| W2 | Shadow mode live: predictions recorded, nothing dispatched (`SHADOW_MODE=true`) |
| W3 | Silent prediction: scores vs confirmed outcomes accumulated, per-feature AUC audit re-run |
| W4 | Human-reviewed intervention evaluation on a pilot district; threshold re-derived; fairness/drift baselines set |
| W6+ | Review gate with I4C ops; go/no-go per the pre-registered KPIs in REAL_DATA_VALIDATION_PROTOCOL.md §13 |

## 3. What changes in the ML pipeline (short list — no rewrites)
1. **Calibration refit** (Platt) on the real validation slice — the 0.7
   threshold is re-derived from the real operating curve.
2. **Threshold re-derivation** per pilot KPIs (precision/capture targets).
3. **Per-feature AUC audit re-run** (leak gate) and **PSI drift baselines** set
   from real features.
4. **Model versioning + outcome store** already in place; alerts carry
   `model_version`; outcomes feed the monitor (MODEL_OUTCOME_MONITOR.md).
5. Feature windows, target definition, split discipline, and the HOLD engine
   are unchanged — they were designed for this contract.

## 4. What is NOT claimed
- No real data has been ingested; no real accuracy, savings, or deployment
  exist. This document is the contract + evidence the pipeline is ready,
  not evidence the pilot has run.