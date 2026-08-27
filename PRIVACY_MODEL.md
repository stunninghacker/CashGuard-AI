# PRIVACY_MODEL.md — Privacy-by-Design for Production (Phase 11)

How the production system would handle sensitive NCRP / CFCFRMS / bank data.
The prototype implements the *pattern*; the production version implements the *controls*.

## 1. Data minimization
- Only fields required for forecasting are ingested (complaint type, timestamps,
  district-level location, linked-account token, amount range, withdrawal
  counts at ATM level). Victim identity is NOT needed for prediction.
- Raw phone numbers, full account numbers, and names are **never** stored.

## 2. Pseudonymized identifiers
- Complaints and withdrawals carry salted-hash **tokens** (`acct_…`, `tel_…`),
  exactly as the prototype does. The vault that maps token→raw is a separate,
  access-controlled store with its own audit trail.
- The prototype's vault is a mock with placeholder raws (documented).

## 3. Role-scoped access (enforced server-side)
- POLICE_STATE / POLICE_DISTRICT / BANK / I4C_ADMIN scopes mirror production
  jurisdiction: a district officer cannot query another district; a bank sees
  only its own ATMs/accounts.

## 4. Audit & accountability
- Every access to a record is appended to the tamper-evident ledger
  (event_type="access", actor, resource, timestamp). This satisfies the DPDP-Act
  access-log expectation and gives re-identification attempts a trail.

## 5. Retention
- Configurable retention window (env: `RETENTION_DAYS`, default prototype: none
  enforced). Production: complaints aggregated to district-day counts after the
  investigation window; withdrawal records retained per RBI/banking record
  retention rules; tokens retained only while an investigation is open.

## 6. Anti-profiling guarantee
- No demographic, community, religion, caste, or similar feature exists
  anywhere (enforced in code and by review). Risk = transaction behaviour +
  complaint linkage + transaction geography only.

## 7. Purpose limitation
- Data is used solely for fraud-withdrawal forecasting, fund-blocking
  coordination, and model monitoring — not for any other purpose.

## 8. Incident handling (assumption, clearly marked)
- Real deployment would define breach notification per DPDP-Act timelines
  (72h to the Board); this prototype documents the posture, not a live policy.