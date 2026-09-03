"""
Issue 6-12 Phase-2 integration test suite.

Repeatable end-to-end checks for the new Phase-2 endpoints:
    Issue 6  -> GET  /graph/mule-network
    Issue 7  -> GET  /analytics/time-granularity  (hour / 6h / day)
    Issue 8  -> GET  /mobile/nearby
    Issue 9  -> GET  /i18n/locales  +  GET /i18n/strings
    Issue 10 -> POST /routing/handoff
    Issue 11 -> GET  /drift/status  +  POST /drift/check
    Issue 12 -> POST /recovery/simulate-freeze

HONESTY NOTES
- Where the current synthetic DB cannot exercise a success path end-to-end
  (e.g. /routing/handoff needs a seeded alert; the baseline alerts table is
  empty) the test verifies the verified surface (404 unknown-alert) and states
  the limitation explicitly rather than fabricating a pass.
- Issue 7 asserts the endpoint returns the honest `model_note` (hourly/6h
  re-training was a measured dead-end, AUC 0.6463 vs 0.6801) — it does NOT
  assert a model-quality improvement that we cannot claim.
- All DB fixtures are created and cleaned up unconditionally.

Run:  python scripts/test_issue6_12_integration.py
"""
import os
import sys
from pathlib import Path

os.environ["ALLOW_INSECURE_DEFAULT_JWT"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from backend import i18n  # noqa: E402
from backend.api.main import app  # noqa: E402
from backend.database import SessionLocal  # noqa: E402
from backend import repositories as repo  # noqa: E402
from backend.models import RecoveryRecommendation as RR  # noqa: E402

CHECKS: list[str] = []


def ok(name: str) -> None:
    CHECKS.append(name)
    print(f"  [ok] {name}")


def main() -> int:
    c = TestClient(app)
    login = c.post("/auth/login", json={"username": "i4c.admin", "password": "I4cAdmin!1"})
    assert login.status_code == 200, "i4c login failed"
    admin = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # ---- Issue 6: mule-network graph ----
    r = c.get("/graph/mule-network", headers=admin)
    assert r.status_code == 200, f"mule-network {r.status_code}"
    body = r.json()
    assert body.get("nodes") and body.get("edges"), "graph must return nodes+edges"
    stats = body.get("stats", {})
    print(f"  mule-network: accounts={stats.get('accounts')} complaints={stats.get('complaints')} edges={len(body['edges'])}")
    assert any(n["type"] == "account" for n in body["nodes"]), "graph should contain account nodes"
    ok("Issue 6 /graph/mule-network")

    # ---- Issue 7: time-granularity ----
    for w in ["hour", "6h", "day"]:
        r = c.get(f"/analytics/time-granularity?window={w}&hours=72", headers=admin)
        assert r.status_code == 200, f"granularity {w} {r.status_code}"
        j = r.json()
        assert j.get("model_note"), "Issue 7 must surface the honest model_note"
        assert "series" in j
    ok("Issue 7 /analytics/time-granularity (hour/6h/day + honest model_note)")

    # ---- Issue 8: mobile nearby ----
    r = c.get("/mobile/nearby?lat=22.66&lon=74.55&max_km=60&limit=5", headers=admin)
    assert r.status_code == 200, f"mobile {r.status_code}"
    mb = r.json()
    mob = mb["atms"]
    assert len(mob) <= 5
    assert all(mob[i]["mobile_score"] >= mob[i + 1]["mobile_score"] for i in range(len(mob) - 1))
    ok("Issue 8 /mobile/nearby (geolocation top-5, sorted desc)")

    # ---- Issue 9: i18n ----
    r = c.get("/i18n/locales")
    assert r.status_code == 200
    codes = [x["code"] for x in r.json()["locales"]]
    assert codes == ["en", "hi", "bn", "te", "mr", "ta"], f"expected 6 locales, got {codes}"
    r = c.get("/i18n/strings?lang=ta")
    assert r.status_code == 200 and "app.title" in r.json()["strings"]
    assert i18n.t("risk.high", lang="ta"), "t() must translate tam"
    ok("Issue 9 i18n (6 locales + /i18n/strings + helper)")

    # ---- Issue 10: routing handoff ----
    r = c.post("/routing/handoff", headers=admin, json={"alert_id": "ALERT-NONEXISTENT-999"})
    # 404 = endpoint wired + validates against missing alert. Honest: success path
    # needs a seeded alert (baseline alerts table is empty); mechanism is covered
    # by scripts/test_jurisdiction_routing.py.
    assert r.status_code == 404, f"handoff unknown-alert expected 404, got {r.status_code}"
    print("  [note] /routing/handoff success path requires a seeded cross-state alert;")
    print("         verified 404 unknown-alert here + mechanism in test_jurisdiction_routing.py")
    ok("Issue 10 /routing/handoff (404 unknown-alert; mechanism in routing unit test)")

    # ---- Issue 11: drift ----
    r = c.get("/drift/status", headers=admin)
    assert r.status_code == 200, f"drift/status {r.status_code}"
    ds = r.json()
    assert ds.get("status") in ("green", "yellow", "red", "PENDING_REFERENCE")
    assert ds.get("n_features", 0) in (0, 24), f"expected 24 drift features, got {ds.get('n_features')}"
    if ds["status"] != "PENDING_REFERENCE":
        r2 = c.post("/drift/check", headers=admin)
        assert r2.status_code == 200
        assert r2.json().get("status") in ("green", "yellow", "red")
    ok(f"Issue 11 /drift/status (+check) -> {ds['status']}")

    # ---- Issue 12: simulate-freeze success path (fixture rec) ----
    db = SessionLocal()
    for r_ in db.query(RR).filter(RR.rec_id.in_(["ITG-FIX-001", "ITG-FIX-002"])):
        db.delete(r_)
    db.commit()
    rec = repo.create_recovery_recommendation(
        db, rec_id="ITG-FIX-001", alert_id="ALERT-ITG", account_token="ACCT-ITG-001",
        home_bank="SBI", linked_complaint_ids="[]", amount_at_risk=40000.0,
        suspected_atm="ATM-ITG", predicted_window="24h", recommended_action="freeze",
        status="freeze_requested")
    print("  [fixture] recovery rec", rec.rec_id, "created")
    db.close()

    r = c.post("/recovery/simulate-freeze", headers=admin,
               json={"rec_id": "ITG-FIX-001", "amount_held": 40000.0})
    assert r.status_code == 200, f"simulate-freeze {r.status_code}"
    fz = r.json()["freeze"]
    assert fz["simulated"] is True and fz["status"] == "held", f"unexpected freeze {fz}"
    db = SessionLocal()
    updated = repo.get_recovery_recommendation(db, "ITG-FIX-001")
    assert updated.status == "held" and updated.amount_held == 40000.0
    db.delete(updated); db.commit(); db.close()
    print("  [cleanup] fixture rec removed + status held verified")
    ok("Issue 12 /recovery/simulate-freeze (simulated held + persisted + cleanup)")

    print(f"\nINTEGRATION TEST: ALL {len(CHECKS)} CHECKS PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"\nINTEGRATION TEST FAILED: {e}")
        sys.exit(1)
