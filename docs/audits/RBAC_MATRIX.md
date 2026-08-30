# RBAC_MATRIX.md — Authorization Matrix (role × route × scope)

Generated 2026-08-30 after Phase 11/12 security red-team. Rows = routes,
columns = roles. `✅` allowed, `❌` denied, `=scope` access restricted to the
caller's own jurisdiction/bank (server-side, never client-trusted).

Roles & scopes (demo creds):
- `POLICE_STATE` (scope=state, e.g. `State-A`) — state LEA
- `POLICE_DISTRICT` (scope=district, e.g. `Northsagar`) — district LEA
- `BANK` (scope=bank, e.g. `HDFC Bank`) — bank ops
- `I4C_ADMIN` (scope=`National`) — national coordinator

| Route | POLICE_STATE | POLICE_DISTRICT | BANK | I4C_ADMIN | Notes |
|---|---|---|---|---|---|
| `/auth/login` `/auth/refresh` | ✅ | ✅ | ✅ | ✅ | valid creds / refresh token |
| `/auth/me` | ✅ | ✅ | ✅ | ✅ | own profile |
| `/atms` (list) | =state | =district | =bank | ✅ all | verified scoped |
| `/atms/{id}` | ✅ | ✅ | ✅ | ✅ | detail, no sensitive fields |
| `/withdrawals` | ✅ all | ✅ all | **=bank (FIXED-2)** | ✅ all | **was bank→bank IDOR; now scoped via `ATM.bank_name==user.scope`** |
| `/risk-scores` | =state | =district | =bank | ✅ all | verified |
| `/alerts` (list) | =state | =district | =bank | ✅ all | demo-cache read, role-gated |
| `POST /alerts` | **=state write (FIXED-3)** | ❌ | ❌ | ✅ national | **was out-of-jurisdiction write; now 403 for out-of-state POLICE_STATE** |
| `/alerts/{id}` `/evidence` | =state | =district | =bank | ✅ all | `repo.get_alert(...,user=)` scoped |
| `/alerts/{id}/status` | =state | =district | ❌ | ✅ | ledger-logged |
| `/alerts/run-now` | ✅ | ✅ | ❌ | ✅ | demo trigger |
| `/alerts/outcomes/*` | ✅ | ❌ | ❌ | ✅ (evaluate) | I4C-only evaluate |
| `/alerts/handoffs/*` | =origin/receiving | =origin/receiving | list=❌ | ✅ | see `routing.py` |
| `/reports/...` | =state | =district | ❌ | ✅ | `_report_in_scope` verified |
| `/recovery/recommendations` | ✅ | ✅ | =bank | ✅ | `bank_name` override ignored (verified no-BOLA) |
| `/ledger`, `/ledger/verify` | ✅ | ✅ | ✅ | ✅ | tamper demo gated by flag |
| `/train` | ❌ | ❌ | ❌ | ✅ | I4C-only (verified `bank.hdfc` 403) |
| `/stats`, `/stats/heatmap` | =state | =district | =bank | ✅ | scope-rolled |
| `/mule_graph`, `/risk/...` | =state | =district | =bank | ✅ | scope-rolled |
| `/simulated`, `/simulated/details` | ✅ | ✅ | ❌ | ✅ | demo factory, role-gated |
| `/realtime` `/ws/alerts` | ✅ (token) | ✅ | ✅ | ✅ | WS 4401 w/o valid token (verified) |
| `/ingest/stream/*` | ❌ | ❌ | ❌ | ✅ | I4C-only |

**Identity/authority invariants (verified)**
1. **Authenticated ≠ authorized.** Every data endpoint requires a valid JWT
   (401 for none) and then enforces role AND scope on both read and write.
2. **Scoping is server-side.** Query params (`atm_id`, `bank_name`, `state`) may
   narrow results but the repository *always* intersects with
   `user.role`/`user.scope`; a `bank_name` override for another bank returns 0,
   never the bank's rows (verified on `/recovery`).
3. **Trust boundary = the token.** Because HS256 relies on the shared secret,
   default-secret forgery (FINDING-1) previously bypassed even correct role
   logic. The boot guard now refuses the public default secret.

**After this red-team the three discovered gaps are closed:**
- FINDING-1 (Critical): default JWT secret → boot guard refuses insecure boot.
- FINDING-2 (High): `/withdrawals` bank isolation enforced in the repo.
- FINDING-3 (Medium): out-of-jurisdiction alert write → 403.

**To activate on a live demo:** restart the server from source (see operator
note). Without restart the in-memory process still runs the pre-fix code.
