"""
Pydantic request/response schemas for the REST API.

Kept deliberately thin — in production these map 1:1 onto the contract the
I4C / state-LEA / bank dashboards consume.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ----------------------------- Responses ----------------------------------
class ComplaintOut(BaseModel):
    complaint_id: str
    filing_timestamp: datetime
    complaint_type: str
    victim_city: str
    victim_district: str
    victim_state: str
    victim_pin: str
    victim_lat: float
    victim_lon: float
    amount_lost: float
    linked_account_token: str
    linked_phone_token: str
    status: str

    model_config = {"from_attributes": True}


class ATMOut(BaseModel):
    atm_id: str
    bank_name: str
    branch_name: str
    city: str
    district: str
    state: str
    pin: str
    police_station_area: str
    latitude: float
    longitude: float

    model_config = {"from_attributes": True}


class WithdrawalOut(BaseModel):
    transaction_id: str
    timestamp: datetime
    atm_id: str
    account_token: str
    amount: float
    channel: str
    is_fraud_withdrawal: bool

    model_config = {"from_attributes": True}


class RiskScoreOut(BaseModel):
    """One ATM + its predicted probability of a fraud withdrawal in the next 24h."""

    atm_id: str
    bank_name: str
    branch_name: str
    city: str
    district: str
    state: str
    police_station_area: str
    pin: str
    latitude: float
    longitude: float
    risk_score: float
    risk_level: str  # LOW / MEDIUM / HIGH / CRITICAL
    emerging_risk: float = 0.0  # rate-of-change score: "risk rising fast" vs "usually risky"
    intervention_priority: float = 0.0  # "where to act first" (see INTERVENTION_PRIORITY.md)
    priority_exposure: float = 0.0
    priority_urgency: float = 0.0
    priority_evidence: float = 0.0
    priority_confidence_weight: float = 0.0
    as_of: datetime


class AlertOut(BaseModel):
    alert_id: str
    created_at: datetime
    atm_id: str
    bank_name: str
    city: str
    district: str
    state: str
    police_station_area: str
    risk_score: float
    recommended_action: str
    tier: str = "monitor"  # dispatch / action / monitor (ACT/REVIEW/HOLD policy)
    status: str
    decision_reason: str = ""
    model_version: str = ""
    sms_log: str
    email_log: str
    dispatch_log: str = ""
    origin_state: str = ""  # complainant-origin jurisdiction (cross-state seeding)
    routing_status: str = "none"  # none / handoff / handoff_ack / handoff_complete
    acknowledged_at: datetime | None = None
    actioned_at: datetime | None = None

    model_config = {"from_attributes": True}


class AlertCreateIn(BaseModel):
    """Schema for POST /alerts — used by the scheduler / external triggers."""

    atm_id: str
    risk_score: float
    recommended_action: str = "Enhanced monitoring"
    status: str = "new"


class AlertUpdateIn(BaseModel):
    status: str
    reason: str = ""


class OutcomeOut(BaseModel):
    alert_id: str
    atm_id: str
    predicted_risk: float
    actual_fraud_happened: str
    prediction_error: float
    is_false_positive: bool
    is_false_negative: bool
    evaluated_at: datetime
    model_version: str


class EvidenceOut(BaseModel):
    """3-field evidence panel for one alert (Section 5b of the spec)."""

    alert_id: str
    atm_id: str
    jurisdiction: dict[str, str]      # state / district / police_station_area (fictional)
    recommended_recipients: list[str]
    complaint_activity: str           # field 1 (plain language)
    withdrawal_activity: str          # field 2 (plain language)
    context_signal: str               # field 3 (context + VERIFIED/ASSUMED disclosure)
    recommended_freeze_accounts: list[dict] = []  # CFCFRMS fund-blocking intel
    recommended_actions: list[dict] = []           # graded response-playbook steps
    per_instance_shap: list[dict] = []             # native XGBoost pred_contribs
    evidence_graph: list[dict] = []                # visual evidence chain (Phase 5)
    uncertainty: dict = {}                         # confidence/freshness/version (Phase 4)
    counterfactual_whatif: dict = {}               # inference-time ablation (Phase 4)
    data_through: datetime            # recency/coverage header metadata
    atms_scored: int
    atms_total: int
    scoring_coverage_pct: float
    suggested_action: str
    fired_rule: str                   # e.g. "risk_score >= 0.70"
    explainability_note: str          # "global importance + instance percentile (NOT SHAP)"
    feature_contributions: list[dict]  # top-3 features: name, value, percentile


class TrainResponse(BaseModel):
    status: str
    message: str
    metrics: dict | None = None


class SummaryStatsOut(BaseModel):
    generated_at: datetime
    total_complaints: int
    complaints_24h: int
    complaints_7d: int
    total_withdrawals: int
    fraud_withdrawals_7d: int
    total_atms: int
    high_risk_atms: int
    alerts_total: int
    alerts_new: int
    alerts_actioned: int
    complaints_by_city_24h: dict[str, int]
    complaints_by_city_7d: dict[str, int]
    complaints_by_type_24h: dict[str, int]
    complaints_by_city_type_24h: dict[str, dict[str, int]]
    high_risk_atms_by_city: dict[str, int]
    hotspots: list[RiskScoreOut]