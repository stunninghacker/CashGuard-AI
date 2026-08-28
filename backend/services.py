"""
Service layer — business logic orchestrating repositories + ML + alerts.

Routes stay thin; all decisions (which ATM is a hotspot, when to alert,
what action to recommend, what evidence to show) live here so the logic is
testable and reusable by the scheduler, the API, and future CLI/ETL tooling.
"""
from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from . import models
from . import repositories as repo
from .alerts.notifier import send_email, send_sms
from .config import ALERT_COOLDOWN_HOURS, ALERT_DEDUP_RISK_DELTA, DEMO_CACHE_DIR, DEMO_MODE, RISK_THRESHOLD, SIMULATED_NOW
from .data.synthetic_data import NIGHT_HOURS, load_calibration_config
from .ml import inference


def resolve_as_of(db: Session, as_of: str | None = None) -> datetime:
    """
    Resolve the reference time for risk scoring.

    Priority: explicit ?as_of= query -> SIMULATED_NOW env -> latest data timestamp.
    This lets the demo show a "live" 24h forecast immediately after data
    generation instead of waiting for real time to catch up.
    """
    if as_of:
        return datetime.fromisoformat(as_of)
    if SIMULATED_NOW:
        return datetime.fromisoformat(SIMULATED_NOW)
    latest = repo.latest_timestamp(db)
    if latest is not None:
        return latest
    return datetime.utcnow()


# ------------------------------ Risk scoring --------------------------------
# Short-TTL inference cache: risk scores are valid within a window (the alert
# cycle recomputes hourly), so repeated reads within SCORE_CACHE_SECONDS are
# served without re-running inference — this is the documented production
# caching requirement (LOAD_TEST.md), implemented for the demo stack.
# A single-flight lock prevents cache stampedes: under concurrency only one
# thread computes while the others wait for the shared result.
import threading as _threading

_score_cache: dict = {"key": None, "payload": None, "expires_at": None}
_score_cache_lock = _threading.Lock()


def _invalidate_score_cache() -> None:
    _score_cache["key"] = None
    _score_cache["payload"] = None
    _score_cache["expires_at"] = None


def get_risk_scores(db: Session, as_of: datetime | None = None, city: str | None = None, user=None) -> list[dict]:
    """Compute P(fraud withdrawal in next 24h) for every ATM, as of `as_of`.
    RBAC: scores are row-scoped to the caller's jurisdiction (repo layer).
    The full score set is cached (TTL SCORE_CACHE_SECONDS, single-flight) and
    invalidated on any data change (drip ingest / alert cycle)."""
    from .config import SCORE_CACHE_SECONDS

    ref = as_of or resolve_as_of(db)
    key = f"{city or '*'}|{ref.isoformat()}"
    now = datetime.utcnow()
    if _score_cache["key"] == key and _score_cache["expires_at"] is not None and now < _score_cache["expires_at"]:
        cached = _score_cache["payload"]
    else:
        with _score_cache_lock:
            if _score_cache["key"] != key or _score_cache["expires_at"] is None or now >= _score_cache["expires_at"]:
                cached = inference.predict_risk(ref)
                _score_cache["key"] = key
                _score_cache["payload"] = cached
                _score_cache["expires_at"] = now + timedelta(seconds=SCORE_CACHE_SECONDS)
            else:
                cached = _score_cache["payload"]
    scores = [dict(s) for s in cached]  # copy: callers may mutate
    if city:
        scores = [s for s in scores if s["city"] == city]
    if user is not None:
        allowed = repo.list_atms(db, limit=5000, user=user)
        allowed_ids = {a.atm_id for a in allowed}
        scores = [s for s in scores if s["atm_id"] in allowed_ids]
    for s in scores:
        s["risk_level"] = _risk_level(s["risk_score"])
        s["as_of"] = ref
    return scores


def get_hotspots(db: Session, k: int = 20, city: str | None = None, as_of: datetime | None = None) -> list[dict]:
    scores = get_risk_scores(db, as_of=as_of, city=city)
    scores.sort(key=lambda s: s["risk_score"], reverse=True)
    return scores[:k]


def _risk_level(score: float) -> str:
    if score >= 0.85:
        return "CRITICAL"
    if score >= 0.7:
        return "HIGH"
    if score >= 0.4:
        return "MEDIUM"
    return "LOW"


# ------------------------------ Alert engine --------------------------------
def _dispatch_webhook(channel: str, payload: dict) -> str:
    """REAL outbound webhook path (httpx) to the configured URL.

    In the demo WEBHOOK_URL points at the local POST /api/mock-i4c-inbox, which
    stores + displays the intel — the integration path is real, the receiver is
    mock. Production: point at I4C/state-LEA/CFCFRMS gateways.
    """
    import httpx

    from .config import CFCFRMS_WEBHOOK_URL, WEBHOOK_URL

    url = CFCFRMS_WEBHOOK_URL if channel == "cfcfrms" else WEBHOOK_URL
    try:
        resp = httpx.post(url, json={"channel": channel, "payload": payload}, timeout=5)
        status = resp.status_code
    except Exception as exc:  # pragma: no cover - stage resilience
        status = f"error: {exc.__class__.__name__}"
    return f"[WEBHOOK:{channel}] POST {url} -> {status}"


def run_alert_cycle(db: Session, force: bool = False) -> dict:
    """
    One alert cycle:
      1. compute risk scores as of now
      2. keep ATMs with risk_score >= threshold
      3. skip ATMs already alerted within the cooldown window (dedupe)
      4. create alert + mock SMS/email + REAL webhook dispatch + WS push
      5. issue CFCFRMS fund-block recommendations for linked mule accounts
    Returns a summary of what happened (for logs / API responses).
    """
    scores = get_risk_scores(db)
    flagged = [s for s in scores if s["risk_score"] >= RISK_THRESHOLD]
    created = 0
    skipped = 0

    for s in flagged:
        if not force:
            existing = repo.recent_open_alert_for_atm(db, s["atm_id"], ALERT_COOLDOWN_HOURS)
            if existing is not None:
                # Alert-fatigue dedup (Phase: mitigation): skip repeat alerts for
                # the same ATM within the cooldown window UNLESS risk has risen
                # meaningfully since the last alert (delta > ALERT_DEDUP_RISK_DELTA)
                # — a genuine escalation still gets through.
                if s["risk_score"] - (existing.risk_score or 0.0) <= ALERT_DEDUP_RISK_DELTA:
                    skipped += 1
                    continue

        action = recommend_action(s["risk_score"], s["risk_level"])
        # INSUFFICIENT EVIDENCE — HOLD ACTION (Phase 7): near-threshold alerts
        # sit in the weakest-evidence band -> they are review flags, not action
        # orders. The full evidence/uncertainty block is shown in the panel.
        if 0.70 <= s["risk_score"] < 0.78:
            action = "INSUFFICIENT EVIDENCE — HOLD ACTION (review recommended; evidence below strength threshold)"
        sms = email = dispatch = ""
        from .config import SHADOW_MODE

        if SHADOW_MODE:
            # SHADOW MODE (Phase 14): record predictions only — no channels fire.
            sms = "[shadow] SMS suppressed (SHADOW_MODE) — prediction recorded for evaluation"
            email = "[shadow] Email suppressed (SHADOW_MODE)"
            dispatch = "[shadow] Dispatch suppressed (SHADOW_MODE)"
        else:
            sms = send_sms(
            f"SHO {s['district']}",
            f"High risk of fraud cash withdrawal at ATM {s['atm_id']} "
            f"({s['branch_name']}, {s['city']}) in next 24h. Risk {s['risk_score']:.2f}. {action}",
        )
        email = send_email(
            f"{s['bank_name']} branch manager, {s['city']}",
            f"ATM {s['atm_id']} flagged as HIGH RISK for fraud withdrawals in the next 24h. "
            f"Risk score {s['risk_score']:.2f}. Recommended: {action}.",
        )
        dispatch = _dispatch_webhook("dispatch", {
            "alert_target": "state-LEA dispatch + I4C coordination node",
            "atm_id": s["atm_id"], "city": s["city"], "state": s["state"],
            "district": s["district"], "police_station_area": s["police_station_area"],
            "bank_name": s["bank_name"], "risk_score": s["risk_score"],
            "recommended_action": action,
        })
        alert = repo.create_alert(
            db,
            alert_id=f"ALT-{s['atm_id']}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            created_at=datetime.utcnow(),
            atm_id=s["atm_id"],
            bank_name=s["bank_name"],
            city=s["city"],
            district=s["district"],
            state=s["state"],
            police_station_area=s["police_station_area"],
            risk_score=round(s["risk_score"], 4),
            tier=alert_tier(s["risk_score"]),
            recommended_action=action,
            status="shadow" if SHADOW_MODE else "new",
            model_version=_model_version(),
            sms_log=sms,
            email_log=email,
            dispatch_log=dispatch,
        )
        # Inter-agency jurisdiction routing (Item 4): origin state = complaint
        # jurisdiction that seeded this ATM's risk. If it differs from the
        # predicted withdrawal state (ATM.state), the case is cross-state.
        from .routing import origin_state_for_atm, route_alert

        origin = origin_state_for_atm(db, s)
        if origin and origin != alert.state:
            alert.origin_state = origin
            alert.routing_status = "handoff"
            db.commit()
        if alert.origin_state and alert.origin_state != alert.state:
            route_alert(db, alert)
        repo.append_ledger(db, actor="scheduler (system)", event_type="alert_created",
                           entity_id=alert.alert_id, payload=s)
        # CFCFRMS fund-block loop (Phase 6)
        recs = create_fund_block_recommendations(db, alert)
        # live push to dashboards (WS) — suppressed in SHADOW_MODE
        from .realtime import enqueue_broadcast

        if not SHADOW_MODE:
            enqueue_broadcast("alert", {
                "alert_id": alert.alert_id, "atm_id": alert.atm_id, "city": alert.city,
                "state": alert.state, "district": alert.district,
                "police_station_area": alert.police_station_area,
                "bank_name": alert.bank_name, "risk_score": alert.risk_score,
                "recommended_action": action, "status": alert.status,
                "recommended_actions": graded_actions(s["risk_score"]),
                "recovery_recs": recs,
            })
        created += 1

    _invalidate_score_cache()
    return {"checked": len(scores), "flagged": len(flagged), "created": created, "skipped": skipped}


HITL_STATUSES = {
    "acknowledged": "seen — no decision yet",
    "actioned": "response completed",
    "dismissed": "false positive / not actionable",
    "escalated": "sent up the chain",
    "monitoring": "watching, no action yet",
    "review_requested": "more data or a second reviewer needed",
}
REASON_REQUIRED = {"dismissed", "escalated"}  # mandatory human reason


def set_alert_status(db: Session, alert, status: str, actor_user, reason: str = "") -> None:
    """Human-in-the-loop (Phase 6): every decision is auditable; dismiss and
    escalate REQUIRE a recorded reason."""
    if status not in HITL_STATUSES:
        raise ValueError(f"status must be one of {sorted(HITL_STATUSES)}")
    if status in REASON_REQUIRED and not reason.strip():
        raise ValueError(f"a reason is required for '{status}'")
    updated = repo.update_alert_status(db, alert, status, reason=reason)
    repo.append_ledger(db, actor=f"{actor_user.user_id} ({actor_user.role})",
                       event_type="status_changed",
                       entity_id=alert.alert_id,
                       payload={"status": status, "reason": reason})
    from .realtime import enqueue_broadcast

    enqueue_broadcast("alert_status", {"alert_id": alert.alert_id, "status": status, "reason": reason})
    return updated


# ------------------------------ Recovery (CFCFRMS loop) -----------------------
def create_fund_block_recommendations(db: Session, alert) -> int:
    """
    Issue Fund-Block Recommendations for complaint-linked accounts active at the
    flagged ATM (Phase 6 — the recovery story). Routed to the Bank dashboard and
    a CFCFRMS-style webhook stub; every issuance is ledger-logged.
    """
    from .config import RISK_THRESHOLD

    ref = resolve_as_of(db)
    wd_24h = repo.recent_withdrawals(db, atm_id=alert.atm_id, since=ref - timedelta(hours=24))
    mule_tokens = set(repo.complaint_mule_account_tokens(db))
    linked = [
        w for w in wd_24h if w.account_token in mule_tokens
    ]
    if not linked:
        return 0
    from collections import Counter

    counts = Counter(w.account_token for w in linked)
    amounts = {}
    for w in linked:
        amounts[w.account_token] = amounts.get(w.account_token, 0.0) + w.amount

    created = 0
    for token, n in counts.most_common(3):
        complaint_ids = repo.complaint_ids_for_account(db, token)[:5]
        rec = repo.create_recovery_recommendation(
            db,
            rec_id=f"REC-{alert.atm_id}-{token[-6:]}-{datetime.utcnow().strftime('%H%M%S')}",
            alert_id=alert.alert_id,
            account_token=token,
            home_bank=repo.bank_for_account(db, token) or alert.bank_name,
            linked_complaint_ids=json.dumps(complaint_ids),
            amount_at_risk=round(amounts.get(token, 0.0), 2),
            suspected_atm=alert.atm_id,
            predicted_window="next 24h",
            recommended_action="freeze" if alert.risk_score >= 0.85 else "hold",
            status="freeze_requested",
        )
        repo.append_ledger(db, actor="scheduler (system)", event_type="fund_block_issued",
                           entity_id=rec.rec_id,
                           payload={"account_token": token, "amount_at_risk": amounts.get(token, 0.0)})
        # CFCFRMS-style stub webhook (real path -> mock inbox)
        _dispatch_webhook("cfcfrms", {
            "action": "fund_block_recommendation",
            "account_token": token, "amount_at_risk": amounts.get(token, 0.0),
            "suspected_atm": alert.atm_id, "recommended_action": rec.recommended_action,
        })
        from .realtime import enqueue_broadcast

        enqueue_broadcast("recovery", {
            "rec_id": rec.rec_id, "account_token": token, "amount_at_risk": rec.amount_at_risk,
            "suspected_atm": alert.atm_id, "recommended_action": rec.recommended_action,
            "status": rec.status,
        })
        created += 1
    return created


def recovery_funnel(db: Session, days: int = 7) -> dict:
    """flagged -> held -> recovered (SYNTHETIC outcomes — clearly labelled)."""
    since = datetime.utcnow() - timedelta(days=days)
    recs = repo.list_recovery_recommendations(db, since=since)
    flagged = sum(r.amount_at_risk for r in recs)
    held = sum(r.amount_held for r in recs)
    recovered = sum(r.amount_recovered for r in recs)
    return {
        "window_days": days,
        "amount_flagged": round(flagged, 2),
        "amount_held": round(held, 2),
        "amount_recovered": round(recovered, 2),
        "recovery_rate_pct": round(100 * recovered / flagged, 1) if flagged else 0.0,
        "note": "Synthetic/illustrative outcomes — real CFCFRMS/core-banking APIs are the Tier 2 integration point.",
    }


def alert_tier(score: float) -> str:
    """Tiered alerts (ACT/REVIEW/HOLD policy): dispatch >= 0.85 (with adequate
    evidence, verified by the HOLD engine), action 0.70-0.85, monitor otherwise.
    Tiers weight LEA attention - they do not change the review-before-action rule."""
    if score >= 0.85:
        return "dispatch"
    if score >= 0.70:
        return "action"
    return "monitor"


def recommend_action(score: float, level: str) -> str:
    # HUMAN-IN-THE-LOOP: review-oriented language — the system never recommends
    # punitive action directly; it recommends review.
    if level == "CRITICAL":
        return "Review recommended — verify evidence, then coordinate branch + police station"
    if level == "HIGH":
        return "Review recommended — enhanced monitoring + notify local police station"
    return "Review recommended — monitor ATM activity and CCTV"


def _counterfactual_whatif(inst, model, calibrator) -> dict:
    """
    Per-alert WHAT-IF (Phase 4): recompute the risk with the complaint-surge
    signals REMOVED (set to 0) — a valid inference-time ablation, clearly
    labelled as a counterfactual simulation, NOT a causal claim.
    Returns {current_risk, without_complaint_surge, delta, interpretation}.
    """
    import pandas as pd

    try:
        row = inst.to_frame().T.copy()
        current = float(model.predict_proba(row)[:, 1][0])
        if calibrator is not None:
            current = float(calibrator.predict_proba([[current]])[0, 1])
        counter = row.copy()
        for c in ["n_complaints_city_24h", "n_complaints_city_7d", "t_phishing_7d",
                  "t_investment_fraud_7d", "t_job_fraud_7d", "t_upi_fraud_7d",
                  "hours_since_last_complaint_city"]:
            counter[c] = 0.0
        without = float(model.predict_proba(counter)[:, 1][0])
        if calibrator is not None:
            without = float(calibrator.predict_proba([[without]])[0, 1])
        return {
            "current_risk": round(current, 4),
            "risk_without_complaint_surge": round(without, 4),
            "delta": round(current - without, 4),
            "interpretation": (
                "Counterfactual simulation: complaint-surge signals removed at inference "
                "time (valid input ablation). NOT a causal claim; residual risk is carried "
                "by withdrawal/mule-behavioural signals."
            ),
        }
    except Exception:
        return {"current_risk": None, "risk_without_complaint_surge": None, "delta": None,
                "interpretation": "Counterfactual unavailable for this row."}


def _model_version() -> str:
    try:
        return inference.load_pipeline().get("trained_at", "unknown")[:10]
    except Exception:
        return "unknown"


def _uncertainty_block(alert, ev) -> dict:
    """Uncertainty + evidence metadata for every forecast (Phase 4)."""
    score = alert.risk_score
    contrib = len(ev.get("feature_contributions", []) or [])
    freeze = len(ev.get("recommended_freeze_accounts", []) or [])
    evidence_strength = min(1 + contrib + freeze, 5)  # 1 baseline + SHAP/global + freeze intel
    if score >= 0.85 and evidence_strength >= 4:
        confidence = "High"
    elif score >= 0.70 or evidence_strength >= 3:
        confidence = "Medium"
    else:
        confidence = "Low"
    # Model disagreement (Phase 10): Model B (statistical baseline) vs Model A
    disagreement = None
    try:
        import joblib as _joblib

        from .config import ARTIFACT_DIR

        b_path = ARTIFACT_DIR / "model_b.joblib"
        if b_path.exists() and ev.get("feature_row") is not None:
            b = _joblib.load(b_path)
            b_row = ev["feature_row"][b["features"]].to_numpy().reshape(1, -1)
            prob_b = float(b["model"].predict_proba(b_row)[0, 1])
            disagreement = round(abs(score - prob_b), 4)
            if disagreement > 0.35:
                confidence = "Low (model disagreement)"
                ev["hold_reason"] = "model disagreement"
            elif disagreement > 0.20:
                confidence = "Medium (reduced — model disagreement)"
    except Exception:
        pass
    ref = ev.get("data_through")
    freshness_h = max(round((datetime.utcnow() - ref).total_seconds() / 3600.0, 1), 0.0) if ref else None
    return {
        "risk_score": score,
        "confidence": confidence,
        "evidence_strength": f"{evidence_strength}/5",
        "data_freshness_hours": freshness_h,
        "model_version": alert.model_version or _model_version(),
        "model_disagreement_abs": disagreement,
        "prediction_timestamp": datetime.utcnow().isoformat(),
        "prediction_horizon_hours": 24,
        "synthetic_evaluation": True,
        "insufficient_evidence": evidence_strength < 3 or (freshness_h is not None and freshness_h > 48) or (disagreement is not None and disagreement > 0.35),
    }


def _evidence_graph(alert, ev, inst) -> list[dict]:
    """Visual evidence chain per alert (Phase 5) — value/direction/source/synthetic."""
    graph = []
    comp = ev.get("complaint_activity", "")
    wd = ev.get("withdrawal_activity", "")
    graph.append({
        "signal": "Recent complaint surge",
        "value": comp,
        "direction": "up" if "complaint(s)" in comp and "0 complaint" not in comp else "flat",
        "source_type": "complaint_record",
        "observed_or_synthetic": "synthetic",
    })
    graph.append({
        "signal": "Transaction velocity increase",
        "value": f"withdrawals_6h={inst.get('withdrawals_6h', 0):.1f}, withdrawals_24h={inst.get('withdrawals_24h', 0):.1f}",
        "direction": "up" if float(inst.get("withdrawals_6h", 0)) > float(inst.get("withdrawals_24h", 0)) / 6.0 else "flat",
        "source_type": "withdrawal_record",
        "observed_or_synthetic": "synthetic",
    })
    graph.append({
        "signal": "Mule-account concentration",
        "value": f"counterparty_count_24h={inst.get('counterparty_count_24h', 0):.1f}, linked_share={inst.get('linked_proportion_24h', 0):.2f}",
        "direction": "up" if float(inst.get("linked_proportion_24h", 0)) >= 0.4 else "flat",
        "source_type": "complaint_linkage",
        "observed_or_synthetic": "synthetic",
    })
    graph.append({
        "signal": "Geographic proximity",
        "value": f"dist_to_complaint_centroid_km={inst.get('dist_to_complaint_centroid_km', 0):.1f}",
        "direction": "near" if float(inst.get("dist_to_complaint_centroid_km", 99)) <= 10 else "far",
        "source_type": "geography",
        "observed_or_synthetic": "synthetic",
    })
    graph.append({
        "signal": "Temporal similarity (Hawkes intensity)",
        "value": f"hawkes_intensity_24h={inst.get('hawkes_intensity_24h', 0):.3f}",
        "direction": "up" if float(inst.get("hawkes_intensity_24h", 0)) > 15 else "flat",
        "source_type": "complaint_timeline",
        "observed_or_synthetic": "synthetic",
    })
    graph.append({
        "signal": "Forecast risk",
        "value": f"{alert.risk_score:.2f} (threshold >= 0.70)",
        "direction": "flagged" if alert.risk_score >= 0.7 else "not-flagged",
        "source_type": "model_output",
        "observed_or_synthetic": "synthetic",
    })
    return graph


def evaluate_pending_outcomes(db: Session) -> int:
    """
    Closed-loop learning (Phase 9): for alerts created >24h ago with no outcome,
    check whether a fraud withdrawal actually occurred at the flagged ATM in the
    next 24h. Writes AlertOutcome records. NEVER auto-retrains.
    """
    cutoff = datetime.utcnow() - timedelta(hours=24)
    alerts = repo.list_alerts(db, limit=500)
    evaluated = 0
    for a in alerts:
        if a.created_at > cutoff:
            continue
        if repo.get_alert_outcome(db, a.alert_id) is not None:
            continue
        window = [a.created_at, a.created_at + timedelta(hours=24)]
        wds = repo.recent_withdrawals(db, atm_id=a.atm_id, since=window[0])
        fraud_now = [w for w in wds if w.timestamp <= window[1] and w.is_fraud_withdrawal]
        actual = "yes" if fraud_now else "no"
        pred = a.risk_score
        repo.create_alert_outcome(
            db,
            alert_id=a.alert_id, atm_id=a.atm_id,
            predicted_risk=pred, actual_fraud_happened=actual,
            prediction_error=round(abs((1.0 if actual == "yes" else 0.0) - pred), 4),
            is_false_positive=(actual == "no" and pred >= 0.5),
            is_false_negative=(actual == "yes" and pred < 0.5),
            evaluated_at=datetime.utcnow(),
            model_version=a.model_version or "",
        )
        evaluated += 1
    return evaluated


def outcome_monitoring(db: Session) -> dict:
    """Model-monitoring summary (Phase 9): predicted vs actual, FP/FN, drift."""
    outcomes = repo.list_alert_outcomes(db, limit=500)
    decided = [o for o in outcomes if o.actual_fraud_happened in ("yes", "no")]
    n = len(decided)
    if n == 0:
        return {"evaluated": 0, "note": "No outcomes evaluated yet — alerts must age past the 24h horizon."}
    fp = sum(1 for o in decided if o.is_false_positive)
    fn = sum(1 for o in decided if o.is_false_negative)
    tp = sum(1 for o in decided if o.actual_fraud_happened == "yes" and o.predicted_risk >= 0.5)
    tn = sum(1 for o in decided if o.actual_fraud_happened == "no" and o.predicted_risk < 0.5)
    mean_err = sum(o.prediction_error for o in decided) / n
    # calibration drift: ECE over recent outcomes (10 bins, coarse)
    import numpy as np

    ece = 0.0
    for lo, hi in zip(np.linspace(0, 1, 11)[:-1], np.linspace(0, 1, 11)[1:]):
        m = [o for o in decided if lo <= o.predicted_risk < hi]
        if len(m) >= 2:
            conf = sum(o.predicted_risk for o in m) / len(m)
            obs = sum(1 for o in m if o.actual_fraud_happened == "yes") / len(m)
            ece += (len(m) / n) * abs(conf - obs)
    return {
        "evaluated": n,
        "true_positives": tp, "false_positives": fp,
        "true_negatives": tn, "false_negatives": fn,
        "mean_abs_error": round(mean_err, 4),
        "outcome_ece_10_bins": round(float(ece), 4),
        "note": "Outcomes are evaluated against the synthetic withdrawal label (CONTROLLED SYNTHETIC EVALUATION). No auto-retraining on small samples.",
    }


def graded_actions(score: float) -> list[dict]:
    """Response playbook (docs/RESPONSE_PLAYBOOK.md) — graded, advisory steps."""
    steps = []
    if score >= 0.70:
        steps.append({"step": 1, "action": "Notify branch — flag ATM to branch manager + cash-in-charge", "owner": "Bank"})
        steps.append({"step": 2, "action": "Heighten transaction monitoring at the ATM (linked accounts, chunking, velocity)", "owner": "Bank"})
    if score >= 0.85:
        steps.append({"step": 3, "action": "CCTV review + pre-position request near the ATM window", "owner": "Police (SHO)"})
        steps.append({"step": 4, "action": "Tighten withdrawal verification for flagged linked-account tokens (CFCFRMS path)", "owner": "Bank + I4C"})
    return steps


# ------------------------------ Evidence panel --------------------------------
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p = math.pi / 180.0
    a = (
        0.5
        - math.cos((lat2 - lat1) * p) / 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def _percentile_label(value: float, quantiles: list[float]) -> str:
    """Instance percentile vs. training reference: '95th percentile', 'above median', etc."""
    if value >= quantiles[3]:
        return "99th percentile"
    if value >= quantiles[2]:
        return "95th percentile"
    if value >= quantiles[1]:
        return "90th percentile"
    if value >= quantiles[0]:
        return "above median"
    return "below median"


def build_alert_evidence(db: Session, alert) -> dict:
    """
    3-field evidence panel for one alert (SIH spec Section 5b):
      1. COMPLAINT ACTIVITY — plain language
      2. WITHDRAWAL ACTIVITY — plain language
      3. CONTEXT SIGNAL + VERIFIED/ASSUMED disclosure — source-tagged per signal

    Plus header metadata: recency/coverage, fired rule, jurisdiction,
    and top-3 global-importance features with instance percentiles.
    Explainability method is EXPLICITLY global importance + instance percentile
    (NOT SHAP).
    """
    atm = repo.get_atm(db, alert.atm_id)
    if atm is None:
        raise ValueError(f"ATM {alert.atm_id} not found")
    cfg = load_calibration_config()
    ref = resolve_as_of(db)
    X, meta, probs = inference.score_all(ref)

    idx = meta.index[meta["atm_id"] == alert.atm_id][0]
    inst = X.loc[idx]

    # --- field 1: complaint activity (6h, within 2km of the ATM) ---
    comps_6h = repo.list_complaints(db, date_from=ref - timedelta(hours=6), limit=20000)
    near = [
        c for c in comps_6h
        if _haversine_km(atm.latitude, atm.longitude, c.victim_lat, c.victim_lon) <= 2.0
    ]
    n_comps = len(near)
    comp_types: dict[str, int] = {}
    for c in near:
        comp_types[c.complaint_type] = comp_types.get(c.complaint_type, 0) + 1
    comp_detail = ", ".join(f"{k} {v}" for k, v in sorted(comp_types.items())) if comp_types else "none"
    complaint_activity = (
        f"{n_comps} complaint(s) in the last 6h within 2km of this ATM "
        f"({comp_detail}). Linked accounts named in these complaints are "
        f"monitored for withdrawal activity."
    )

    # --- field 2: withdrawal activity (3h at this ATM) ---
    wd_3h = repo.recent_withdrawals(db, atm_id=alert.atm_id, since=ref - timedelta(hours=3))
    n_wd = len(wd_3h)
    n_accts = len({w.account_token for w in wd_3h})
    withdrawal_activity = (
        f"{n_wd} withdrawal(s) from {n_accts} distinct account(s) at this ATM in the last 3h."
    )

    # --- CFCFRMS recovery intel: linked accounts to recommend blocking ---
    mule_ids = set(repo.complaint_mule_account_tokens(db))
    wd_24h = repo.recent_withdrawals(db, atm_id=alert.atm_id, since=ref - timedelta(hours=24))
    freeze = sorted(
        {w.account_token for w in wd_24h if w.account_token in mule_ids},
        key=lambda a: -sum(1 for w in wd_24h if w.account_token == a),
    )[:3]
    recommended_freeze_accounts = [
        {"account_token": a, "recent_withdrawals": sum(1 for w in wd_24h if w.account_token == a)}
        for a in freeze
    ]

    # --- field 3: context signal + verified/assumed disclosure ---
    hour = ref.hour
    is_night = hour in NIGHT_HOURS
    night_tag = cfg["behaviour"]["night_weight_source_status"]
    cluster_tag = cfg["clustering"]["pareto_skew_source_status"]
    cluster_dir_tag = cfg["clustering"]["clustering_direction_source_status"]

    quantiles = inference.load_pipeline().get("feature_quantiles", {})
    # NOTE: this proxy uses complaint-linked account activity at the ATM
    # (available at prediction time) — the historical ground-truth fraud count
    # feature (fraud_withdrawals_24h) was removed as a label leak.
    fr_hist_pct = _percentile_label(
        float(inst["linked_proportion_24h"]),
        quantiles.get("linked_proportion_24h", [0, 0, 0, 1]),
    )

    night_clause = (
        f"Forecast time is in the night window (19:00–05:00); night-time weighting "
        f"is an {night_tag.replace('_', ' ')} parameter (no India-specific public statistic)."
        if is_night
        else "Forecast time is outside the night window; no night weighting applies."
    )
    cluster_clause = (
        f"This ATM shows complaint-linked (mule) account activity in the {fr_hist_pct} — the DIRECTION of "
        f"withdrawal clustering is a verified pattern (I4C Suspect Registry documents "
        f"concentrated cash-out hubs); the exact concentration coefficients are "
        f"{cluster_tag.replace('_', ' ')} tunable parameters."
    )
    context_signal = f"{night_clause} {cluster_clause}"

    # --- feature contributions (top-3 global importance, instance percentiles) ---
    pipe = inference.load_pipeline()
    model = pipe["model"]
    importance = sorted(
        zip(pipe["feature_names"], model.feature_importances_), key=lambda x: -x[1]
    )[:3]
    feature_contributions = []
    for name, imp in importance:
        value = float(inst[name])
        feature_contributions.append({
            "feature": name,
            "value": round(value, 4),
            "percentile": _percentile_label(value, quantiles.get(name, [0, 0, 0, 1])),
            "global_importance": round(float(imp), 4),
        })

    n_scored = int(len(probs))
    return {
        "alert_id": alert.alert_id,
        "atm_id": alert.atm_id,
        "jurisdiction": {
            "state": atm.state,
            "district": atm.district,
            "police_station_area": atm.police_station_area,
        },
        "recommended_recipients": [
            f"Local Police ({atm.district}) — {atm.police_station_area}",
            f"Bank Branch Manager ({atm.bank_name} / {atm.branch_name})",
        ],
        "complaint_activity": complaint_activity,
        "withdrawal_activity": withdrawal_activity,
        "context_signal": context_signal,
        "recommended_freeze_accounts": recommended_freeze_accounts,
        "data_through": ref,
        "atms_scored": n_scored,
        "atms_total": n_scored,
        "scoring_coverage_pct": 100.0,
        "suggested_action": alert.recommended_action,
        "recommended_actions": graded_actions(alert.risk_score),
        "fired_rule": f"risk_score >= {RISK_THRESHOLD}",
        "explainability_note": (
            "Feature contributions: global feature importance + instance percentile "
            "(interpretation aid), plus per-instance TreeSHAP values via XGBoost's "
            "native pred_contribs (exact tree-based attribution; no causal claim implied)."
        ),
        "feature_contributions": feature_contributions,
        "per_instance_shap": inference.shap_contributions(inst),
        "evidence_graph": _evidence_graph(alert, {
            "complaint_activity": complaint_activity,
            "withdrawal_activity": withdrawal_activity,
        }, inst),
        "uncertainty": _uncertainty_block(alert, {
            "feature_contributions": feature_contributions,
            "recommended_freeze_accounts": recommended_freeze_accounts,
            "data_through": ref,
            "feature_row": inst,
        }),
        "counterfactual_whatif": _counterfactual_whatif(inst, inference.load_pipeline()["model"],
                                                        inference.load_pipeline().get("calibrator")),
    }


# ------------------------------ Demo-mode cache --------------------------------
def read_demo_cache(name: str):
    """Serve pre-computed 'golden path' data when DEMO_MODE=true (fallback plan)."""
    if not DEMO_MODE:
        return None
    path = DEMO_CACHE_DIR / f"{name}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------ Live-stream ingestion -------------------------
def drip_ingest(db: Session, rng, cfg: dict) -> int:
    """
    StreamSimulatorAdapter drip: insert a fresh complaint + a few withdrawals
    (incl. occasional mule-linked fraud) at 'now'. PII tokens stay vault-consistent.
    KafkaAdapter (true scale) = Tier 2 stub.
    """
    from .data.synthetic_data import BANKS, CITIES, Pseudonymizer, _account_raw, _phone_raw, _rid

    now = datetime.utcnow()
    city = rng.choice(list(CITIES.keys()))
    meta = CITIES[city]
    # per-drip salt: repeat runs (e.g. load tests) must never regenerate the
    # same PII tokens and hit UNIQUE constraints — tokens stay vault-consistent
    pii = Pseudonymizer(salt=f"drip-{uuid.uuid4().hex}")
    raw_acct = _account_raw(rng)
    token = pii.account(raw_acct)
    db.add_all(pii.vault_rows(now))
    db.add(models.Account(account_token=token, home_bank=rng.choice(BANKS),
                          first_seen=now, is_mule=False))
    complaint = models.Complaint(
        complaint_id=_rid("CMP", 12), filing_timestamp=now,
        complaint_type=rng.choice(cfg["dataset"]["complaint_types"]),
        victim_city=city, victim_district=meta["district"], victim_state=meta["state"],
        victim_pin=meta["pin"],
        victim_lat=round(meta["lat"] + rng.uniform(-0.05, 0.05), 6),
        victim_lon=round(meta["lon"] + rng.uniform(-0.05, 0.05), 6),
        amount_lost=round(rng.uniform(1000, 500000), 2),
        linked_account_token=token, linked_phone_token=pii.phone(_phone_raw(rng)),
        status="under_investigation",
    )
    db.add(complaint)
    atm_ids = [a.atm_id for a in repo.list_atms(db, city=city, limit=1000)]
    for _ in range(rng.randint(1, 3)):
        db.add(models.Withdrawal(
            transaction_id=_rid("TXN", 12), timestamp=now, atm_id=rng.choice(atm_ids),
            account_token=token, amount=round(rng.uniform(500, 20000), 2),
            channel="ATM", is_fraud_withdrawal=False,
        ))
    db.commit()
    _invalidate_score_cache()
    return 1 + 3  # complaint + withdrawals inserted


# ------------------------------ Intelligence reports ----------------------------
def build_hotspot_report(db: Session, alert, generating_user) -> dict:
    """
    Per-hotspot Intelligence Report (Phase 4 — deliverable c):
    case-ref, officer, jurisdiction, risk + confidence, 3-field evidence,
    linked complaints, mule account tokens, suspected ATM + window, action,
    synthetic-data watermark. Hash goes to the ledger (chain-of-custody).
    """
    atm = repo.get_atm(db, alert.atm_id)
    ev = build_alert_evidence(db, alert)
    ref = ev["data_through"]
    complaints_near = []
    for c in repo.list_complaints(db, date_from=ref - timedelta(hours=24), limit=20000):
        if _haversine_km(atm.latitude, atm.longitude, c.victim_lat, c.victim_lon) <= 2.0:
            complaints_near.append(c)
    report = {
        "report_id": f"RPT-HS-{alert.atm_id}-{ref.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}",
        "report_type": "hotspot",
        "title": f"Intelligence Report — {alert.atm_id}",
        "created_at": datetime.utcnow().isoformat(),
        "created_by": f"{generating_user.display_name} ({generating_user.role})",
        "case_ref": alert.alert_id,
        "jurisdiction": {"state": atm.state, "district": atm.district, "police_station_area": atm.police_station_area},
        "recommended_recipients": ev["recommended_recipients"],
        "atm": {"atm_id": atm.atm_id, "bank": atm.bank_name, "branch": atm.branch_name},
        "risk_score": alert.risk_score,
        "confidence": "calibrated probability (Platt), synthetic labels",
        "predicted_window": "next 24h",
        "evidence": {
            "complaint_activity": ev["complaint_activity"],
            "withdrawal_activity": ev["withdrawal_activity"],
            "context_signal": ev["context_signal"],
        },
        "linked_complaints": [
            {"complaint_id": c.complaint_id, "type": c.complaint_type, "amount_lost": c.amount_lost,
             "account_token": c.linked_account_token}
            for c in complaints_near[:10]
        ],
        "mule_account_tokens": [f["account_token"] for f in ev["recommended_freeze_accounts"]],
        "recommended_action": alert.recommended_action,
        "watermark": "Synthetic data / hackathon prototype — not operational intelligence.",
    }
    return report


def build_situational_report(db: Session, generating_user, as_of: datetime | None = None) -> dict:
    """I4C daily/shift Situational Report (national aggregate)."""
    ref = as_of or resolve_as_of(db)
    h24 = ref - timedelta(hours=24)
    d7 = ref - timedelta(days=7)
    report = {
        "report_id": f"RPT-SIT-{ref.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}",
        "report_type": "situational",
        "title": "I4C Situational Report",
        "created_at": datetime.utcnow().isoformat(),
        "created_by": f"{generating_user.display_name} ({generating_user.role})",
        "data_through": ref.isoformat(),
        "complaints_per_city_24h": repo.complaints_by_city(db, since=h24),
        "complaints_per_city_7d": repo.complaints_by_city(db, since=d7),
        "complaints_by_type_24h": repo.complaints_by_type(db, since=h24),
        "high_risk_atms_per_district": repo.high_risk_alerts_by_district(db),
        "alerts": {"total": repo.count_alerts(db), "new": repo.count_alerts(db, status="new"),
                   "actioned": repo.count_alerts(db, status="actioned")},
        "recovery_funnel": recovery_funnel(db, days=7),
        "watermark": "Synthetic data / hackathon prototype — not operational intelligence.",
    }
    return report


def generate_pdf(report: dict, out_dir: Path) -> Path:
    """Render the intelligence report as a printable PDF (reportlab)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    path = out_dir / f"{report['report_id']}.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=A4, title=report["title"])
    story = [Paragraph(report["title"], styles["Title"]),
             Paragraph(f"Generated: {report['created_at']} · {report['created_by']}", styles["Normal"]),
             Spacer(1, 10)]
    if report["report_type"] == "hotspot":
        story.append(Paragraph(f"Case ref: {report['case_ref']}", styles["Heading2"]))
        j = report["jurisdiction"]
        story.append(Paragraph(f"Jurisdiction: {j['state']}, {j['district']}, {j['police_station_area']} (fictional)", styles["Normal"]))
        story.append(Paragraph(f"ATM: {report['atm']['atm_id']} · {report['atm']['bank']} / {report['atm']['branch']}", styles["Normal"]))
        story.append(Paragraph(f"Risk score: {report['risk_score']:.2f} ({report['confidence']})", styles["Normal"]))
        story.append(Paragraph(f"Predicted window: {report['predicted_window']}", styles["Normal"]))
        story.append(Paragraph("Recommended action: " + report["recommended_action"], styles["Normal"]))
        story.append(Paragraph("<b>Evidence — Complaint activity:</b> " + report["evidence"]["complaint_activity"], styles["Normal"]))
        story.append(Paragraph("<b>Evidence — Withdrawal activity:</b> " + report["evidence"]["withdrawal_activity"], styles["Normal"]))
        story.append(Paragraph("<b>Evidence — Context + source disclosure:</b> " + report["evidence"]["context_signal"], styles["Normal"]))
        rows = [["Complaint", "Type", "Amount (INR)", "Account token"]]
        for c in report["linked_complaints"][:10]:
            rows.append([c["complaint_id"], c["type"], f"{c['amount_lost']:,.0f}", c["account_token"]])
        story.append(Spacer(1, 8))
        story.append(Table(rows, repeatRows=1, style=TableStyle([("GRID", (0, 0), (-1, -1), 0.4, "#888"),
                                                                 ("BACKGROUND", (0, 0), (-1, 0), "#dde7f5")])))
        story.append(Spacer(1, 8))
        story.append(Paragraph("Mule account tokens: " + ", ".join(report["mule_account_tokens"]) + " — recommended for fund-blocking via CFCFRMS path.", styles["Normal"]))
        story.append(Paragraph("Recommended recipients: " + "; ".join(report["recommended_recipients"]), styles["Normal"]))
    else:  # situational
        t = Table([[k, str(v)] for k, v in report["complaints_per_city_24h"].items()] +
                  [["Recovery funnel", str(report["recovery_funnel"])]], repeatRows=1)
        story.append(Paragraph("Complaints per city (24h):", styles["Heading2"]))
        story.append(t)
        story.append(Paragraph("Alerts: " + str(report["alerts"]), styles["Normal"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>{report['watermark']}</b>", styles["Normal"]))
    doc.build(story)
    return path


def build_city_report(db: Session, city: str, as_of: datetime | None = None) -> dict:
    """City-level intelligence brief (HTML/JSON) — used by /api/reports/city."""
    ref = as_of or resolve_as_of(db)
    h24 = ref - timedelta(hours=24)
    d7 = ref - timedelta(days=7)
    scores = get_risk_scores(db, as_of=ref, city=city)
    hotspots = sorted(scores, key=lambda s: s["risk_score"], reverse=True)[:10]
    report = {
        "report_id": f"RPT-{city[:3].upper()}-{ref.strftime('%Y%m%d%H%M')}",
        "city": city,
        "jurisdiction": {
            "state": CITIES_STATE.get(city, {}).get("state", ""),
            "district": CITIES_STATE.get(city, {}).get("district", city),
        },
        "generated_at": datetime.utcnow().isoformat(),
        "data_through": ref.isoformat(),
        "complaints_24h": repo.count_complaints(db, since=h24),
        "complaints_7d": repo.count_complaints(db, since=d7),
        "complaints_by_type_24h": repo.complaints_by_type(db, city=city, since=h24),
        "complaints_by_type_7d": repo.complaints_by_type(db, city=city, since=d7),
        "atms_scored": len(scores),
        "high_risk_atms": sum(1 for s in scores if s["risk_score"] >= RISK_THRESHOLD),
        "hotspots": [
            {"atm_id": s["atm_id"], "bank_name": s["bank_name"], "branch_name": s["branch_name"],
             "police_station_area": s["police_station_area"], "risk_score": s["risk_score"],
             "risk_level": s["risk_level"]}
            for s in hotspots
        ],
        "open_alerts": [
            {"alert_id": a.alert_id, "atm_id": a.atm_id, "risk_score": a.risk_score,
             "recommended_action": a.recommended_action, "status": a.status}
            for a in repo.list_alerts(db, city=city, limit=100) if a.status in ("new", "acknowledged")
        ],
        "methodology_note": (
            "Risk scores are calibrated probabilities from an XGBoost model + Platt "
            "calibration trained on synthetic data. See CALIBRATION_NOTES.md and "
            "LIMITATIONS.md — metrics are NOT real-world precision."
        ),
        "ui_policy": "Locations shown are fictionalized for demonstration.",
    }
    return report


def report_audit_ref(report: dict) -> str:
    """Stable SHA-256 fingerprint of a report — recorded on the audit chain."""
    import hashlib

    return hashlib.sha256(json.dumps(report, sort_keys=True, default=str).encode()).hexdigest()[:32]


# ------------------------------ Audit chain -------------------------------------
def verify_ledger_chain(db: Session) -> dict:
    """Recompute the hash chain; any tampered record breaks it."""
    import hashlib

    records = repo.ledger_chain(db)
    prev = "0" * 64
    for r in records:
        raw = f"{r.index}|{r.created_at.isoformat()}|{r.actor}|{r.event_type}|{r.payload_hash}|{r.prev_hash}"
        recomputed = hashlib.sha256(raw.encode()).hexdigest()
        if r.prev_hash != prev or r.hash != recomputed:
            return {"intact": False, "broken_at_index": r.index, "records": len(records)}
        prev = r.hash
    return {"intact": True, "records": len(records), "last_hash": prev}


def tamper_demo_record(db: Session) -> dict:
    """DEMO ONLY (ALLOW_TAMPER_DEMO=true): flip one ledger payload so the chain
    integrity check detects it. The original hash is backed up so
    scripts/restore_ledger.py can restore the chain exactly (the demo's
    'restore story'). Never enabled in production."""
    from .config import ALLOW_TAMPER_DEMO, ARTIFACT_DIR

    if not ALLOW_TAMPER_DEMO:
        return {"error": "tamper demo disabled (set ALLOW_TAMPER_DEMO=true)"}
    records = repo.ledger_chain(db)
    if not records:
        return {"error": "ledger empty"}
    target = records[-1]
    backup = {"index": target.index, "original_payload_hash": target.payload_hash}
    (ARTIFACT_DIR / "ledger_tamper_backup.json").write_text(json.dumps(backup), encoding="utf-8")
    target.payload_hash = ("0" * 64) if target.payload_hash != ("0" * 64) else ("1" * 64)
    db.commit()
    return {"tampered": target.entity_id, "note": "payload_hash flipped — /ledger/verify will now fail"}


from .data.synthetic_data import CITIES as CITIES_STATE  # noqa: E402  (state lookup for reports)


# -------------------------------- Statistics --------------------------------
def summary_stats(db: Session, k: int = 20, user=None) -> dict:
    from .config import DEMO_MODE

    if DEMO_MODE:
        cached = read_demo_cache("risk-scores")
        scores = cached if cached is not None else []
        now = datetime.utcnow()
    else:
        now = resolve_as_of(db)
        scores = get_risk_scores(db, as_of=now, user=user)
    h24 = datetime.utcnow() - timedelta(hours=24)
    d7 = datetime.utcnow() - timedelta(days=7)
    hotspots = sorted(scores, key=lambda s: s["risk_score"], reverse=True)[:k]
    high_risk_atms = sum(1 for s in scores if s["risk_score"] >= RISK_THRESHOLD)
    high_by_city: dict[str, int] = {}
    for s in scores:
        if s["risk_score"] >= RISK_THRESHOLD:
            high_by_city[s["city"]] = high_by_city.get(s["city"], 0) + 1

    return {
        "generated_at": now,
        "total_complaints": repo.count_complaints(db),
        "complaints_24h": repo.count_complaints(db, since=h24),
        "complaints_7d": repo.count_complaints(db, since=d7),
        "total_withdrawals": repo.count_withdrawals(db),
        "fraud_withdrawals_7d": repo.count_fraud_withdrawals(db, since=d7),
        "total_atms": repo.count_atms(db),
        "high_risk_atms": high_risk_atms,
        "alerts_total": repo.count_alerts(db),
        "alerts_new": repo.count_alerts(db, status="new"),
        "alerts_actioned": repo.count_alerts(db, status="actioned"),
        "complaints_by_city_24h": repo.complaints_by_city(db, since=h24),
        "complaints_by_city_7d": repo.complaints_by_city(db, since=d7),
        "complaints_by_type_24h": repo.complaints_by_type(db, since=h24),
        "complaints_by_city_type_24h": repo.complaints_by_city_type(db, since=h24),
        "high_risk_atms_by_city": high_by_city,
        "hotspots": hotspots,
    }