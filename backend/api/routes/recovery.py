"""
Recovery / CFCFRMS fund-blocking loop (Phase 6 — the money story).

GET /recovery/recommendations         -> fund-block queue (bank-scoped for BANK role)
POST /recovery/{rec_id}/status        -> freeze_requested / held / recovered
GET /recovery/funnel                  -> flagged -> held -> recovered (synthetic, labelled)

Real CFCFRMS/core-banking APIs are the Tier 2 integration point — commented below.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ... import repositories as repo, services
from ...adapters.bank_adapter import BankFundFreezeAdapter
from ...database import get_db
from ...security import require_auth

router = APIRouter(prefix="/recovery", tags=["recovery"])


class RecoveryStatusIn(BaseModel):
    status: str  # freeze_requested / held / recovered
    amount_held: float = 0.0
    amount_recovered: float = 0.0


class SimulateFreezeIn(BaseModel):
    rec_id: str
    amount_held: float | None = None


@router.get("/recommendations")
def recommendations(
    bank_name: str | None = None,
    user=Depends(require_auth("BANK", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    # Tier 2 integration point: fetch live mule-account status from the real
    # CFCFRMS / bank core-banking API here; the prototype uses the local store.
    scope_bank = user.scope if user.role == "BANK" else bank_name
    recs = repo.list_recovery_recommendations(db, bank_name=scope_bank)
    return [
        {
            "rec_id": r.rec_id, "created_at": r.created_at.isoformat(),
            "alert_id": r.alert_id, "account_token": r.account_token,
            "home_bank": r.home_bank, "linked_complaint_ids": r.linked_complaint_ids,
            "amount_at_risk": r.amount_at_risk, "suspected_atm": r.suspected_atm,
            "predicted_window": r.predicted_window, "recommended_action": r.recommended_action,
            "status": r.status, "amount_held": r.amount_held, "amount_recovered": r.amount_recovered,
        }
        for r in recs
    ]


@router.post("/{rec_id}/status")
def update_status(
    rec_id: str,
    payload: RecoveryStatusIn,
    user=Depends(require_auth("BANK", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    rec = repo.get_recovery_recommendation(db, rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    updated = repo.update_recovery_status(db, rec, payload.status, payload.amount_held, payload.amount_recovered)
    repo.append_ledger(db, actor=f"{user.user_id} ({user.role})", event_type="fund_block_status",
                       entity_id=rec_id, payload={"status": payload.status})
    from ...realtime import enqueue_broadcast

    enqueue_broadcast("recovery_status", {"rec_id": rec_id, "status": payload.status})
    return {"rec_id": rec_id, "status": updated.status,
            "amount_held": updated.amount_held, "amount_recovered": updated.amount_recovered}


@router.get("/funnel")
def funnel(days: int = 7, user=Depends(require_auth("BANK", "I4C_ADMIN", "POLICE_STATE")), db: Session = Depends(get_db)):
    return services.recovery_funnel(db, days=days)


@router.post("/simulate-freeze")
def simulate_freeze(
    payload: SimulateFreezeIn,
    user=Depends(require_auth("BANK", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    """
    Issue 12 — drive a fund freeze through the core-banking Adapter layer.

    Looks up the recovery recommendation, calls BankFundFreezeAdapter
    (simulated unless a LIVE core-banking endpoint is configured), persists
    the freeze outcome, emits a ledger + WS event, and returns the freeze
    result with an explicit `simulated` flag.
    """
    rec = repo.get_recovery_recommendation(db, payload.rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    adapter = BankFundFreezeAdapter()
    result = adapter.send_freeze_request(rec, amount_held=payload.amount_held or 0.0)

    if result.success:
        repo.update_recovery_status(
            db, rec, "held",
            amount_held=payload.amount_held or rec.amount_at_risk,
        )
    repo.append_ledger(db, actor=f"{user.user_id} ({user.role})",
                       event_type="fund_freeze_request",
                       entity_id=rec.rec_id,
                       payload={"freeze_ref": result.freeze_ref,
                                "status": result.status,
                                "simulated": result.simulated})
    from ...realtime import enqueue_broadcast

    enqueue_broadcast("fund_freeze", {"rec_id": rec.rec_id,
                                      "freeze_ref": result.freeze_ref,
                                      "status": result.status,
                                      "simulated": result.simulated})
    return {
        "rec_id": rec.rec_id,
        "account_token": getattr(rec, "account_token", None),
        "home_bank": getattr(rec, "home_bank", None),
        "freeze": result.to_dict(),
    }