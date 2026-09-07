# UI / UX Changelog — SIH26184 demo-hardening pass

Traceable against the work-order prompt (Priority 1 → 2 → 3).
Nothing here changes model methodology, metrics, or the honesty/limitations docs.

---

## Priority 1 — Fix the flat-demo risk ✅

| Change | Files | Notes |
|---|---|---|
| **P1.1 Model Status strip** — dashboard strip showing last inference run time, ATMs scored (RBAC-scoped), max/median risk, level counts, and a plain-language calm-day line: *"Calm day — no ATM currently crosses the 70% alert threshold… This is expected behavior, not a failure."* | `backend/services.py` (`get_model_status`, cache `computed_at`), `backend/api/routes/risk.py` (`GET /model/status`, supports `&as_of=` for replay), `frontend/index.html`, `frontend/app.js` (`ModelStatus`) | Read-only over the existing cached scoring path — no model/inference change. In DEMO_MODE it honestly reports `DEMO CACHE` as source. |
| **P1.2 Replay Historical High-Risk Day** — one-click replay using **real historical synthetic data already in the DB** (not the SCRIPTED button): backend ranks days by actual fraud withdrawals in the caller's RBAC scope; the UI picker replays a day by calling the **live model** via the existing `GET /risk-scores?as_of=<end of previous day>`. Features stay strictly backward-looking → genuine out-of-sample replay. | `backend/api/routes/replay.py` (new, DB query only), `backend/api/main.py` (router), `frontend/app.js` (`Replay`), `frontend/index.html` (`#replay-banner`, picker modal) | Replay mode gets its own amber **HISTORICAL REPLAY** banner + strip chip; the SCRIPTED `/simulated/scenario` labeling, banner, and watermark are untouched; the two modes are mutually exclusive. Honest framing everywhere: verified replay of the 2026-09-04 peak returns max risk 69.5% — the UI explicitly says "below the 70% alert threshold, so no alerts would have fired" instead of overclaiming. Toast compares to calm-day max (69.5% vs 18.3%). |
| **P1.3 RBAC scoping on new endpoints** — verified: District (Northsagar) sees 180 ATMs and its own peak days; BANK sees its 127 ATMs with complaint counts zeroed (BANK never sees complaint lists). | `backend/api/routes/replay.py`, `risk.py` | Uses the existing `_scoped_atm_stmt` / `_scoped_complaint_stmt` repo helpers. |

### Pre-existing blockers found & fixed while verifying P1
| Bug | Fix |
|---|---|
| `frontend/app.js` had a **fatal syntax error** (unescaped quotes in the drift renderer) — the entire frontend never loaded. | Rewrote the offending line; `node --check` clean. |
| **WebSocket reconnect pile-up**: both `onclose` and `onerror` scheduled reconnects and the socket never authenticated (no `?token=`), so failed handshakes doubled pending reconnect timers until the page wedged. Also the message shape was wrong (`msg.type` vs server's `{event, payload}`). | Single-path reconnect with a current-socket guard, `?token=` auth, correct `{event:"alert", payload}` parsing. Topbar now shows a real **Connected** state. *(Addresses P2 alert-feed groundwork.)* |
| **SQLite `database is locked`** killed the server mid-demo (every authed request writes an audit event; scheduler + webhook + dashboard overlap). | WAL journal mode, 30 s busy timeout, `synchronous=NORMAL` per connection in `backend/database.py`. Verified live on the running server. |

Verification: `/model/status`, `/replay/high-risk-days`, `/risk-scores?as_of=…` exercised via curl for all four roles; browser end-to-end login → calm-day strip → replay picker → replay banner/chip/stat relabel (screenshot in session log).

---
