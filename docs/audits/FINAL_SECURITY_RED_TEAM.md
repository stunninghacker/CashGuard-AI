# FINAL_SECURITY_RED_TEAM.md — Phase 11/12 Findings, Addressed

Red-team conducted 2026-08-30 against the live app on `127.0.0.1:8000` and the
source. Methodology per finding: **DISCOVER → REPRODUCE (live) → ROOT CAUSE →
FIX → NEGATIVE TEST → POSITIVE TEST → DOCUMENT**.

The prior `FINAL_SECURITY_AUDIT.md` (re-verification pass) validated many
controls (auth 401s, role gates, district/state scoping, WS auth, recovery
scoping) but had a blind spot on `/withdrawals` and on the **default JWT secret**.
This red-team closes those gaps. Every finding below is confirmed with concrete
request/response evidence, not hypothesis.

---

## FINDING 1 — [CRITICAL] HS256 JWT forgery via public default secret → full I4C_ADMIN

- **Severity:** Critical · **CVSS 9.8** (AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H)
- **Endpoint:** `/auth/me`, `/reports/situational`, any role-gated route
- **CWE:** CWE-798 (Use of Hard-coded Credentials) / CWE-347 (Improper Verification of Cryptographic Signature)

**Impact:** Attacker with ZERO credentials forges a valid HS256 access token for
any user. Because the signing secret is the well-known public default
`dev-secret-change-in-production` (from `backend/config.py`, not overridden), the
attacker becomes `I4C_ADMIN` (national super-user) — read all states, trigger
national actions, download reports. Complete compromise of confidentiality,
integrity and availability of the fraud-intelligence platform.

**Root cause:** `JWT_SECRET` defaulted to a public constant and that value was
used in production-ish demo without env override. HS256 is symmetric: whoever
knows the secret can sign arbitrary payloads.

**Reproduction (live, pre-fix):**
1. Login is unnecessary. Forge a token signed with the default secret:
   `header={"alg":"HS256"}`, `payload={"sub":"u-i4c","role":"I4C_ADMIN","scope":"National","exp":...}`,
   signature = HMAC-SHA256(secret=default).
2. `GET /auth/me` with `Authorization: Bearer <forged>` → **200**, returns full
   I4C admin profile.
3. `POST /reports/situational` with the same token → **200**, national admin
   action executed.
4. **Control:** forged `POLICE_DISTRICT` token → **403** `Role 'POLICE_DISTRICT'
   not allowed here`. This proves the RBAC role logic is sound — the defect was
   exclusively the public signing secret.

**Fix (implemented):** `_secure_boot_check()` in `backend/api/main.py`, run at
startup (`lifespan`), refuses to serve when `JWT_SECRET` equals the public
default unless `ALLOW_INSECURE_DEFAULT_JWT=1` (demo-only opt-in, with a loud
warning). A real deployment MUST export a strong random `JWT_SECRET` (≥32 chars).

**Negative test (passes):** default secret, no opt-in → `RuntimeError:
Refusing to start: JWT_SECRET is the public default …`.
**Positive test (passes):** strong 64-char `JWT_SECRET` → starts; explicit
`ALLOW_INSECURE_DEFAULT_JWT=1` → starts with warning.

---

## FINDING 2 — [HIGH] Bank→bank isolation failure on GET /withdrawals (IDOR / BOLA)

- **Severity:** High · **CVSS 8.1** (AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N)
- **Endpoint:** `GET /withdrawals`
- **Parameter:** `atm_id` (omitted → all ATMs), BANK role caller
- **CWE:** CWE-639 (Authorization Bypass Through User-Controlled Key) / CWE-862

**Impact:** A `BANK` user (e.g. `bank.hdfc`) can read the complete ATM withdrawal
history of EVERY bank — amounts, timestamps, channels and **fraud flags** —
simply by calling `/withdrawals` with any `atm_id` (or none). This leaks cross-bank
transaction intelligence and exposes which accounts at other banks are flagged
fraudulent — a direct violation of the bank-isolation contract the product
advertises.

**Root cause:** `repo.list_withdrawals` in `backend/repositories.py` had **no
`user` parameter and no bank filter**; `backend/api/routes/withdrawals.py:32`
called it without scoping. `/atms`, `/risk-scores`, `/recovery` were correctly
bank-scoped, but `/withdrawals` was a scoping gap.

**Reproduction (live, pre-fix):**
- Login `bank.hdfc` → access token.
- `GET /atms` (scoped) → **127 HDFC ATMs**.
- `GET /withdrawals` (unscoped) → **636 distinct ATMs, of which 543 are NOT
  HDFC** (e.g. `ATM-DIS0001…` District bank). Bank read other banks' data.

**Fix (implemented):** `list_withdrawals(..., user=None)` now, for `BANK`-role
callers, joins withdrawals to `ATM` and restricts to
`ATM.bank_name == user.scope` (server-side, never trusted on the client).
`withdrawals.py` passes `user=user`. Police/I4C retain full national visibility.

**Negative test (passes):** `BANK(HDFC).list_withdrawals(limit=1000)` → **0**
non-HDFC rows; full-dataset pagination (20,000+ rows) → **0 leaked**, exactly the
**127 HDFC ATMs** visible.
**Positive test (passes):** HDFC rows still returned to its own bank; no-user /
`POLICE_STATE` / `I4C_ADMIN` callers still see all rows (control unaffected).

---

## FINDING 3 — [MEDIUM] POLICE_STATE can write alerts outside its jurisdiction

- **Severity:** Medium · **CVSS 5.4** (AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:L/A:N)
- **Endpoint:** `POST /alerts`
- **Parameter:** `atm_id` (any state)
- **CWE:** CWE-863 (Incorrect Authorization)

**Impact:** A state-police user (scope `State-A`) can fabricate an alert for an
ATM in any other state — injecting fraudulent alert records / SMS+email queues
into jurisdictions they do not own (mass / cross-jurisdiction pollution).

**Root cause:** `create_alert` in `backend/api/routes/alerts.py` authorized on
*role* (`POLICE_STATE`/`I4C_ADMIN`) but never enforced the ATM's *jurisdiction
(state)* against the caller's scope on the write path.

**Reproduction (live, pre-fix):** `POLICE_STATE(scope=State-A)` →
`POST /alerts {atm_id: ATM-MET0000 (State-B)}` → **200** (created out-of-scope).

**Fix (implemented):** `create_alert` returns **403** when a `POLICE_STATE` caller
targets an ATM whose `state` differs from `user.scope`. `I4C_ADMIN` remains
national (can create anywhere).

**Negative test (passes):** `POLICE_STATE(State-A)` → `ATM-MET0000 (State-B)` →
**403** `ATM … is in state 'State-B' which is outside your jurisdiction 'State-A'`.
**Positive test (passes):** `POLICE_STATE(State-A)` → in-state ATM → created;
`I4C_ADMIN` → out-of-state ATM → created (national scope).

---

## Summary

| # | Sev | Finding | Status |
|---|---|---|---|
| 1 | Critical | Default JWT secret → forgery → I4C admin | ✅ Guard enforced (server refuses insecure boot) |
| 2 | High | `/withdrawals` bank→bank IDOR (543 ATMs leaked) | ✅ Server-side bank scoping + re-verified 0 leak |
| 3 | Medium | Out-of-jurisdiction alert writes | ✅ 403 on out-of-state for POLICE_STATE |

All three were discovered, reproduced live, root-caused, fixed in source, and
re-verified with negative + positive regression tests. RBAC matrix:
`RBAC_MATRIX.md`. The running demo process must be restarted from source to
activate the fixes (see `RBAC_MATRIX.md` / operator notes).
