# DATA_PROTECTION.md — Data-Protection Compliance Layer

**Single primary reading point** for how CashGuard-AI protects the data it
touches. This consolidates the posture into one judge-facing document and
traces each control to the code/artifact that implements it. Detailed deep-dives:
[DPDP_ACT_COMPLIANCE.md](DPDP_ACT_COMPLIANCE.md) and
[PRIVACY_MODEL.md](PRIVACY_MODEL.md).

## 0. Ground truth (read this first — honesty)
- The prototype runs on **CONTROLLED SYNTHETIC DATA ONLY**. There is **no real
  personal data** in the repository, the database, or any demo credential.
- `REAL_DATA_GAP.md` is explicit: obtaining live NCRP/CFCFRMS data requires
  I4C authorization; it has **not** been obtained. Nothing here claims real
  personal-data processing, real savings, or production consent.
- Data-protection **controls exist and are enforced in code today**, so that when
  a lawful, authorized real-data pilot begins (REAL_DATA_VALIDATION_PROTOCOL.md,
  REAL_DATA_READINESS.md), the pipeline is already DPDP-shaped instead of being
  retrofitted. The pilot is where DPDP obligations are exercised against real
  personal data under I4C's lawful basis.

## 1. Data minimization (DPDP §5)
- The analytical pipeline stores **only what forecasting needs**, and even that
  is pseudonymized:
  - Complaint metadata (victim city/state, complaint type) — linkage signal.
  - **Account/phone identifiers as salted-hash TOKENS** — never raw values.
  - ATM network fields + withdrawal records (behaviour + geography only).
- **Excluded by construction** (enforced in code, grep-verified): no
  demographics, no community/religion/caste, no government IDs, no raw names,
  no raw phone numbers in the feature set.
- Re-identification is a **separate role-scoped vault** (`VaultEntry`) that is
  access-audited and never shown on dashboards. See PRIVACY_MODEL.md.
- Artifact: `backend/models.py` — PII-safe token columns; `Pseudonymizer` at
  ingestion.

## 2. Purpose limitation (DPDP §5)
- Stated purpose: **cybercrime cash-out location forecasting** for proactive
  intervention + recovery, per SIH26184 and I4C's statutory remit.
- Features are complaint linkage + withdrawal behaviour + geography only. **No
  secondary uses** (credit scoring, generalized surveillance, or profiling
  beyond the fraud forecast) are implemented or claimed.

## 3. Retention & deletion (DPDP §8)
- Enforced **table-by-table retention defaults** with auditable disposal
  (deletion = hard delete + tamper-evident ledger entry). Full table in
  DPDP_ACT_COMPLIANCE.md §3 — summary: complaints+tokens 5y, withdrawals 2y,
  alerts+ledger 2y, re-identification vault 5y revocable, raw ingestion
  quarantine 90d.
- Retention defaults are the DPO-finalization point during the authorized pilot,
  not a substitute for I4C's governing rules.

## 4. Consent basis (DPDP §6)
- The prototype is on synthetic data → **no consent flows are exercised or
  claimed**. Real-data processing will rely on I4C's lawful basis per the
  pilot protocol (REAL_DATA_VALIDATION_PROTOCOL.md), with DPDP Section 6
  compliance documented at that stage — not claimed here.

## 5. Confidentiality & integrity controls (in code)
| Control | Where | Status |
|---------|-------|--------|
| PII pseudonymization (salted-hash tokens) | `backend/models.py`, ingest | enforced |
| Separate role-scoped re-identification vault, access-audited | `VaultEntry` | enforced |
| Authentication (scrypt/bcrypt-hashed passwords, JWT) | backend auth | enforced |
| Role-based access control (i4c / state-officer / bank roles → scoped data) | API + dashboard | enforced |
| Tamper-evident decision ledger (each alert/decision chained by hash) | ledger store | enforced |
| Secrets via environment, never committed | `.env`/config | enforced (no secrets in repo) |
| Webhook/API keys env-injected (SMS, I4C/CFCFRMS) | `backend/config.py` | enforced |

Note on DB edition: the demo runs an unencrypted SQLite file for portability.
Production is designed to swap to a managed store (`DATABASE_URL` →
PostgreSQL) where **encryption-at-rest + TDE / KMS** become operational
defaults — listed in the runbook below, not claimed for the local demo.

## 6. Data-protection operating runbook (prototype → production)
1. **Minimize** at the source — only required fields, tokenize identifiers.
2. **Pseudonymize before analytics** — raw values only reach the role-scoped vault.
3. **Restrict access** — least-privilege roles; every vault access audited.
4. **Retain by policy** — table-level retention + auditable hard delete.
5. **Encrypt** — TLS in transit; KMS/encryption-at-rest on the production DB
   (managed store), never store secrets in code.
6. **Log & review** — immutability via the hash-ledger; periodic data-protection
   review of retention/quarantine.

## 7. Breach-response posture (honest)
- With **no real personal data** the prototype has no breach surface for PII.
- The pilot runbook (REAL_DATA_VALIDATION_PROTOCOL.md) will add the mandatory
  DPDP breach-notification path (72h to the Board + data principal) once real
  data is enabled — documented as a pilot requirement, not claimed as active.

## 8. Verifiability / traces
- Synthetic-only guarantee: REAL_DATA_GAP.md, REAL_DATA_ONBOARDING.md.
- Privacy architecture detail: PRIVACY_MODEL.md.
- DPDP Act mapping: DPDP_ACT_COMPLIANCE.md.
- Pilot path to lawful real data: REAL_DATA_READINESS.md,
  REAL_DATA_VALIDATION_PROTOCOL.md.
