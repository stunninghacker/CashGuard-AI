"""
Inter-agency jurisdiction routing engine (Item 4).

Determines whether a generated alert is a CROSS-STATE case — i.e. the
complainant(s) whose reports seeded the ATM's risk originate from a different
state than the predicted withdrawal location (the flagged ATM's state). When
so, an AlertHandoff is created: the intelligence is queued to the receiving
state-LEA while the originating state retains provenance (I4C coordination-node
pattern).

Determinism / honesty:
- origin_state is derived strictly from Complaint rows: an ATM is "seeded" by
  complaints whose victim_district / victim_city / police_station_area matches
  the ATM's own location fields. The modal victim_state among those seeds is
  used. If it differs from the ATM state, the case is cross-state.
- If no matching complaint seeds exist, origin_state is "" and no handoff is
  created (the case stays intra-jurisdiction).
- Handoff forwarding is an in-app queue with mock state-LEA semantics; it does
  not call a real inter-agency gateway (documented Tier 2).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models


def _match_keys(atm: dict) -> list[tuple[str, str]]:
    """Ordered (column, value) match keys against an ATM's location.

    Most-specific first; we fall through to broader matches so an ATM with no
    district-level complaints can still be seeded by city or station complaints.
    """
    keys = []
    if atm.get("district"):
        keys.append(("victim_district", atm["district"]))
    if atm.get("state"):
        keys.append(("victim_state", atm["state"]))
    if atm.get("city"):
        keys.append(("victim_city", atm["city"]))
    if atm.get("police_station_area"):
        keys.append(("police_station_area", atm["police_station_area"]))
    return keys


def origin_state_for_atm(db: Session, atm: dict, days: int = 45) -> str:
    """Origin victim_state that seeded an ATM's risk; "" if none.

    Two independent signals, strongest wins:
      1. LOCAL SEED: modal victim_state of complaints whose victim_district /
         victim_city / police_station_area matches the ATM's own location.
      2. ACCOUNT-LINKED (cross-state mule): modal victim_state of complaints
         whose linked_account_token has a Withdrawal at this ATM in the window
         but whose victim_state differs from the ATM's state. This is the real
         layering pattern (funds originated in state X, cashed out in state Y).

    If signal 2 yields a state different from the ATM's, the case is routed as
    cross-state even when local complaints are same-state.
    """
    keys = _match_keys(atm)
    from .config import SEED_COMPLAINT_LOOKBACK_DAYS

    lookback = int(SEED_COMPLAINT_LOOKBACK_DAYS) if SEED_COMPLAINT_LOOKBACK_DAYS else days
    cutoff = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=lookback)

    cross = ""
    if atm.get("atm_id"):
        # link flagged ATM -> withdrawal account tokens -> complainants
        acct_rows = db.execute(
            select(models.Withdrawal.account_token)
            .where(models.Withdrawal.atm_id == atm["atm_id"], models.Withdrawal.timestamp >= cutoff)
            .limit(400)
        ).all()
        tokens = {r[0] for r in acct_rows if r[0]}
        if tokens:
            cross_rows = db.execute(
                select(models.Complaint.victim_state, func.count(models.Complaint.id))
                .where(
                    models.Complaint.linked_account_token.in_(list(tokens)),
                    models.Complaint.filing_timestamp >= cutoff,
                    models.Complaint.victim_state != (atm.get("state") or ""),
                )
                .group_by(models.Complaint.victim_state)
                .order_by(func.count(models.Complaint.id).desc(), models.Complaint.victim_state)
            ).all()
            if cross_rows:
                candidate = cross_rows[0][0] or ""
                if candidate and candidate != atm.get("state"):
                    cross = candidate

    # local seed (district -> state -> city -> station precedence)
    if not keys:
        return cross
    for col, val in keys:
        rows = db.execute(
            select(models.Complaint.victim_state, func.count(models.Complaint.id))
            .where(getattr(models.Complaint, col) == val, models.Complaint.filing_timestamp >= cutoff)
            .group_by(models.Complaint.victim_state)
            .order_by(func.count(models.Complaint.id).desc(), models.Complaint.victim_state)
        ).all()
        if rows:
            origin = rows[0][0] or ""
            # if account-linked cross-state origin exists and differs, prefer it
            # (a cross-state mule case should be handed off regardless)
            if cross:
                return cross
            return origin
    return cross


def route_alert(db: Session, alert: models.Alert, atm: dict | None = None) -> models.AlertHandoff | None:
    """Create a cross-state AlertHandoff for a new alert, if the origin state
    differs from the predicted-withdrawal state. Returns the handoff or None.

    Idempotent: if a handoff already exists for this alert, returns it without
    duplicating."""
    existing = db.scalar(select(models.AlertHandoff).where(models.AlertHandoff.alert_id == alert.alert_id))
    if existing is not None:
        return existing

    origin = alert.origin_state or (origin_state_for_atm(db, atm) if atm else "")
    if not origin or origin == alert.state:
        return None  # intra-jurisdiction — no handoff

    from . import repositories

    handoff = models.AlertHandoff(
        handoff_id=f"HO-{alert.alert_id}",
        alert_id=alert.alert_id,
        atm_id=alert.atm_id,
        origin_state=origin,
        receiving_state=alert.state,
        status="queued",
        reason="cross_state_withdrawal",
        created_at=datetime.utcnow(),
    )
    db.add(handoff)
    db.commit()
    db.refresh(handoff)
    repositories.append_ledger(
        db, actor="routing engine", event_type="alert_handoff_created",
        entity_id=handoff.handoff_id,
        payload={"alert_id": alert.alert_id, "origin_state": origin,
                 "receiving_state": alert.state, "reason": handoff.reason},
    )
    return handoff


def list_handoffs(db: Session, status: str | None = None, limit: int = 200) -> list[models.AlertHandoff]:
    stmt = select(models.AlertHandoff).order_by(models.AlertHandoff.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(models.AlertHandoff.status == status)
    return list(db.scalars(stmt))


def ack_handoff(db: Session, handoff_id: str, actor: str, complete: bool = False,
                note: str = "") -> models.AlertHandoff | None:
    h = db.scalar(select(models.AlertHandoff).where(models.AlertHandoff.handoff_id == handoff_id))
    if h is None:
        return None
    h.status = "complete" if complete else "ack"
    h.ack_by = actor
    h.ack_at = datetime.utcnow()
    h.note = note or h.note
    # mirror routing status onto the alert so the UI badge reflects it
    from . import repositories
    al = db.scalar(select(models.Alert).where(models.Alert.alert_id == h.alert_id))
    if al is not None:
        al.routing_status = "handoff_complete" if complete else "handoff_ack"
        repositories.append_ledger(
            db, actor=actor, event_type="alert_handoff_" + ("complete" if complete else "ack"),
            entity_id=h.handoff_id,
            payload={"alert_id": h.alert_id, "status": h.status, "note": note},
        )
    db.commit()
    return h
