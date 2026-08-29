# FINAL_SECURITY_AUDIT.md — Full Control Inventory

Audited 2026-08-27 against the running application (live probes where noted).
Status per control: ✅ verified live · ⚠️ documented gap / demo-scope caveat.

> **Re-verified live 2026-08-30 (Phase 16 re-test)** against the current build on 127.0.0.1:8000.
> Confirmed: anonymous `/risk-scores` → 401; bad password → 401; `officer.district1` sees only
> Northsagar (180 ATMs, `district=Northsagar`); `officer.statea` sees only State-A; `i4c.admin`
> sees all 5 states (900 ATMs); WS `/ws/alerts` without token rejected; `bank.hdfc` denied
> `POST /train` (403); `bank.hdfc` `/recovery/recommendations` is **bank-scoped** — a query-param
> `bank_name` override for a different bank is ignored (`scope_bank = user.scope`, returns 0, not
> another bank's rows), i.e. no BOLA via the param. RBAC row-level isolation holds on the current build.

## Authentication
| Control | Status | Evidence |
|---|---|---|
| Login (bcrypt + HMAC-SHA256 JWT) | ✅ | POST /auth/login → access + refresh tokens; wrong password 401 |
| Token expiry | ✅ | Access TTL 30 min (`JWT_TTL_MINUTES`); refresh 24h; refresh endpoint rotates |
| Anonymous access to data endpoints | ✅ | `/risk-scores` without token → 401 (verified live) |
| Wrong-role access | ✅ | Role-scoped dependencies; 403 for wrong role (verified live in the auth tests) |

## Authorization (row-level)
| Control | Status | Evidence |
|---|---|---|
| District officer sees only own district | ✅ | `/risk-scores` as `officer.district1` returns ONLY Northsagar rows (verified via API JSON, not UI) |
| Bank sees only own bank | ✅ | `bank.hdfc` returns ONLY HDFC Bank rows (verified live) |
| State officer sees only own state | ✅ | `officer.statea` → State-A only (verified live) |
| I4C national view | ✅ | `i4c.admin` → all 5 states |
| Recovery/reports/evidence/training endpoints | ✅ | Role-gated (`BANK`/`I4C_ADMIN`/`POLICE_*`); `/train` is I4C_ADMIN-only |

## Transport & session
| Control | Status | Evidence |
|---|---|---|
| CORS | ✅ | Default tightened to localhost origins (was `*`) |
| Rate limiting | ✅ | Per-IP middleware; login-strict (10/min); 429 verified under rapid logins |
| CSRF | ⚠️ | No state-changing GETs; mutations are POST/PATCH with JSON bearer tokens — CSRF not exploitable via forms; production adds SameSite cookies + strict CORS |
| TLS | ⚠️ | Deployment concern (production sits behind TLS/LB) |

## WebSocket
| Control | Status | Evidence |
|---|---|---|
| WS authorization | ✅ | `/ws/alerts` requires `?token=` (valid access JWT); missing/invalid → 403/4401 (verified live) |
| WS channel suppression | ✅ | SHADOW_MODE suppresses WS broadcasts |

## Reports, audit, model, mock endpoints
| Control | Status | Evidence |
|---|---|---|
| Report generation/download | ✅ | `POLICE_*`/`I4C_ADMIN` required; PDFs written to fixed `artifacts/reports/` with server-generated ids |
| Ledger endpoints | ✅ | `/ledger`, `/ledger/verify` role-gated; tamper demo gated by `ALLOW_TAMPER_DEMO` (never on in production) |
| Model artifacts | ✅ | `model.joblib` gitignored, no download route; served only via inference endpoints |
| Training endpoint | ✅ | `/train` I4C_ADMIN only |
| Mock inbox POST | ✅ | `X-Webhook-Token` enforced when `WEBHOOK_TOKEN` set (default open only for local demo) |
| Ingest stream | ✅ | `ingest/stream/*` I4C-only |
| PII vault | ✅ | Role-scoped re-identification; tokens only in data tables; no raw values in API responses |

## Demo-mode isolation
- `DEMO_MODE=true` serves the pre-computed cache with zero inference — it is a
  read-only fallback, never a privilege escalation path (auth still applies in
  demo mode).

## Residual items (documented, not blockers)
1. CSRF hardening (SameSite + strict CORS policy) before production.
2. CSP header not set (self-hosted single-page demo; no third-party scripts).
3. TLS termination is a deployment concern.
4. OAuth2.0/OIDC + org SSO replaces the prototype token scheme (integration
   point marked in `backend/security.py`).
5. Auth secret must be env-forced (dev default is flagged in code).