# DPDP_ACT_COMPLIANCE.md — Privacy Posture for the I4C–Bank–Police Pipeline

Mapped against the Digital Personal Data Protection Act, 2023 (DPDP Act)
principles. This is a compliance *posture* document for a prototype on
synthetic data; the pilot (REAL_DATA_VALIDATION_PROTOCOL.md) is where the
controls are exercised against real personal data under I4C's lawful basis.

## 1. Data minimization (DPDP §5 — collection limited to what is necessary)
- Only the fields required for forecasting are collected: complaint metadata,
  linked-account/phone **tokens**, ATM network fields, withdrawal records.
- **No demographics, no community/religion/caste, no government IDs, no raw
  names or phone numbers** in the analytical pipeline — enforced in code
  (`Pseudonymizer` at ingestion; grep-verified).
- The vault stores raw identifiers separately for lawful re-identification,
  role-scoped and audit-logged (PRIVACY_MODEL.md).

## 2. Purpose limitation (DPDP §5 — use only for the stated purpose)
- Purpose: cybercrime cash-out location forecasting for proactive
  intervention and recovery, per SIH26184 and I4C's statutory remit.
- The model's features are behaviour + complaint linkage + geography only;
  **no secondary uses** (credit scoring, surveillance, profiling beyond the
  fraud forecast) are implemented or claimed.

## 3. Retention periods (DPDP §8 — deletion when purpose is served)
Prototype defaults (to be finalized with the DPO during the pilot):

| Data class | Default retention | Rationale |
|---|---|---|
| Complaints + linked tokens | 5 years from filing | Statutory/evidentiary use in fraud investigation (subject to I4C rules) |
| Withdrawals | 2 years | Forecast/recovery audit trail |
| Alerts + decisions + ledger | 2 years | Operational accountability; tamper-evident chain |
| Re-identification vault | 5 years, revocable per request | Lawful access path; raw values never in analytics |
| Outcome records | 2 years | Closed-loop monitoring |
| Raw ingestion quarantine | 90 days | Data-quality review then deletion or tokenization |

Deletion = hard delete + ledger entry (auditable disposal).

## 4. Consent basis (DPDP §6)
- The prototype operates on **synthetic data** — no consent flows are
  exercised.
- For the real pilot, the lawful basis is I4C/MHA statutory processing under
  the NCRP/CFCFRMS mandate (not marketing-style consent), with:
  - notice language for data subjects on the NCRP intake form (already
    standard in the portal), and
  - DPDP-compliant consent records for any processing beyond the statutory
    purpose (e.g., sharing with partner banks for fund-block execution).
- Banks receive only what their fund-block duty requires (linked-account
  tokens + amounts at risk), never the full complaint narrative.

## 5. Rights & safeguards
- **Correction/erasure requests**: routed via the vault; tokenized analytics
  rows are reconstructed on lawful request (DPDP §11–12 flows defined for the
  pilot, not yet exercised).
- **Breach response**: every access event is ledger-logged; the tamper-evident
  chain supports forensic review (DPDP §8(6) breach-notice readiness is a
  pilot task with I4C's CERT-In coordination).
- **Children's data**: not applicable to this processing (no such fields).

## 6. What is NOT claimed
- No real personal data is processed today; no consent records exist; no DPO
  engagement has occurred. This document is the design posture, not a
  certification — the pilot's Week-1 data-quality checklist includes a
  DPDP/DPO sign-off gate.