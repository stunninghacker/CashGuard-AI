"""Security regression tests — every vulnerability found across all passes.

Run: python scripts/test_security_regression.py
(requires the server on 127.0.0.1:8000, ALLOW_TAMPER_DEMO=true)
Exit code 0 = all pass; 1 = failure.
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx

B = "http://127.0.0.1:8000"
FAILURES = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name} {detail}")
    if not cond:
        FAILURES.append(name)


def main():
    c = httpx.Client(timeout=60)

    def tok(u, pw):
        r = c.post(f"{B}/auth/login", json={"username": u, "password": pw})
        return r.json()["access_token"] if r.status_code == 200 else None

    i4c = tok("i4c.admin", "I4cAdmin!1")
    dist = tok("officer.district1", "District1!1")
    bank = tok("bank.hdfc", "HdfcBank!1")
    h = {"Authorization": f"Bearer {i4c}"}
    check("login_i4c", i4c is not None)

    # 1. anonymous access
    check("anon_401", c.get(f"{B}/risk-scores?limit=5").status_code == 401)

    # 2. JWT tamper
    tampered = i4c[:-4] + ("AAAA" if i4c[-4:] != "AAAA" else "BBBB")
    check("jwt_tamper", c.get(f"{B}/risk-scores?limit=5", headers={"Authorization": f"Bearer {tampered}"}).status_code == 401)

    # 3. expired token (forged with the dev secret — the same secret the app uses)
    from jose import jwt as pyjwt
    from backend.config import JWT_SECRET, JWT_ALGORITHM

    expired = pyjwt.encode({"sub": "u-i4c", "role": "I4C_ADMIN", "scope": "national", "type": "access",
                            "exp": datetime.now(timezone.utc) - timedelta(minutes=5)}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    check("expired_token", c.get(f"{B}/risk-scores?limit=5", headers={"Authorization": f"Bearer {expired}"}).status_code == 401)

    # 4. forged role (bank-signed I4C claim) — must NOT escalate
    forged = pyjwt.encode({"sub": "u-bank", "role": "I4C_ADMIN", "scope": "HDFC Bank", "type": "access",
                           "exp": datetime.now(timezone.utc) + timedelta(minutes=30)}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    check("forged_role_train", c.post(f"{B}/train", headers={"Authorization": f"Bearer {forged}"}).status_code == 403)

    # 5. WS without token
    import websockets

    async def ws_no_token():
        try:
            async with websockets.connect("ws://127.0.0.1:8000/ws/alerts") as ws:
                await ws.recv()
                return "open"
        except Exception:
            return "rejected"

    check("ws_no_token", asyncio.run(ws_no_token()) == "rejected")

    # 6. row-level RBAC (list level)
    rs = c.get(f"{B}/risk-scores?limit=2000", headers={"Authorization": f"Bearer {dist}"}).json()
    check("rbac_district", {r["city"] for r in rs} == {"Northsagar"})
    rsb = c.get(f"{B}/risk-scores?limit=2000", headers={"Authorization": f"Bearer {bank}"}).json()
    check("rbac_bank", {r["bank_name"] for r in rsb} == {"HDFC Bank"})

    # 7. IDOR: single-alert reads (regression for the found vulnerability)
    alerts = c.get(f"{B}/alerts?limit=500", headers=h).json()
    foreign = [a for a in alerts if a.get("city") != "Northsagar"]
    if foreign:
        aid = foreign[0]["alert_id"]
        r1 = c.get(f"{B}/alerts/{aid}", headers={"Authorization": f"Bearer {dist}"})
        r2 = c.get(f"{B}/alerts/{aid}/evidence", headers={"Authorization": f"Bearer {dist}"})
        check("idor_foreign_alert", r1.status_code in (403, 404) and r2.status_code in (403, 404))
    own = [a for a in alerts if a.get("city") == "Northsagar"]
    if own:
        r3 = c.get(f"{B}/alerts/{own[0]['alert_id']}", headers={"Authorization": f"Bearer {dist}"})
        check("idor_positive_control", r3.status_code == 200)

    # 8. report scoping (regression for the found vulnerability)
    sit = c.post(f"{B}/reports/situational", headers=h)
    if sit.status_code == 200:
        rid = sit.json()["report_id"]
        check("report_situational_scoped", c.get(f"{B}/reports/{rid}", headers={"Authorization": f"Bearer {dist}"}).status_code == 404)

    # 9. path traversal
    check("path_traversal", c.get(f"{B}/reports/..%2F..%2Fconfig.py", headers=h).status_code == 404)

    # 10. privilege: district cannot train
    check("train_role", c.post(f"{B}/train", headers={"Authorization": f"Bearer {dist}"}).status_code == 403)

    # 11. demo-mode is not a privilege escalation path: DEMO_MODE serves cache but auth still applies
    check("demo_auth_still_required", c.get(f"{B}/alerts?limit=5").status_code == 401)

    print()
    if FAILURES:
        print(f"REGRESSION FAILURES: {FAILURES}")
        sys.exit(1)
    print("ALL SECURITY REGRESSION TESTS PASS")


if __name__ == "__main__":
    main()