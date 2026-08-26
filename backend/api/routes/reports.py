"""
Intelligence reports (Phase 4 — deliverable c).

POST /reports/hotspot/{alert_id}   -> generate + store per-hotspot report (PDF + JSON)
POST /reports/situational          -> I4C daily/shift situational report (PDF + JSON)
GET  /reports/{report_id}          -> JSON payload
GET  /reports/{report_id}/download -> PDF download
GET  /reports/city?city=&format=   -> city brief (JSON|HTML) — retained from earlier phase

Every generated report is hashed into the tamper-evident ledger.
"""
from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from ... import repositories as repo, services
from ...config import ARTIFACT_DIR
from ...database import get_db
from ...security import require_auth

router = APIRouter(prefix="/reports", tags=["reports"])
PDF_DIR = ARTIFACT_DIR / "reports"
PDF_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/hotspot/{alert_id}")
def hotspot_report(alert_id: str, user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN")), db: Session = Depends(get_db)):
    alert = repo.get_alert(db, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    report = services.build_hotspot_report(db, alert, user)
    pdf = services.generate_pdf(report, PDF_DIR)
    fingerprint = services.report_audit_ref(report)
    stored = repo.create_report(db, report["report_id"], report["report_type"], report["title"],
                                json.dumps(report, default=str), str(pdf), fingerprint)
    repo.append_ledger(db, actor=f"{user.user_id} ({user.role})", event_type="report_generated",
                       entity_id=report["report_id"], payload_hash=fingerprint)
    return {"report_id": stored.report_id, "pdf": str(pdf), "ledger_hash": fingerprint}


@router.post("/situational")
def situational_report(user=Depends(require_auth("I4C_ADMIN")), db: Session = Depends(get_db)):
    report = services.build_situational_report(db, user)
    pdf = services.generate_pdf(report, PDF_DIR)
    fingerprint = services.report_audit_ref(report)
    stored = repo.create_report(db, report["report_id"], report["report_type"], report["title"],
                                json.dumps(report, default=str), str(pdf), fingerprint)
    repo.append_ledger(db, actor=f"{user.user_id} ({user.role})", event_type="report_generated",
                       entity_id=report["report_id"], payload_hash=fingerprint)
    return {"report_id": stored.report_id, "pdf": str(pdf), "ledger_hash": fingerprint}


@router.get("/{report_id}")
def get_report(report_id: str, user=Depends(require_auth()), db: Session = Depends(get_db)):
    report = repo.get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return json.loads(report.payload)


@router.get("/{report_id}/download")
def download_report(report_id: str, user=Depends(require_auth()), db: Session = Depends(get_db)):
    report = repo.get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    path = Path(report.pdf_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF file missing")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


# ------------------------------ retained: city brief -----------------------------
@router.get("/city")
def city_report(
    city: str,
    format: str = Query(default="json", pattern="^(json|html)$"),
    as_of: str | None = None,
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    ref = services.resolve_as_of(db, as_of)
    report = services.build_city_report(db, city, as_of=ref)
    fingerprint = services.report_audit_ref(report)
    repo.append_ledger(db, actor=f"{user.user_id} ({user.role})", event_type="report_generated",
                       entity_id=report["report_id"], payload_hash=fingerprint)
    if format == "html":
        return HTMLResponse(content=_render_html(report, fingerprint))
    report["audit_fingerprint"] = fingerprint
    return report


def _render_html(report: dict, fingerprint: str) -> str:
    rows = "".join(
        f"<tr><td>{i+1}</td><td>{html.escape(h['atm_id'])}</td><td>{html.escape(h['bank_name'])} / "
        f"{html.escape(h['branch_name'])}</td><td>{html.escape(h['police_station_area'])}</td>"
        f"<td>{h['risk_score']*100:.1f}%</td><td>{h['risk_level']}</td></tr>"
        for i, h in enumerate(report["hotspots"])
    )
    alert_rows = "".join(
        f"<tr><td>{html.escape(a['alert_id'])}</td><td>{html.escape(a['atm_id'])}</td>"
        f"<td>{a['risk_score']*100:.1f}%</td><td>{html.escape(a['recommended_action'])}</td>"
        f"<td>{a['status']}</td></tr>"
        for a in report["open_alerts"]
    ) or "<tr><td colspan=5>No open alerts.</td></tr>"
    types24 = " · ".join(f"{html.escape(t)}: {n}" for t, n in report["complaints_by_type_24h"].items()) or "none"

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Intelligence Brief — {html.escape(report['city'])}</title>
<style>
 body {{ font-family: 'Segoe UI', sans-serif; margin: 32px; color: #111c31; }}
 h1 {{ font-size: 22px; }} h2 {{ font-size: 15px; margin-top: 22px; border-bottom: 2px solid #111c31; }}
 table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 8px; }}
 th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; }}
 th {{ background: #eef2f9; }}
 .meta {{ color: #555; font-size: 12px; }}
 .warn {{ background: #fff7e0; border: 1px solid #eab308; padding: 10px; font-size: 12px; margin-top: 18px; }}
 @media print {{ body {{ margin: 12px; }} }}
</style></head><body>
<h1>Intelligence Brief — {html.escape(report['city'])} <span style="font-weight:normal;font-size:12px">(fictional location)</span></h1>
<p class="meta">Report {html.escape(report['report_id'])} · Generated {report['generated_at']} ·
Based on data through <b>{report['data_through']}</b> · Jurisdiction: {html.escape(report['jurisdiction']['state'])}, {html.escape(report['jurisdiction']['district'])}</p>

<h2>1. Complaint Overview</h2>
<p>Last 24h: <b>{report['complaints_24h']}</b> complaints · Last 7d: <b>{report['complaints_7d']}</b></p>
<p>By category (24h): {types24}</p>

<h2>2. Predicted Withdrawal Hotspots (next 24h)</h2>
<table><tr><th>#</th><th>ATM</th><th>Bank / Branch</th><th>Police Station Area</th><th>Risk</th><th>Level</th></tr>{rows}</table>
<p class="meta">{report['atms_scored']} ATMs scored · {report['high_risk_atms']} above the 0.70 alert threshold</p>

<h2>3. Open Alerts &amp; Recommended Actions</h2>
<table><tr><th>Alert</th><th>ATM</th><th>Risk</th><th>Recommended action</th><th>Status</th></tr>{alert_rows}</table>

<h2>4. Recommended Recipients</h2>
<p>Local Police ({html.escape(report['city'])}) · Bank branch managers (flagged ATMs) · I4C coordination node (via dispatch webhook)</p>

<div class="warn"><b>Methodology &amp; honesty notice:</b> {html.escape(report['methodology_note'])}
<br/><b>Audit fingerprint (SHA-256, recorded on the tamper-evident chain):</b> {fingerprint}
<br/><b>UI policy:</b> {html.escape(report['ui_policy'])}</div>
</body></html>"""


# keep module import light (datetime unused at runtime but part of API surface)
_ = datetime