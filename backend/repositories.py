"""
Repository layer — the ONLY place that touches the database.

Swapping storage engines (SQLite -> PostgreSQL) or switching to live feeds
(NCRP/CFCFRMS REST APIs, bank ATM transaction APIs) only requires rewriting
this file; routes and services stay untouched.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models


# ------------------------------- Complaints --------------------------------
def list_complaints(
    db: Session,
    city: str | None = None,
    district: str | None = None,
    state: str | None = None,
    complaint_type: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
    user=None,  # RBAC: row-level scope enforcement lives HERE
) -> list[models.Complaint]:
    stmt = select(models.Complaint).order_by(models.Complaint.filing_timestamp.desc())
    if city:
        stmt = stmt.where(models.Complaint.victim_city == city)
    if district:
        stmt = stmt.where(models.Complaint.victim_district == district)
    if state:
        stmt = stmt.where(models.Complaint.victim_state == state)
    if complaint_type:
        stmt = stmt.where(models.Complaint.complaint_type == complaint_type)
    if status:
        stmt = stmt.where(models.Complaint.status == status)
    if date_from:
        stmt = stmt.where(models.Complaint.filing_timestamp >= date_from)
    if date_to:
        stmt = stmt.where(models.Complaint.filing_timestamp <= date_to)
    scope = _scoped_complaint_stmt(user) if user else None
    if scope is not None:
        stmt = stmt.where(scope)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def count_complaints(db: Session, since: datetime | None = None) -> int:
    stmt = select(func.count(models.Complaint.id))
    if since:
        stmt = stmt.where(models.Complaint.filing_timestamp >= since)
    return int(db.scalar(stmt) or 0)


def complaints_by_city(db: Session, since: datetime | None = None) -> dict[str, int]:
    stmt = select(models.Complaint.victim_city, func.count()).group_by(models.Complaint.victim_city)
    if since:
        stmt = stmt.where(models.Complaint.filing_timestamp >= since)
    return {city: int(n) for city, n in db.execute(stmt).all()}


def complaints_by_type(db: Session, city: str | None = None, since: datetime | None = None) -> dict[str, int]:
    """Complaints grouped by complaint_type (optionally city + recency) — category drill-down."""
    stmt = select(models.Complaint.complaint_type, func.count()).group_by(models.Complaint.complaint_type)
    if city:
        stmt = stmt.where(models.Complaint.victim_city == city)
    if since:
        stmt = stmt.where(models.Complaint.filing_timestamp >= since)
    return {t: int(n) for t, n in db.execute(stmt).all()}


def complaints_by_city_type(db: Session, since: datetime | None = None) -> dict[str, dict[str, int]]:
    """city -> {complaint_type: count} — I4C drill-down by location + crime category."""
    stmt = (
        select(models.Complaint.victim_city, models.Complaint.complaint_type, func.count())
        .group_by(models.Complaint.victim_city, models.Complaint.complaint_type)
    )
    if since:
        stmt = stmt.where(models.Complaint.filing_timestamp >= since)
    out: dict[str, dict[str, int]] = {}
    for city, ctype, n in db.execute(stmt).all():
        out.setdefault(city, {})[ctype] = int(n)
    return out


# ---------------------------------- ATMs ------------------------------------
def list_atms(
    db: Session,
    city: str | None = None,
    bank_name: str | None = None,
    limit: int = 1000,
    offset: int = 0,
    user=None,  # RBAC scope
) -> list[models.ATM]:
    stmt = select(models.ATM).order_by(models.ATM.atm_id)
    if city:
        stmt = stmt.where(models.ATM.city == city)
    if bank_name:
        stmt = stmt.where(models.ATM.bank_name == bank_name)
    scope = _scoped_atm_stmt(user) if user else None
    if scope is not None:
        stmt = stmt.where(scope)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def get_atm(db: Session, atm_id: str) -> models.ATM | None:
    return db.scalar(select(models.ATM).where(models.ATM.atm_id == atm_id))


def list_banks(db: Session) -> list[str]:
    stmt = select(models.ATM.bank_name).distinct().order_by(models.ATM.bank_name)
    return list(db.scalars(stmt).all())


def count_atms(db: Session) -> int:
    return int(db.scalar(select(func.count(models.ATM.id))) or 0)


# ------------------------------- Withdrawals --------------------------------
def list_withdrawals(
    db: Session,
    atm_id: str | None = None,
    account_token: str | None = None,
    fraud_only: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[models.Withdrawal]:
    stmt = select(models.Withdrawal).order_by(models.Withdrawal.timestamp.desc())
    if atm_id:
        stmt = stmt.where(models.Withdrawal.atm_id == atm_id)
    if account_token:
        stmt = stmt.where(models.Withdrawal.account_token == account_token)
    if fraud_only is not None:
        stmt = stmt.where(models.Withdrawal.is_fraud_withdrawal == fraud_only)
    if date_from:
        stmt = stmt.where(models.Withdrawal.timestamp >= date_from)
    if date_to:
        stmt = stmt.where(models.Withdrawal.timestamp <= date_to)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def count_withdrawals(db: Session, since: datetime | None = None) -> int:
    stmt = select(func.count(models.Withdrawal.id))
    if since:
        stmt = stmt.where(models.Withdrawal.timestamp >= since)
    return int(db.scalar(stmt) or 0)


def recent_withdrawals(
    db: Session,
    atm_id: str | None = None,
    since: datetime | None = None,
) -> list[models.Withdrawal]:
    """Withdrawals at an ATM (optionally since a timestamp) — used by the evidence panel."""
    stmt = select(models.Withdrawal).order_by(models.Withdrawal.timestamp.desc())
    if atm_id:
        stmt = stmt.where(models.Withdrawal.atm_id == atm_id)
    if since:
        stmt = stmt.where(models.Withdrawal.timestamp >= since)
    stmt = stmt.limit(1000)
    return list(db.scalars(stmt).all())


def count_fraud_withdrawals(db: Session, since: datetime | None = None) -> int:
    stmt = select(func.count(models.Withdrawal.id)).where(models.Withdrawal.is_fraud_withdrawal.is_(True))
    if since:
        stmt = stmt.where(models.Withdrawal.timestamp >= since)
    return int(db.scalar(stmt) or 0)


# ---------------------------------- Alerts ----------------------------------
def create_alert(db: Session, **kwargs) -> models.Alert:
    alert = models.Alert(**kwargs)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def get_alert_by_atm_recent(db: Session, atm_id: str, since: datetime) -> models.Alert | None:
    return db.scalar(
        select(models.Alert)
        .where(models.Alert.atm_id == atm_id, models.Alert.created_at >= since)
        .order_by(models.Alert.created_at.desc()).limit(1)
    )


def create_alert_outcome(db: Session, **kwargs) -> models.AlertOutcome:
    outcome = models.AlertOutcome(**kwargs)
    db.add(outcome)
    db.commit()
    db.refresh(outcome)
    return outcome


def get_alert_outcome(db: Session, alert_id: str) -> models.AlertOutcome | None:
    return db.scalar(select(models.AlertOutcome).where(models.AlertOutcome.alert_id == alert_id))


def list_alert_outcomes(db: Session, limit: int = 500) -> list[models.AlertOutcome]:
    return list(db.scalars(select(models.AlertOutcome).order_by(models.AlertOutcome.evaluated_at.desc()).limit(limit)))


def list_alerts(
    db: Session,
    status: str | None = None,
    atm_id: str | None = None,
    city: str | None = None,
    limit: int = 100,
    offset: int = 0,
    user=None,  # RBAC scope
) -> list[models.Alert]:
    stmt = select(models.Alert).order_by(models.Alert.created_at.desc())
    if status:
        stmt = stmt.where(models.Alert.status == status)
    if atm_id:
        stmt = stmt.where(models.Alert.atm_id == atm_id)
    if city:
        stmt = stmt.where(models.Alert.city == city)
    scope = _scoped_alert_stmt(user) if user else None
    if scope is not None:
        stmt = stmt.where(scope)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def get_alert(db: Session, alert_id: str) -> models.Alert | None:
    return db.scalar(select(models.Alert).where(models.Alert.alert_id == alert_id))


def update_alert_status(db: Session, alert: models.Alert, status: str, reason: str = "") -> models.Alert:
    now = datetime.utcnow()
    alert.status = status
    if reason:
        alert.decision_reason = reason
    if status == "acknowledged" and alert.acknowledged_at is None:
        alert.acknowledged_at = now
    if status == "actioned":
        alert.actioned_at = now
    db.commit()
    db.refresh(alert)
    return alert


def count_alerts(db: Session, status: str | None = None) -> int:
    stmt = select(func.count(models.Alert.id))
    if status:
        stmt = stmt.where(models.Alert.status == status)
    return int(db.scalar(stmt) or 0)


def recent_open_alert_for_atm(db: Session, atm_id: str, hours: int) -> models.Alert | None:
    """Return a still-open (new/acknowledged) alert for this ATM within the cooldown window."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    stmt = (
        select(models.Alert)
        .where(
            models.Alert.atm_id == atm_id,
            models.Alert.status.in_(["new", "acknowledged"]),
            models.Alert.created_at >= cutoff,
        )
        .order_by(models.Alert.created_at.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def high_risk_atms_count(db: Session, threshold: float, since: datetime | None = None) -> int:
    stmt = select(func.count()).select_from(
        select(models.Alert.atm_id)
        .where(models.Alert.risk_score >= threshold)
        .group_by(models.Alert.atm_id)
        .subquery()
    )
    return int(db.scalar(stmt) or 0)


def high_risk_alerts_by_district(db: Session) -> dict[str, int]:
    stmt = (
        select(models.Alert.district, func.count())
        .where(models.Alert.risk_score >= 0.7)
        .group_by(models.Alert.district)
    )
    return {d: int(n) for d, n in db.execute(stmt).all()}


# ------------------------------- Ledger (hash chain) -------------------------
def complaint_mule_account_tokens(db: Session) -> list[str]:
    """Distinct linked (mule) account tokens from complaints — CFCFRMS freeze intel."""
    return list(db.scalars(select(models.Complaint.linked_account_token).distinct()))


def append_ledger(
    db: Session,
    actor: str,
    event_type: str,
    entity_id: str,
    payload_hash: str = "",
    payload: dict | None = None,
) -> models.AuditRecord:
    """
    Append a block to the tamper-evident SHA-256 chain.

    Block = {index, timestamp, actor, event_type, payload_hash, prev_hash,
             hash = SHA-256(index|ts|actor|event_type|payload_hash|prev_hash)}.
    """
    import hashlib
    import json as _json

    last = db.scalar(select(models.AuditRecord).order_by(models.AuditRecord.index.desc()).limit(1))
    prev_hash = last.hash if last else ("0" * 64)
    index = (last.index + 1) if last else 1
    if payload_hash == "" and payload is not None:
        payload_hash = hashlib.sha256(_json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    ts = datetime.utcnow()
    raw = f"{index}|{ts.isoformat()}|{actor}|{event_type}|{payload_hash}|{prev_hash}"
    record = models.AuditRecord(
        index=index,
        created_at=ts,
        actor=actor,
        event_type=event_type,
        entity_id=entity_id,
        payload_hash=payload_hash,
        prev_hash=prev_hash,
        hash=hashlib.sha256(raw.encode()).hexdigest(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def ledger_chain(db: Session) -> list[models.AuditRecord]:
    return list(db.scalars(select(models.AuditRecord).order_by(models.AuditRecord.index)))


# ------------------------------- Users (auth/RBAC) ----------------------------
def get_user_by_id(db: Session, user_id: str) -> models.User | None:
    return db.scalar(select(models.User).where(models.User.user_id == user_id))


def get_user_by_username(db: Session, username: str) -> models.User | None:
    return db.scalar(select(models.User).where(models.User.username == username))


def create_user(db: Session, user_id: str, username: str, password_hash: str, role: str, scope: str, display_name: str) -> models.User:
    user = models.User(user_id=user_id, username=username, password_hash=password_hash, role=role, scope=scope, display_name=display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_demo_users(db: Session) -> None:
    """Four demo users (one per role) — documented in README / DEMO_SCRIPT."""
    from .security import hash_password

    if get_user_by_username(db, "officer.district1") is not None:
        return
    users = [
        ("u-police-state", "officer.statea", "PoliceStateA!1", "POLICE_STATE", "State-A", "SHO (State-A)"),
        ("u-police-district", "officer.district1", "District1!1", "POLICE_DISTRICT", "Northsagar", "Inspector (Northsagar)"),
        ("u-bank", "bank.hdfc", "HdfcBank!1", "BANK", "HDFC Bank", "Bank Fraud Ops (HDFC)"),
        ("u-i4c", "i4c.admin", "I4cAdmin!1", "I4C_ADMIN", "national", "I4C Duty Officer"),
    ]
    for uid, username, password, role, scope, display in users:
        create_user(db, uid, username, hash_password(password), role, scope, display)
    db.commit()


# ------------------------------- Scope-aware reads (RBAC) ---------------------
def _scoped_alert_stmt(user) -> None:
    """Row-level scoping for alerts — enforced HERE, never in the frontend."""
    if user.role == "I4C_ADMIN":
        return None
    if user.role == "BANK":
        return models.Alert.bank_name == user.scope
    if user.role == "POLICE_DISTRICT":
        return models.Alert.district == user.scope
    if user.role == "POLICE_STATE":
        return models.Alert.state == user.scope
    return None


def _scoped_atm_stmt(user) -> None:
    if user.role == "I4C_ADMIN":
        return None
    if user.role == "BANK":
        return models.ATM.bank_name == user.scope
    if user.role == "POLICE_DISTRICT":
        return models.ATM.district == user.scope
    if user.role == "POLICE_STATE":
        return models.ATM.state == user.scope
    return None


def _scoped_complaint_stmt(user) -> None:
    if user.role == "I4C_ADMIN":
        return None
    if user.role == "POLICE_DISTRICT":
        return models.Complaint.victim_district == user.scope
    if user.role == "POLICE_STATE":
        return models.Complaint.victim_state == user.scope
    return None  # BANK sees complaints only via linked-account evidence, not as a list


def create_report(db: Session, report_id: str, report_type: str, title: str, payload: str, pdf_path: str, ledger_hash: str) -> models.Report:
    report = models.Report(report_id=report_id, report_type=report_type, title=title,
                           payload=payload, pdf_path=pdf_path, ledger_hash=ledger_hash,
                           created_at=datetime.utcnow())
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_report(db: Session, report_id: str) -> models.Report | None:
    return db.scalar(select(models.Report).where(models.Report.report_id == report_id))


def complaint_cities_for_category(db: Session, complaint_type: str, since: datetime | None = None, limit: int = 5000) -> set[str]:
    stmt = select(models.Complaint.victim_city).where(models.Complaint.complaint_type == complaint_type).distinct()
    if since:
        stmt = stmt.where(models.Complaint.filing_timestamp >= since)
    return set(db.scalars(stmt).all())


# ------------------------------- Recovery / inbox ----------------------------
def create_recovery_recommendation(db: Session, **kwargs) -> models.RecoveryRecommendation:
    kwargs.setdefault("created_at", datetime.utcnow())
    rec = models.RecoveryRecommendation(**kwargs)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def get_recovery_recommendation(db: Session, rec_id: str) -> models.RecoveryRecommendation | None:
    return db.scalar(select(models.RecoveryRecommendation).where(models.RecoveryRecommendation.rec_id == rec_id))


def list_recovery_recommendations(db: Session, since: datetime | None = None, bank_name: str | None = None) -> list[models.RecoveryRecommendation]:
    stmt = select(models.RecoveryRecommendation).order_by(models.RecoveryRecommendation.created_at.desc())
    if since:
        stmt = stmt.where(models.RecoveryRecommendation.created_at >= since)
    if bank_name:
        stmt = stmt.where(models.RecoveryRecommendation.home_bank == bank_name)
    stmt = stmt.limit(500)
    return list(db.scalars(stmt).all())


def update_recovery_status(db: Session, rec, status: str, amount_held: float = 0.0, amount_recovered: float = 0.0):
    rec.status = status
    if amount_held:
        rec.amount_held = amount_held
    if amount_recovered:
        rec.amount_recovered = amount_recovered
    db.commit()
    db.refresh(rec)
    return rec


def complaint_ids_for_account(db: Session, account_token: str) -> list[str]:
    return list(db.scalars(
        select(models.Complaint.complaint_id)
        .where(models.Complaint.linked_account_token == account_token)
        .limit(20)
    ))


def bank_for_account(db: Session, account_token: str) -> str | None:
    acct = db.scalar(select(models.Account).where(models.Account.account_token == account_token))
    return acct.home_bank if acct else None


def store_inbox_message(db: Session, channel: str, payload: dict) -> models.InboxMessage:
    import json as _json

    msg = models.InboxMessage(received_at=datetime.utcnow(), channel=channel,
                              payload=_json.dumps(payload, default=str))
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def list_inbox_messages(db: Session, limit: int = 100) -> list[models.InboxMessage]:
    return list(db.scalars(select(models.InboxMessage).order_by(models.InboxMessage.received_at.desc()).limit(limit)))


# ------------------------------- Misc / meta --------------------------------
def latest_timestamp(db: Session) -> datetime | None:
    """Latest data timestamp across complaints & withdrawals (used as simulated 'now')."""
    c = db.scalar(select(func.max(models.Complaint.filing_timestamp)))
    w = db.scalar(select(func.max(models.Withdrawal.timestamp)))
    candidates = [t for t in (c, w) if t is not None]
    return max(candidates) if candidates else None


def table_counts(db: Session) -> dict[str, int]:
    return {
        "complaints": count_complaints(db),
        "atms": count_atms(db),
        "withdrawals": count_withdrawals(db),
        "alerts": count_alerts(db),
    }