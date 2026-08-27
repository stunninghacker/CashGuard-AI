# REAL_DATA_ONBOARDING.md — from synthetic to pilot (Phase 13)

This document is the honest path to real validation. The prototype does NOT
claim real data access; this is the engineering plan for when access is granted.

## Required fields (minimum viable)
Complaints: complaint_id, filing_timestamp, complaint_type, victim_city/district/
state, amount_lost, linked_account_token, linked_phone_token, status.
ATMs: atm_id, bank_name, branch_name, city, district, state, pin,
police_station_area, latitude, longitude.
Withdrawals: transaction_id, timestamp, atm_id, account_token, amount, channel.
Outcomes (pilot phase): investigation-confirmed withdrawal/fraud flags per alert.

## Data ownership & access-control assumptions (clearly marked)
- NCRP/CFCFRMS data: owned by MHA/I4C; access via agreed MoU + API credentials
  (assumption; mechanisms are MHA-internal).
- Bank/ATM data: owned by banks/NPCI; access via bilateral agreements (assumption).
- All providers deliver **pseudonymized tokens**, never raw identifiers.

## Schema mapping, validation, PII minimization, retention, encryption, audit
- Mapping: providers -> `backend/repositories.py` tables (contracts in
  PRODUCTION_DATA_INTEGRATION.md). Validation: schema check per batch;
  invalid batches rejected + logged. PII: tokens only (PRIVACY_MODEL.md).
  Retention: configurable (RETENTION_DAYS); encryption: TLS in transit, disk
  encryption at rest (production requirement); audit: every access on the
  tamper-evident chain.

## Consent/legal assumptions (clearly marked)
- Victim consent for use of complaint-derived analytics under the DPDP-Act and
  MHA operational mandate — to be confirmed by MHA legal (not claimed).

## Pilot methodology (30-day plan; NO automatic real intervention)
- **Week 1 — Schema validation**: point providers at real batches in a staging
  sandbox; validate schema, latency, missingness, token integrity.
- **Week 2 — Shadow mode**: SHADOW_MODE=true — predictions computed, stored,
  compared to outcomes; NO alerts dispatched, NO operational actions.
- **Week 3 — Silent prediction**: alerts generated and shown only to a
  nominated review team; outcomes recorded; precision/lead-time re-estimated
  against investigation-confirmed withdrawals.
- **Week 4 — Human-reviewed operational evaluation**: limited district/bank
  cohort; every alert goes through the human review gate; metrics: precision,
  recall, lead time, false-alert rate, time-to-intervention, recovery funnel;
  threshold retuning per city/bank via ops review.

## Success criteria
- Week-4 precision ≥ synthetic threshold precision (± tolerance, stated),
  false-alert rate acceptable to ops, lead time ≥ 6h median, zero
  investigation-confirmed wrongful targeting.

## Rollback plan
- Feature flag for the whole pilot; instant revert to shadow/no-op;
  provider failure handling = stale-data HOLD ACTION (already implemented);
  model rollback = versioned artifacts (model_version on every alert).