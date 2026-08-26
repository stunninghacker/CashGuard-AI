"""
Cache the DEMO_MODE "golden path" (fallback plan — DEMO_SCRIPT.md).

Runs the live risk engine + alert list + evidence panels once and writes them
to data/demo_cache/*.json. When the server runs with DEMO_MODE=true, the API
serves these cached payloads — same UI, pre-computed data — so the live
walkthrough survives inference hangs or breakage on stage.

Usage (after generate + train):
    python scripts/cache_demo_mode.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import repositories as repo  # noqa: E402
from backend.config import DEMO_CACHE_DIR  # noqa: E402
from backend.database import SessionLocal  # noqa: E402
from backend.ml.inference import predict_risk  # noqa: E402
from backend.services import build_alert_evidence, resolve_as_of  # noqa: E402


def _jsonable(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    if isinstance(obj, (list, tuple)):
        return [_jsonable(o) for o in obj]
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    return str(obj)


def main() -> None:
    db = SessionLocal()
    try:
        ref = resolve_as_of(db)
        print(f">> Scoring all ATMs as of {ref} ...")
        scores = predict_risk(ref)
        for s in scores:
            s["risk_level"] = "CRITICAL" if s["risk_score"] >= 0.85 else "HIGH" if s["risk_score"] >= 0.7 else "MEDIUM" if s["risk_score"] >= 0.4 else "LOW"
            s["as_of"] = ref.isoformat()

        alerts = repo.list_alerts(db, limit=200)
        alerts_out = []
        evidence = {}
        for a in alerts:
            out = {
                "alert_id": a.alert_id, "created_at": a.created_at.isoformat(),
                "atm_id": a.atm_id, "bank_name": a.bank_name, "city": a.city,
                "district": a.district, "state": a.state,
                "police_station_area": a.police_station_area,
                "risk_score": a.risk_score, "recommended_action": a.recommended_action,
                "status": a.status, "sms_log": a.sms_log, "email_log": a.email_log,
                "dispatch_log": a.dispatch_log,
            }
            alerts_out.append(out)
            evidence[a.alert_id] = _jsonable(build_alert_evidence(db, a))

        DEMO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (DEMO_CACHE_DIR / "risk-scores.json").write_text(json.dumps(scores, indent=1))
        (DEMO_CACHE_DIR / "alerts.json").write_text(json.dumps(alerts_out, indent=1))
        (DEMO_CACHE_DIR / "evidence.json").write_text(json.dumps(evidence, indent=1))
        print(f">> Cached {len(scores)} risk scores, {len(alerts_out)} alerts, {len(evidence)} evidence panels.")
        print(f">> Start the server with DEMO_MODE=true to serve this golden path.")
    finally:
        db.close()


if __name__ == "__main__":
    main()