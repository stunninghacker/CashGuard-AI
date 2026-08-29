"""
SIMULATED SCENARIO endpoints (Option B / P1.5 demo framing).

Until the forecast-safe (leak-fixed) model produces detectably high-risk next-day
scores, the honest live state shows sparse, low scores for every ATM (max ~0.11)
and NO alerts. A populated alert workflow is therefore intentionally provided as
an EXPLICITLY LABELLED, OPT-IN simulation so judges can exercise the alert ->
dispatch -> SMS/email/bank -> action workflow on a coherent example scenario
(alerts, risk scores, evidence and delivery logs are SCRIPTED, NOT live model
output — stated on every element).

Honesty invariants:
  * Never served automatically. The frontend must explicitly call
    GET /simulated/scenario (turned on by the "Load Simulated Scenario" button).
  * Every response carries "simulated": true and a human-readable disclosure.
  * Risk scores / alerts / evidence / delivery logs are clearly scripted values,
    never presented as output of the live risk engine (which is calibrated and
    honestly reports ~0-0.1 for calm days).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends

from ...security import require_auth

router = APIRouter(prefix="/simulated", tags=["simulated"])

DISCLOSURE = (
    "SIMULATED SCENARIO - NOT LIVE MODEL OUTPUT. The alerts, risk scores, "
    "evidence and SMS/email/dispatch logs here are SCRIPTED for demonstration. "
    "The leak-fixed live risk engine (honest AUC 0.63) reports low risk for "
    "calm days and produced no alerts; this scenario stands in for a cash-out "
    "spree so the alert workflow can be exercised. Risk levels are scenario "
    "values, not predictions."
)

# ---- scripted scenario: 12 ATMs, 4 states/districts, banks incl HDFC ----
# (atm_id, bank, branch, city, district, state, PS area, pin, lat, lng, risk)
_ROWS = [
    # Northex district, state A
    ("ATM-NOR0001", "HDFC Bank", "Northex Branch", "Northex City", "Northex District", "State-A", "Northex Central PS", "244101", 28.70, 77.10, 0.93),
    ("ATM-NOR0002", "HDFC Bank", "Northex Mall", "Northex City", "Northex District", "State-A", "Northex Central PS", "244101", 28.72, 77.12, 0.87),
    ("ATM-NOR0003", "State Bank of India", "Northex Market", "Northex City", "Northex District", "State-A", "Northex Central PS", "244101", 28.69, 77.09, 0.82),
    ("ATM-NOR0004", "Kotak Mahindra Bank", "Northex Road", "Northex City", "Northex District", "State-A", "Northex Central PS", "244101", 28.71, 77.08, 0.71),
    # Eastvale district, state B
    ("ATM-EAS0001", "HDFC Bank", "Eastvale High St", "Eastvale", "Eastvale District", "State-B", "Eastvale PS", "700091", 22.57, 88.36, 0.90),
    ("ATM-EAS0002", "Axis Bank", "Eastvale Stn Rd", "Eastvale", "Eastvale District", "State-B", "Eastvale PS", "700091", 22.58, 88.37, 0.78),
    ("ATM-EAS0003", "ICICI Bank", "Eastvale Plaza", "Eastvale", "Eastvale District", "State-B", "Eastvale PS", "700091", 22.56, 88.35, 0.86),
    # Metro-West district, state C
    ("ATM-MET0001", "Bank of Baroda", "MetroWest Food Crt", "Metro-West", "Metro-West District", "State-C", "MetroWest Megapolis PS", "400001", 19.08, 72.88, 0.89),
    ("ATM-MET0002", "State Bank of India", "MetroWest Centre", "Metro-West", "Metro-West District", "State-C", "MetroWest Megapolis PS", "400001", 19.09, 72.89, 0.80),
    # Greenfield District, state D
    ("ATM-GRE0001", "Punjab National Bank", "Greenfield Campus", "Greenfield District", "Greenfield District", "State-D", "Greenfield Sector-12 PS", "122001", 28.45, 77.03, 0.84),
    ("ATM-GRE0002", "Axis Bank", "Greenfield Tech Park", "Greenfield District", "Greenfield District", "State-D", "Greenfield Sector-12 PS", "122001", 28.46, 77.04, 0.72),
    ("ATM-GRE0003", "Kotak Mahindra Bank", "Greenfield Hub", "Greenfield District", "Greenfield District", "State-D", "Greenfield Sector-12 PS", "122001", 28.44, 77.02, 0.69),
]

_ACTIONS = {
    "dispatch": "Freeze linked mule accounts + dispatch beat officer to ATM",
    "action": "Enable enhanced monitoring + increase cash-in-cassette checks",
    "monitor": "HOLD - watch; no dispatch",
}


def _risk_meta(score: float) -> dict:
    tier = "dispatch" if score >= 0.85 else "action" if score >= 0.7 else "monitor"
    return {"tier": tier, "action": _ACTIONS[tier],
            "emerging": round(min(0.35 + score * 0.5, 0.95), 3),
            "priority": round(min(0.4 * score + 0.35, 0.98), 3)}


def _build_scenario() -> dict:
    now = datetime.utcnow().replace(microsecond=0)
    risk_scores, alerts, evidence = [], [], {}
    # statuses: 8 new (dispatch-tier) for demo, 4 already actioned
    statuses = ["new", "new", "new", "actioned", "new", "new", "new",
                "actioned", "new", "actioned", "new", "actioned"]
    for i, (aid, bank, branch, city, district, state, psa, pin, lat, lng, score) in enumerate(_ROWS):
        meta = _risk_meta(score)
        status = statuses[i]
        created = now - timedelta(hours=(i % 5) + 1, minutes=(i * 7) % 60)
        risk_scores.append({
            "atm_id": aid, "bank_name": bank, "branch_name": branch,
            "city": city, "district": district, "state": state,
            "police_station_area": psa, "pin": pin, "latitude": lat,
            "longitude": lng, "risk_score": score,
            "emerging_risk": meta["emerging"],
            "intervention_priority": meta["priority"],
            "risk_level": "CRITICAL" if score >= 0.85 else "HIGH" if score >= 0.7 else "MEDIUM",
            "simulated": True,
        })
        alert_id = f"ALT-SIM-{aid}-{created.strftime('%Y%m%d%H%M')}"
        sms = f"[SIMULATED] SMS sent to LEA officer + {bank} branch ops: ATM {aid} risk {(score*100):.0f}% - {meta['action']}"
        email = f"[SIMULATED] Email sent to {state} LEA + {bank} fraud desk: {aid} ({branch}, {city}) escalated {meta['tier']} tier"
        dispatch = f"[SIMULATED] I4C dispatch webhook POSTed to local mock inbox for {aid} ({bank} / {city})"
        alerts.append({
            "alert_id": alert_id, "created_at": created.isoformat(),
            "atm_id": aid, "bank_name": bank, "branch_name": branch,
            "city": city, "district": district, "state": state,
            "police_station_area": psa, "risk_score": score,
            "recommended_action": meta["action"],
            "status": status, "tier": meta["tier"],
            "routing_status": "none", "origin_state": None,
            "reobservation_count": (i % 3), "risk_delta_vs_last": None,
            "sms_log": sms, "email_log": email, "dispatch_log": dispatch,
            "simulated": True,
        })
        evidence[alert_id] = {
            "alert_id": alert_id,
            "data_through": now.isoformat(),
            "atms_scored": 900, "atms_total": 900, "scoring_coverage_pct": 100.0,
            "suggested_action": meta["action"],
            "fired_rule": f"scripted scenario tier >= {meta['tier']}",
            "jurisdiction": {"state": state, "district": district, "police_station_area": psa},
            "recommended_recipients": [f"{state} LEA", f"{bank} Fraud Desk", "I4C"],
            "complaint_activity": f"[SIMULATED] 6 linked complaints in {city} in last 24h (scripted scenario - not live complaint data).",
            "withdrawal_activity": f"[SIMULATED] Elevated cash-out: ~180 withdrawals / 24h at {aid} with 14 distinct accounts (scripted).",
            "context_signal": f"[SIMULATED] Counterparty concentration high at {aid}; mule-account linkage consistent with scenario.",
            "recommended_freeze_accounts": [{"account_token": "ACCT-SIM-0001", "recent_withdrawals": 22},
                                             {"account_token": "ACCT-SIM-0007", "recent_withdrawals": 18}],
            "recommended_actions": [
                {"step": 1, "action": f"Notify {bank} to freeze linked accounts", "owner": f"{bank} Fraud Desk"},
                {"step": 2, "action": f"Dispatch beat officer to {city} / {psa}", "owner": f"{state} LEA"},
                {"step": 3, "action": "Prepare victim-notification outreach", "owner": "I4C"},
            ],
            "uncertainty": {"confidence": "MEDIUM", "evidence_strength": "HIGH",
                            "data_freshness_hours": 2, "model_version": "forecast-safe-0.63",
                            "prediction_horizon_hours": 24, "synthetic_evaluation": True,
                            "insufficient_evidence": True},
            "counterfactual_whatif": {"current_risk": score,
                                      "risk_without_complaint_surge": round(max(score - 0.2, 0.05), 3),
                                      "delta": round(min(0.2, score), 3),
                                      "interpretation": "[SIMULATED] If complaint-surge signals were absent the scripted tier would fall below dispatch; shown to illustrate sensitivity, not a live backtest."},
            "evidence_graph": [
                {"signal": f"Cash-out surge at {aid}", "value": "180 wd / 24h",
                 "direction": "up", "source_type": "withdrawal", "observed_or_synthetic": "scripted"},
                {"signal": f"Linked complaints {city}", "value": "6 / 24h",
                 "direction": "up", "source_type": "complaint", "observed_or_synthetic": "scripted"},
            ],
            "feature_contributions": [
                {"feature": "counterparty_count_24h", "global_importance": "high", "value": 14, "percentile": "p98"},
                {"feature": "withdrawals_24h", "global_importance": "med", "value": 180, "percentile": "p95"},
            ],
            "per_instance_shap": [
                {"feature": "counterparty_count_24h", "value": 14, "shap": 0.31},
                {"feature": "withdrawals_24h", "value": 180, "shap": 0.22},
            ],
            "explainability_note": "SCRIPTED scenario attribution - not live SHAP. Shows the evidence-graph UX only.",
        }

    stats = {
        "generated_at": now.isoformat(),
        "total_complaints": 4820, "complaints_24h": 24, "complaints_7d": 171,
        "total_withdrawals": 214000, "fraud_withdrawals_7d": 16,
        "total_atms": 900, "high_risk_atms": 12,
        "alerts_total": 12, "alerts_new": 8, "alerts_actioned": 4,
        "complaints_by_city_24h": {"Northex City": 9, "Eastvale": 7, "Metro-West": 5, "Greenfield District": 3},
        "complaints_by_city_7d": {"Northex City": 52, "Eastvale": 49, "Metro-West": 41, "Greenfield District": 29},
        "complaints_by_type_24h": {"upi_fraud": 11, "phishing": 7, "investment_fraud": 4, "job_fraud": 2},
        "high_risk_atms_by_city": {"Northex City": 4, "Eastvale": 3, "Metro-West": 2, "Greenfield District": 3},
        "hotspots": sorted(risk_scores, key=lambda s: s["risk_score"], reverse=True)[:20],
    }
    return {
        "simulated": True,
        "scenario": "Scripted cash-out spree across 4 states (Northex / Eastvale / Metro-West / Greenfield)",
        "disclosure": DISCLOSURE,
        "as_of": now.isoformat(),
        "risk_scores": risk_scores,
        "alerts": alerts,
        "evidence": evidence,
        "stats": stats,
    }


_SCENARIO = _build_scenario()


@router.get("/scenario")
def scenario(user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN"))):
    """Explicitly-requested scripted scenario (opt-in only; see module doc)."""
    return _SCENARIO
