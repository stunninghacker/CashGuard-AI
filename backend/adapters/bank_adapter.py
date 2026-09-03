"""
BankFundFreezeAdapter — Tier 2 core-banking / CFCFRMS fund-block integration
(Issue 12).

The real flow:
  I4C/Bank marks an account as frozen (freeze_requested) -> the CFCFRMS / bank
  core-banking API actually stops disbursement on the linked mule account.

This adapter wraps that call behind a single, testable interface:

    BankFundFreezeAdapter().send_freeze_request(rec, amount_held)

Honest behaviour:
- `LIVE` defaults to False. Until a real bank endpoint + credential is
  configured (env), the adapter returns a **simulated** freeze outcome with
  `simulated: true` and a synthetic freeze reference — it NEVER pretends a real
  bank call happened, and it NEVER touches real accounts (the repo's synthetic
  recovery_recommendations are the only entities involved).
- When `LIVE` is enabled, the adapter would POST to the configured core-banking
  endpoint. The request/response contract mirrors CFCFRMS fund-freeze payloads.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Real integration gate — mirror the repo's honest "configured:false" convention.
LIVE = os.getenv("BANK_FREEZE_LIVE", "0").strip().lower() in ("1", "true", "yes")

CORE_BANKING_URL = os.getenv("BANK_CORE_BANKING_URL", "")


@dataclass
class FreezeResult:
    """Outcome of a fund-freeze request against the bank core-banking system."""

    success: bool
    freeze_ref: str
    status: str  # accepted / held / rejected
    simulated: bool
    message: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "freeze_ref": self.freeze_ref,
            "status": self.status,
            "simulated": self.simulated,
            "message": self.message,
            "details": self.details,
        }


class BankFundFreezeAdapter:
    """Single entry point for freezing funds on a mule account."""

    def __init__(self, live: bool = LIVE, base_url: str = CORE_BANKING_URL):
        self.live = live
        self.base_url = base_url

    def send_freeze_request(self, rec, amount_held: float = 0.0) -> FreezeResult:
        """
        Request a fund freeze for the mule account behind a recovery
        recommendation. `rec` is a RecoveryRecommendation (rec_id, account_token,
        home_bank, amount_at_risk, ...). Returns a FreezeResult.
        """
        if self.live:
            if not self.base_url:
                return FreezeResult(
                    success=False, freeze_ref="", status="rejected",
                    simulated=True,
                    message="LIVE mode set but BANK_CORE_BANKING_URL is empty; refusing to call.",
                )
            return self._live_request(rec, amount_held)
        return self._simulate(rec, amount_held)

    def _simulate(self, rec, amount_held: float) -> FreezeResult:
        """
        Deterministic, non-destructive simulation of the bank accepting the
        freeze. Always labelled `simulated: true`.
        """
        freeze_ref = f"FB-{uuid.uuid4().hex[:12].upper()}"
        return FreezeResult(
            success=True,
            freeze_ref=freeze_ref,
            status="held",
            simulated=True,
            message=(
                f"Simulated fund-freeze accepted for account {rec.account_token} "
                f"at {rec.home_bank} (ref {freeze_ref}). Configure a live "
                "core-banking endpoint (BANK_FREEZE_LIVE=1) for a real freeze."
            ),
            details={
                "account_token": rec.account_token,
                "home_bank": rec.home_bank,
                "amount_at_risk": rec.amount_at_risk,
                "amount_held": amount_held or rec.amount_at_risk,
                "requested_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _live_request(self, rec, amount_held: float) -> FreezeResult:
        """
        Real core-banking POST (CFCFRMS fund-freeze contract). Kept as the
        documented integration path; not executed in this prototype.
        """
        # import here so the optional HTTP lib is only needed when going live
        import requests  # type: ignore

        payload = {
            "account_token": rec.account_token,
            "bank": rec.home_bank,
            "amount_at_risk": rec.amount_at_risk,
            "amount_held": amount_held or rec.amount_at_risk,
            "recommended_action": rec.recommended_action,
            "reference": f"{rec.rec_id}",
        }
        resp = requests.post(f"{self.base_url}/fund-freeze", json=payload, timeout=20)
        resp.raise_for_status()
        body = resp.json()
        return FreezeResult(
            success=bool(body.get("accepted", False)),
            freeze_ref=body.get("freeze_ref", ""),
            status="held" if body.get("accepted") else "rejected",
            simulated=False,
            message=body.get("message", "Live freeze response"),
            details=body,
        )
