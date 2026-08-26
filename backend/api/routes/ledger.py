"""
Tamper-evident ledger endpoints (Blockchain & Cybersecurity theme — Phase 4).

GET /ledger              -> list blocks (chain-of-custody record)
GET /ledger/verify       -> recompute the SHA-256 chain; reports integrity
POST /ledger/tamper-demo -> DEMO ONLY (ALLOW_TAMPER_DEMO=true): flip one block
                            so /ledger/verify detects the tampering.

HONEST LABEL: append-only SHA-256 hash chain (tamper-evidence, chain-of-custody)
— NOT a cryptocurrency/public blockchain. Tier 2 = anchor the chain root to a
permissioned ledger (Hyperledger Fabric) for multi-org consensus.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ... import repositories as repo, services
from ...database import get_db
from ...security import require_auth

router = APIRouter(prefix="/ledger", tags=["ledger"])


@router.get("")
def ledger_list(user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN")), db: Session = Depends(get_db)):
    records = repo.ledger_chain(db)
    return [
        {
            "index": r.index,
            "created_at": r.created_at.isoformat(),
            "actor": r.actor,
            "event_type": r.event_type,
            "entity_id": r.entity_id,
            "payload_hash": r.payload_hash[:16] + "…",
            "prev_hash": r.prev_hash[:16] + "…",
            "hash": r.hash[:16] + "…",
        }
        for r in records
    ]


@router.get("/verify")
def ledger_verify(user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN")), db: Session = Depends(get_db)):
    return services.verify_ledger_chain(db)


@router.post("/tamper-demo")
def ledger_tamper_demo(user=Depends(require_auth("I4C_ADMIN")), db: Session = Depends(get_db)):
    """Flip one record's payload hash — the next /ledger/verify must fail."""
    return services.tamper_demo_record(db)