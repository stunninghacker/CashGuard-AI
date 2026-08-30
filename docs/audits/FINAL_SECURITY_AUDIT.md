# FINAL_SECURITY_AUDIT.md — Full Control Inventory

Audited 2026-08-27 against the running application (live probes where noted).
Status per control: ✅ verified live · ⚠️ documented gap / demo-scope caveat.

> **Re-verified live 2026-08-30 (Phase 16 re-test)** against the current build on 127.0.0.1:8000.
> Confirmed: anonymous `/risk-scores` → 401; bad password → 401; `officer.district1` sees only
> Northsagar (180 ATMs, `district=Northsagar`); `officer.statea` sees only State-A; `i4c.admin`
> sees all 5 states (900 ATMs); WS `/ws/alerts` without token rejected; `bank.hdfc` denied
> `POST /train` (403); `bank.hdfc` `/recovery/recommendations` is **bank-scoped** — a query-param
> `bank_name` override for a different bank is ignored (`scope_bank = user.scope`, returns 0, not
> another bank's rows), i.e. no BOLA via the param.

> **Phase 11/12 security red-team added 2026-08-30 — 3 findings discovered, root-caused and FIXED**
> (full detail in `FINAL_SECURITY_RED_TEAM.md` + `RBAC_MATRIX.md`):
> 1. **CRITICAL — default JWT secret → HS256 token forgery → full I4C admin.** The running app used the
>    public default `dev-secret-change-in-production`. Forged `sub='u-i4c'` token got `200` on
>    `/auth/me` and `POST /reports/situational` (admin action executed); control DISTRICT token got `403`
>    (RBAC role logic intact, secret was the flaw). **FIX:** `_secure_boot_check()` in `backend/api/main.py`
>    now REFUSES to serve unless `JWT_SECRET` is not the public default OR `ALLOW_INSECURE_DEFAULT_JWT=1`
>    (demo). Verified: default secret → BLOCKED; strong secret / explicit opt-in → STARTED.
> 2. **HIGH — `/withdrawals` had NO bank scoping (bank→bank IDOR).** `repo.list_withdrawals` never filtered
>    by bank; `backend/api/routes/withdrawals.py:32` passed no `user`. Live: `bank.hdfc` read withdrawals
>    from **543 non-HDFC ATMs** (636 distinct vs 127 HDFC-owned). **FIX:** `list_withdrawals(..., user=)` now
>    joins to ATMs and restricts `BANK` scope to `ATM.bank_name == user.scope`. Verified across the full
>    dataset: BANK-HDFC sees **exactly its 127 ATMs, 0 non-HDFC rows**; police/I4C still see all.
> 3. **MEDIUM — `POST /alerts` allowed out-of-jurisdiction writes.** A `POLICE_STATE` user could create an
>    alert for any ATM, including another state. **FIX:** `create_alert` returns `403` when the ATM's state
>    is outside a `POLICE_STATE` caller's scope (`I4C_ADMIN` national stays open). Verified: out-of-state
>    403, in-state OK, I4C OK.

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
| Bank sees only own bank (withdrawals) | ✅ **FIXED 2026-08-30** | `bank.hdfc` `/withdrawals` was UN-scoped (read 543 non-HDFC ATMs). Now `list_withdrawals(..., user=)` scopes to `ATM.bank_name == user.scope`; re-verified full dataset: 0 other-bank rows. `/atms`,`/risk-scores`,`/recovery` were already bank-scoped. |
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
5. ✅ **FIXED 2026-08-30** — Auth/JWT secret hardening: `_secure_boot_check()` refuses to serve
   with the public default JWT secret unless explicitly opted in
   (`ALLOW_INSECURE_DEFAULT_JWT=1`, demo only). A strong `JWT_SECRET` is now enforced for any
   non-demo run.