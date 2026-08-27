# DEMO CREDENTIALS

**SYNTHETIC DEMO CREDENTIALS — NOT FOR PRODUCTION.**

These users exist only in the demo database (seeded at server startup) and are
used solely to exercise the four role views during the walkthrough. Production
replaces the entire scheme with OAuth2.0/OIDC against MHA/I4C identity
providers (integration point marked in `backend/security.py`).

| Username | Password | Role | Scope |
|---|---|---|---|
| `officer.statea` | `PoliceStateA!1` | POLICE_STATE | State-A |
| `officer.district1` | `District1!1` | POLICE_DISTRICT | Northsagar |
| `bank.hdfc` | `HdfcBank!1` | BANK | HDFC Bank |
| `i4c.admin` | `I4cAdmin!1` | I4C_ADMIN | national |

Notes:
- All data behind these accounts is synthetic; there is no real PII, no real
  bank data, and no real government access.
- `AUTH_SECRET` is a dev placeholder by default and must be env-forced in any
  non-demo deployment.
- Do not reuse these credentials anywhere outside the local demo.