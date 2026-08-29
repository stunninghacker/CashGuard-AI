"""
ORM models — mirror the real NCRP / CFCFRMS / bank ATM data schema.

In production these tables would be populated by ETL pipelines pulling from:
  * NCRP  (National Cyber Crime Reporting Portal) complaint records
  * CFCFRMS (Citizen Financial Cyber Fraud Reporting and Management System)
  * Bank ATM/transaction feeds (NPCI, UPI, bank core-banking systems)

The extra lat/lon columns on complaints are derived victim geolocation
(city/district level) used for the geo risk features and map layers.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Complaint(Base):
    """Cybercrime complaint filed on the (simulated) NCRP portal.

    PII-SAFE: linked_account_id / linked_phone are STORED AS SALTED-HASH TOKENS
    (e.g. acct_7f3a9c2b). Raw values live only in the mock re-identification
    vault (VaultEntry) — role-scoped, access-audited, never shown on dashboards.
    """

    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    complaint_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    filing_timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    complaint_type: Mapped[str] = mapped_column(String(64), index=True)  # phishing / investment_fraud / job_fraud / upi_fraud / digital_arrest / sextortion
    victim_city: Mapped[str] = mapped_column(String(64), index=True)
    victim_district: Mapped[str] = mapped_column(String(64))
    victim_state: Mapped[str] = mapped_column(String(64), index=True)  # jurisdiction awareness
    victim_pin: Mapped[str] = mapped_column(String(12))
    victim_lat: Mapped[float] = mapped_column(Float, default=0.0)
    victim_lon: Mapped[float] = mapped_column(Float, default=0.0)
    amount_lost: Mapped[float] = mapped_column(Float, default=0.0)
    linked_account_token: Mapped[str] = mapped_column(String(64), index=True)  # PII-pseudonymized
    linked_phone_token: Mapped[str] = mapped_column(String(64))                 # PII-pseudonymized
    status: Mapped[str] = mapped_column(String(32), default="under_investigation")  # under_investigation / funds_frozen / funds_partially_recovered


class ATM(Base):
    """ATM / branch network master data (simulated bank data feed)."""

    __tablename__ = "atms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    atm_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    bank_name: Mapped[str] = mapped_column(String(64), index=True)
    branch_name: Mapped[str] = mapped_column(String(64))
    city: Mapped[str] = mapped_column(String(64), index=True)
    district: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(64), index=True)  # jurisdiction awareness
    pin: Mapped[str] = mapped_column(String(12))
    police_station_area: Mapped[str] = mapped_column(String(64), index=True)  # jurisdiction awareness
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    withdrawals: Mapped[list["Withdrawal"]] = relationship(back_populates="atm")


class Withdrawal(Base):
    """Cash withdrawal transaction at an ATM (simulated bank transaction feed).

    account_token is a PII-pseudonymized account identifier (mock vault maps it).
    """

    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    atm_id: Mapped[str] = mapped_column(String(32), ForeignKey("atms.atm_id"), index=True)
    account_token: Mapped[str] = mapped_column(String(64), index=True)  # PII-pseudonymized
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    channel: Mapped[str] = mapped_column(String(16), default="ATM")
    is_fraud_withdrawal: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    atm: Mapped["ATM"] = relationship(back_populates="withdrawals")


class Account(Base):
    """Account master (recovery loop). account_token only — PII-safe."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    home_bank: Mapped[str] = mapped_column(String(64), index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, index=True)
    is_mule: Mapped[bool] = mapped_column(Boolean, default=False, index=True)  # eval only
    txn_frequency_7d: Mapped[float] = mapped_column(Float, default=0.0)   # behavioural source fields
    counterparty_count_7d: Mapped[int] = mapped_column(Integer, default=0)
    fund_velocity_inr_h: Mapped[float] = mapped_column(Float, default=0.0)
    activity_spike_flag: Mapped[bool] = mapped_column(Boolean, default=False)


class VaultEntry(Base):
    """
    MOCK re-identification vault (PII pseudonymization, Phase 1).

    Maps pseudonymized tokens back to raw identifiers. In production this would be
    a separate access-controlled store with its own audit trail + DPDP-Act
    compliance; here it simulates the vault so the role-scoped masking path can be
    demonstrated end-to-end. Dashboards NEVER show raw values.
    """

    __tablename__ = "vault"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(16))  # account / phone
    raw_value: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class User(Base):
    """Dashboard users for the prototype (Phase 3 auth/RBAC)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(24), index=True)  # POLICE_STATE / POLICE_DISTRICT / BANK / I4C_ADMIN
    scope: Mapped[str] = mapped_column(String(64), default="")  # state | district | bank_name | national
    display_name: Mapped[str] = mapped_column(String(64), default="")


class Alert(Base):
    """Alert generated by the risk engine — the actionable intelligence output."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    atm_id: Mapped[str] = mapped_column(String(32), ForeignKey("atms.atm_id"), index=True)
    bank_name: Mapped[str] = mapped_column(String(64), default="")
    city: Mapped[str] = mapped_column(String(64), index=True)
    district: Mapped[str] = mapped_column(String(64), default="")
    state: Mapped[str] = mapped_column(String(64), default="")          # jurisdiction awareness
    police_station_area: Mapped[str] = mapped_column(String(64), default="")  # jurisdiction awareness
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    tier: Mapped[str] = mapped_column(String(16), default="monitor", index=True)  # dispatch / action / monitor (ACT/REVIEW/HOLD policy)
    recommended_action: Mapped[str] = mapped_column(String(160), default="Enhanced monitoring")
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)  # new / acknowledged / actioned / dismissed / escalated / monitoring / review_requested
    decision_reason: Mapped[str] = mapped_column(String(256), default="")  # mandatory for dismiss/escalate
    model_version: Mapped[str] = mapped_column(String(32), default="")
    sms_log: Mapped[str] = mapped_column(Text, default="")
    email_log: Mapped[str] = mapped_column(Text, default="")
    dispatch_log: Mapped[str] = mapped_column(Text, default="")  # I4C / state-LEA webhook (mock)
    origin_state: Mapped[str] = mapped_column(String(64), default="")  # complainant-origin jurisdiction (cross-state seeding)
    routing_status: Mapped[str] = mapped_column(String(16), default="none", index=True)  # none / handoff / handoff_ack / handoff_complete
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actioned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reobservation_count: Mapped[int] = mapped_column(Integer, default=0)  # anti alert-fatigue: times the same risk was re-seen WITHOUT a duplicate alert
    last_reobserved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    risk_delta_vs_last: Mapped[float | None] = mapped_column(Float, nullable=True)  # risk change vs the ATM's most recent alert (genuine escalation)


class AlertOutcome(Base):
    """
    Closed-loop outcome store (Phase 9): predicted risk vs observed outcome.

    After the 24h horizon, an outcome record is written: did a fraud withdrawal
    actually occur at the flagged ATM within the window? Used for model
    monitoring (FP/FN, calibration drift). Never auto-retrains on tiny data.
    """

    __tablename__ = "alert_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    atm_id: Mapped[str] = mapped_column(String(32), index=True)
    predicted_risk: Mapped[float] = mapped_column(Float, default=0.0)
    actual_fraud_happened: Mapped[str] = mapped_column(String(16), default="unknown")  # yes / no / unknown
    prediction_error: Mapped[float] = mapped_column(Float, default=0.0)  # |actual - predicted|
    is_false_positive: Mapped[bool] = mapped_column(Boolean, default=False)
    is_false_negative: Mapped[bool] = mapped_column(Boolean, default=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    model_version: Mapped[str] = mapped_column(String(32), default="")


class AlertHandoff(Base):
    """
    Inter-agency jurisdiction routing record (Item 4).

    When a predicted fraud-withdrawal location (the flagged ATM's state) differs
    from the complainant-originating jurisdiction that seeded the risk
    (origin_state), the alert is a CROSS-STATE case. A handoff is created to
    forward the intelligence to the receiving state-LEA queue, while the
    originating state keeps provenance. This models the real I4C coordination
    node pattern: cases move between state jurisdictions.

    HONEST SCOPE: an in-app routing/handoff queue with mock state-LEA
    forwarding. It does not call any real inter-agency gateway (Tier 2).
    """

    __tablename__ = "alert_handoffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    handoff_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    alert_id: Mapped[str] = mapped_column(String(32), ForeignKey("alerts.alert_id"), index=True)
    atm_id: Mapped[str] = mapped_column(String(32), index=True)
    origin_state: Mapped[str] = mapped_column(String(64), index=True)   # complaint-origin jurisdiction
    receiving_state: Mapped[str] = mapped_column(String(64), index=True)  # predicted withdrawal state
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)  # queued / ack / complete / rejected
    reason: Mapped[str] = mapped_column(String(200), default="cross_state_withdrawal")
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ack_by: Mapped[str] = mapped_column(String(64), default="")
    ack_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(String(256), default="")


class AuditRecord(Base):
    """
    Append-only, tamper-evident hash-chained LEDGER (Blockchain & Cybersecurity theme).

    Block = { index, timestamp, actor (user+role), event_type, payload_hash
    (SHA-256 of event payload), prev_hash, this_hash = SHA-256(index|ts|actor|
    event_type|payload_hash|prev_hash) }.

    Logged for: alert created, evidence snapshot, alert status change,
    intelligence report generated, fund-block recommendation issued, access
    events. GET /ledger/verify recomputes the chain; tampering is detected.

    HONEST LABEL: an append-only SHA-256 hash chain providing tamper-evidence
    and chain-of-custody — NOT a cryptocurrency/public blockchain. Tier 2 =
    anchor the chain root to a permissioned ledger (Hyperledger Fabric).
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    index: Mapped[int] = mapped_column(Integer, unique=True, index=True)  # chain position (unique => impossible to double-append the same block)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    actor: Mapped[str] = mapped_column(String(64), default="system")  # user_id + role
    event_type: Mapped[str] = mapped_column(String(32), index=True)   # alert_created / evidence_snapshot / status_changed / report_generated / fund_block_issued / access
    entity_id: Mapped[str] = mapped_column(String(64), index=True)    # alert_id / report id / account_token
    payload_hash: Mapped[str] = mapped_column(String(64), default="")
    prev_hash: Mapped[str] = mapped_column(String(64), default="")
    hash: Mapped[str] = mapped_column(String(64), index=True)


class Report(Base):
    """Generated intelligence reports (PDF + JSON payload), chain-of-custody."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    report_type: Mapped[str] = mapped_column(String(16), index=True)  # hotspot / situational
    title: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_by: Mapped[str] = mapped_column(String(64), default="")
    payload: Mapped[str] = mapped_column(Text, default="{}")  # JSON payload
    pdf_path: Mapped[str] = mapped_column(String(256), default="")
    ledger_hash: Mapped[str] = mapped_column(String(64), default="")


class RecoveryRecommendation(Base):
    """
    CFCFRMS-style fund-block recommendation (Phase 6 — the recovery story).

    Recovery outcomes (freeze -> held -> recovered) are SYNTHETIC/illustrative —
    clearly labelled; real CFCFRMS/core-banking APIs are the Tier 2 integration
    point (commented in code).
    """

    __tablename__ = "recovery_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rec_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    alert_id: Mapped[str] = mapped_column(String(32), index=True)
    account_token: Mapped[str] = mapped_column(String(64), index=True)
    home_bank: Mapped[str] = mapped_column(String(64), index=True)
    linked_complaint_ids: Mapped[str] = mapped_column(Text, default="[]")
    amount_at_risk: Mapped[float] = mapped_column(Float, default=0.0)
    suspected_atm: Mapped[str] = mapped_column(String(32), default="")
    predicted_window: Mapped[str] = mapped_column(String(64), default="")
    recommended_action: Mapped[str] = mapped_column(String(32), default="freeze")  # freeze / hold / enhanced_monitoring
    status: Mapped[str] = mapped_column(String(24), default="freeze_requested")  # freeze_requested / held / recovered
    amount_held: Mapped[float] = mapped_column(Float, default=0.0)
    amount_recovered: Mapped[float] = mapped_column(Float, default=0.0)


class InboxMessage(Base):
    """
    Mock I4C inbox — receives REAL outbound webhooks (dispatch + CFCFRMS stubs)
    and stores them for display. The webhook path is real (httpx); the inbox is
    local and labelled mock.
    """

    __tablename__ = "inbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    channel: Mapped[str] = mapped_column(String(32), default="dispatch")  # dispatch / cfcfrms / access_audit
    payload: Mapped[str] = mapped_column(Text, default="{}")