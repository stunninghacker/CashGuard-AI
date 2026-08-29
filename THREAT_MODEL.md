# Threat Model — CashGuard AI (SIH26184 Prototype)

**Scope**: Hackathon prototype demonstrating predictive fraud-withdrawal intelligence for I4C/CFCFRMS. Not a production system. All data is synthetic. Threat model follows STRIDE + data-flow analysis on the prototype architecture.

---

## System Overview

```
┌─────────────┐     ┌──────────────────────────────────────────────────┐
│  Data Feeds │────▶│  Backend (FastAPI + APScheduler)                 │
│  (synthetic)│     │  • ML inference (XGBoost)                        │
│  • NCRP     │     │  • Alert engine + dedup + fairness cap           │
│  • ATM logs │     │  • CFCFRMS fund-block recommendations            │
│  • Transfers│     │  • Mule-graph (terminal cash-out centrality)     │
└─────────────┘     │  • RBAC (I4C_ADMIN / POLICE_STATE / POLICE_DISTRICT / BANK) │
                    │  • JWT auth + bcrypt                             │
                    │  • Tamper-evident ledger (hash chain)            │
                    └──────────────────────┬───────────────────────────┘
                                           ▼
                              ┌──────────────────────────┐
                              │  Frontend (vanilla JS)   │
                              │  • Leaflet risk heatmap  │
                              │  • Drill-down filters    │
                              │  • Evidence panel (3-field)│
                              │  • Money-trail graph     │
                              │  • WS live feed          │
                              └──────────────────────────┘
```

**Trust Boundaries**:
1. **External → Backend**: Synthetic data feeds (no real NCRP/CFCFRMS integration in prototype)
2. **Backend → Frontend**: Authenticated API + WS (JWT, role-scoped)
3. **Scheduler → DB**: Background job with own DB session
4. **Webhook → Mock Inbox**: Local HTTP POST (simulates I4C/CFCFRMS gateway)

---

## STRIDE Analysis

### 1. Spoofing

| Vector | Risk | Mitigation |
|--------|------|------------|
| Stolen JWT / credential reuse | **Medium** | Short JWT TTL (30 min), refresh token rotation, bcrypt password hashing, rate-limited login (10/min), ledger audit on every access |
| Fake webhook payload to mock inbox | **Low (prototype)** | `WEBHOOK_TOKEN` optional HMAC check on `/mock-i4c-inbox`; production would require mTLS + signed payloads |
| Role escalation via token tampering | **Low** | HS256 signature validation, role claim in token, server-side RBAC re-check on every request |

### 2. Tampering

| Vector | Risk | Mitigation |
|--------|------|------------|
| Alert status/evidence modification | **Medium** | Immutable append-only ledger (hash chain) records every state change + reason; `/ledger/verify` detects tampering |
| ML model / metrics substitution | **Low** | Artifacts loaded from local filesystem (`artifacts/model.joblib`, `metrics.json`); production would use signed/versioned artifact store |
| Synthetic data regeneration altering labels | **Medium (demo)** | `scripts/generate_data.py` wipes tables idempotently; `VERIFICATION_LOG.md` documents every regeneration |
| Transfer graph edges injected to skew terminal risk | **Low** | Transfer edges are generated synthetically with fixed seed; no external input path in prototype |

### 3. Repudiation

| Vector | Risk | Mitigation |
|--------|------|------------|
| Operator denies taking action on alert | **Low** | Every status change (acknowledged/actioned/dismissed/escalated) requires a recorded reason; ledger records actor + timestamp + reason hash-chained |
| Scheduler denies auto-escalation | **Low** | Auto-escalation events logged to ledger with actor="scheduler (auto-escalation)" |

### 4. Information Disclosure

| Vector | Risk | Mitigation |
|--------|------|------------|
| Cross-role data access (e.g., Bank sees other bank's ATMs) | **Medium** | Row-level scoping in repository layer: `repo.list_atms(db, user)` applies `_scoped_atm_stmt`; same for accounts, complaints, alerts |
| PII leakage via account tokens | **Low** | All account identifiers are pseudonymised tokens (`acct_...`); raw PII never stored in DB or sent to frontend |
| Transfer graph exposes money-laundering patterns | **Low (synthetic)** | Demo data is fully synthetic; production would require PII-pseudonymisation + access logging per DPDP Act |
| Model metrics / calibration config exposed | **Low** | Metrics are synthetic evaluation results; no real victim data |

### 5. Denial of Service

| Vector | Risk | Mitigation |
|--------|------|------------|
| Alert flood (many ATMs flagged) | **Low** | Fairness cap (per-state proportional budget) limits actionable alerts; excess demoted to "monitor" |
| WebSocket connection exhaustion | **Low** | Single WS endpoint `/ws/alerts` with JWT auth; in-memory broadcast queue; demo scale only |
| Scheduler job overlap / DB lock | **Low** | `BackgroundScheduler` with single-threaded executor; SQLite `check_same_thread=False`; production would use PostgreSQL + pgbouncer |
| Login brute force | **Low** | Rate limit 10 req/min on `/auth/login`; bcrypt slows verification |

### 6. Elevation of Privilege

| Vector | Risk | Mitigation |
|--------|------|------------|
| District police accessing state-level dashboard | **Medium** | Role-based dashboard render: `renderI4C()` only for `I4C_ADMIN`; `renderPolice()` for `POLICE_STATE`/`POLICE_DISTRICT`; route RBAC via `require_auth()` |
| Bank user triggering alert cycle | **Low** | POST `/alerts/run-now` restricted to `I4C_ADMIN` + `POLICE_STATE` |
| SQL injection via query params | **Low** | SQLAlchemy ORM used everywhere; no raw SQL with user input |

---

## Data Flow Threats (DFD)

```
[Data Feeds] ──(synthetic CSV/SQLite)──▶ [Backend DB]
       │                                    │
       │                                    ▼
       │                          [ML Inference] ──▶ [Risk Scores Cache]
       │                                    │
       ▼                                    ▼
[Transfer Gen] ──(synthetic)──▶ [Mule Graph] ──▶ [Terminal Risk API]
                                          │
                                          ▼
                                 [Alert Engine] ──▶ [Alerts Table]
                                                    │
                    ┌──────────────────────────────┼──────────────────────────────┐
                    ▼                              ▼                              ▼
            [Mock SMS/Email]              [Webhook → Mock Inbox]            [WS Broadcast]
            (logged only)                 (local HTTP POST)                 (dashboard push)
```

**Critical Flows**:
1. **Risk Scores → Alerts**: Threshold-based; fairness cap prevents jurisdiction monopolization.
2. **Alerts → Actions**: Human-in-the-loop; every transition audited.
3. **Transfers → Mule Graph**: Pure-Python, no external deps; runs on demand via API.
4. **Scheduler → DB**: Separate session; errors caught + logged, loop continues.

---

## Prototype-Specific Gaps (Not Production Hardening)

| Gap | Why Acceptable for Prototype | Production Fix |
|-----|------------------------------|----------------|
| SQLite single-file DB | Demo portability; no concurrent writers | PostgreSQL + read replicas |
| HS256 JWT with static secret | Simplicity; secret in `.env` | OAuth2/OIDC + org SSO (NIC/MHA IdP), key rotation |
| In-memory rate limit / WS broadcast | Single-instance demo | Redis-backed distributed limiter + pub/sub |
| Mock SMS/Email/Webhook | No external credentials | NIC SMS gateway, SendGrid/SES, signed webhook endpoints |
| No TLS termination | Localhost demo | HTTPS via reverse proxy (nginx/Traefik) + cert-manager |
| No secrets manager | `.env` file | Vault / AWS Secrets Manager / Azure Key Vault |
| No automated backup / DR | Hackathon scope | Point-in-time recovery, cross-region replication |

---

## Mitigation Summary (Priority for Production)

| Priority | Mitigation |
|----------|------------|
| **P0** | Replace JWT with OAuth2/OIDC + organizational SSO; enforce mTLS on all service-to-service |
| **P0** | Move to PostgreSQL with row-level security policies mirroring repo scoping |
| **P0** | Sign all webhook payloads (JWS); verify on receiver; enforce `WEBHOOK_TOKEN` |
| **P1** | Artifact signing (cosign/slsa) for model + metrics; versioned model registry |
| **P1** | Distributed rate limiting (Redis); WS connection pooling + backpressure |
| **P1** | PII pseudonymisation pipeline (DPDP Act compliance) for any real data ingestion |
| **P2** | Ledger anchoring to immutable store (blockchain testnet or AWS QLDB) |
| **P2** | Automated backup + chaos testing (kill scheduler mid-cycle, verify ledger integrity) |
| **P3** | Security headers (CSP, HSTS, Referrer-Policy) via reverse proxy |
| **P3** | Pen-test / SAST / DAST on API surface; dependency scanning (Dependabot) |

---

## Assumptions & Out of Scope

- **All data is synthetic** — no real victim PII, no real NCRP/CFCFRMS feeds.
- **No external network calls** in default config (webhooks point to local mock inbox).
- **Single-instance deployment** — no HA, no clustering.
- **No encryption at rest** — SQLite file is local; production requires TDE / volume encryption.
- **No WAF / API gateway** — prototype serves direct from uvicorn.

---

## References

- `backend/security.py` — JWT + RBAC implementation
- `backend/repositories.py` — row-level scoping functions (`_scoped_*_stmt`)
- `backend/alerts/scheduler.py` — alert cycle + auto-escalation
- `backend/services.py` — alert lifecycle + set_alert_status (ledger-audited)
- `backend/ledger.py` — tamper-evident hash chain
- `RESPONSE_PLAYBOOK.md` — graded escalation ladder (human decision required)
- `LIMITATIONS.md` — synthetic evaluation caveats
- `PRODUCTION_DATA_INTEGRATION.md` — integration gaps for real NCRP/CFCFRMS