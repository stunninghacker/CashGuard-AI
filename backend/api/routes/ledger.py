"""
Tamper-evident ledger endpoints (Blockchain & Cybersecurity theme — Phase 4).

GET /ledger              -> list blocks (chain-of-custody record)
GET /ledger/verify       -> recompute the SHA-256 chain; reports integrity
POST /ledger/tamper-demo -> DEMO ONLY (ALLOW_TAMPER_DEMO=true): flip one block
                            so /ledger/verify detects the tampering.
GET /ledger/verify-onchain -> Tier-2: prove the true PoW blockchain root matches
                            the on-chain AuditLog record (Polygon Amoy).
POST /ledger/anchor      -> Tier-2: submit the blockchain root to the on-chain
                            AuditLog contract (needs env RPC/key/contract).

HONEST LABEL: append-only SHA-256 hash chain (tamper-evidence, chain-of-custody)
— NOT a cryptocurrency/public blockchain. Tier 2 = anchor the chain root to a
permissioned on-chain AuditLog contract for an immutable, public, timestamped
proof-of-existence; the write path /ledger/anchor and the verifier
/ledger/verify-onchain both report "not configured" honestly until the
LEDGER_ANCHOR_* env vars are set (see backend/blockchain/onchain.py).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ... import repositories as repo, services
from ...database import get_db
from ...security import require_auth

router = APIRouter(prefix="/ledger", tags=["ledger"])


@router.get("")
def ledger_list(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    records = repo.ledger_chain(db)
    total = len(records)
    page = records[offset:offset + limit]
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "records": [
            {
                "index": r.index,
                "created_at": r.created_at.isoformat(),
                "actor": r.actor,
                "event_type": r.event_type,
                "entity_id": r.entity_id,
                "payload_hash": r.payload_hash[:16] + "\u2026",
                "prev_hash": r.prev_hash[:16] + "\u2026",
                "hash": r.hash[:16] + "\u2026",
            }
            for r in page
        ],
    }


@router.get("/verify")
def ledger_verify(user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN")), db: Session = Depends(get_db)):
    return services.verify_ledger_chain(db)


@router.get("/network")
def ledger_network(user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN"))):
    """Replicated-ledger status (demo-grade 3-node replication; see
    BLOCKCHAIN_JUSTIFICATION.md for what is real vs simulated)."""
    from ...database import SessionLocal
    from ...ledger_replication import ReplicaNetwork
    from ... import repositories as repo

    db = SessionLocal()
    try:
        records = repo.ledger_chain(db)
    finally:
        db.close()
    net = ReplicaNetwork()
    for r in records:
        net.replicate(r.actor, r.event_type, r.payload_hash)
    return net.network_status()


@router.post("/tamper-demo")
def ledger_tamper_demo(user=Depends(require_auth("I4C_ADMIN")), db: Session = Depends(get_db)):
    """Flip one record's payload hash — the next /ledger/verify must fail."""
    return services.tamper_demo_record(db)


@router.post("/restore")
def ledger_restore(user=Depends(require_auth("I4C_ADMIN")), db: Session = Depends(get_db)):
    """Reverse the tamper-demo: restore the flipped block from its backup so the
    chain verifies intact again. Completes the 'tamper -> detect -> restore' story."""
    return services.restore_ledger_record(db)


# ---------------------------------------------------------------------------
# Tier-2 on-chain anchoring (Blockchain theme). The authoritative audit trail
# is the true PoW blockchain (backend/blockchain/chain.py); we anchor ITS
# consensus root to a permissioned AuditLog contract on Polygon Amoy.
# Both endpoints are honest: with no RPC/key/contract configured they report
# "not configured" instead of faking an anchor (see onchain.py).
# ---------------------------------------------------------------------------
@router.get("/verify-onchain")
def ledger_verify_onchain(
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN")),
):
    """Prove whether the live cashguard blockchain root matches the on-chain
    audit record. Honest pre-production default: not anchored."""
    from ...blockchain import get_chain
    from ...blockchain.onchain import verify_onchain

    return verify_onchain(get_chain())


@router.post("/anchor")
def ledger_anchor(
    user=Depends(require_auth("I4C_ADMIN")),
):
    """Submit the current cashguard blockchain root to the on-chain AuditLog
    contract (needs LEDGER_ANCHOR_RPC_URL/PRIVATE_KEY/CONTRACT_ADDRESS)."""
    from ...blockchain import get_chain
    from ...blockchain.onchain import anchor_latest

    return anchor_latest(get_chain())