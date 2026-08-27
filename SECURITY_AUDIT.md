# SECURITY_AUDIT.md — Final Security Checklist (Phase 16)

Date of audit: iteration 3. Status per control: ✅ verified / ⚠️ documented gap / ❌ open.

| Control | Status | Evidence |
|---|---|---|
| Authentication (bcrypt + JWT access/refresh) | ✅ | `backend/security.py`; `/auth/login` 200 for seeded users; refresh endpoint |
| Authorization / RBAC row-level | ✅ | Repository-layer scoping; verified: district officer sees only Northsagar; bank only HDFC |
| Token expiry / refresh | ✅ | Access TTL 30 min (env `JWT_TTL_MINUTES`), refresh 24h |
| Secrets | ✅ | `.env.example` only; dev defaults flagged; `.env` gitignored; no credentials in repo |
| CORS | ✅ | Default tightened to localhost origins (was `*`) |
| Rate limiting | ✅ | Per-IP middleware; login-strict (10/min); verified 429/401 behaviour |
| Input validation | ✅ | Pydantic schemas on all bodies/params |
| SQL injection | ✅ | SQLAlchemy ORM parameterized queries only |
| XSS | ✅ | Frontend escapes all rendered strings (`esc()`); CSP not set (demo; noted) |
| CSRF | ⚠️ | No state-changing GETs; mutations are POST/PATCH with JSON; demo uses bearer tokens — CSRF not exploitable via forms; production would add SameSite + CORS policy review |
| WebSocket authorization | ✅ (fixed) | `/ws/alerts` now requires `?token=` (access JWT); invalid → close 4401 |
| Report access | ✅ | Reports require auth; role-scoped by `require_auth` |
| File handling | ✅ | PDFs written to fixed `artifacts/reports/`; filenames server-generated |
| Audit endpoints | ✅ | `/ledger`, `/ledger/verify`, access events chained |
| Demo-only endpoints | ✅ | `ingest/stream/*`, `ledger/tamper-demo` — I4C-only; tamper gated by `ALLOW_TAMPER_DEMO` |
| Mock inbox POST | ✅ (fixed) | `X-Webhook-Token` enforced when `WEBHOOK_TOKEN` configured; open by default only for demo |
| Training endpoint | ✅ | `/train` I4C_ADMIN only |
| Model artifact access | ✅ | `model.joblib` gitignored + served only via inference endpoints; no download route |
| Outcome endpoints | ✅ | `/alerts/outcomes/*` — I4C/POLICE_STATE only |

## Residual items (documented, not blockers for the demo)
- CSRF: add SameSite cookies + strict CORS policy before production.
- CSP header not set (frontend is a demo single-page app; no third-party scripts
  beyond self-hosted assets).
- TLS termination is a deployment concern (production behind TLS/LB).
- OAuth2/OIDC + org SSO replacement of the prototype token scheme (documented).