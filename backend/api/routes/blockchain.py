"""
CashGuard AI - blockchain REST API (SIH 2024: Blockchain & Cybersecurity).
    GET    /blockchain                  -> list blocks (immutable chain)
    GET    /blockchain/verify           -> full PoW/hash/linkage verification
    GET    /blockchain/statistics       -> chain stats + validity
    GET    /blockchain/network          -> permissioned peer / consensus status
    POST   /blockchain/record           -> mine a typed record onto the chain
    GET    /blockchain/history/{alert_id} -> chain-of-custody for an alert
    POST   /blockchain/tamper-demo      -> DEMO ONLY (I4C): corrupt a block
    POST   /blockchain/restore          -> DEMO ONLY (I4C): restore from backup
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...blockchain import ChainNetwork, get_chain
from ...security import require_auth

router = APIRouter(prefix="/blockchain", tags=["blockchain"])

_LABEL = "CashGuard true PoW blockchain"


class RecordIn(BaseModel):
    data: dict
    record_type: str
    created_by: str = "api"


@router.get("")
def chain_list(
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
):
    chain = get_chain()
    return {
        "kind": _LABEL,
        "length": chain.get_chain_length(),
        "difficulty": chain.difficulty,
        "blocks": [b.to_dict() for b in chain.get_full_chain()],
    }


@router.get("/verify")
def chain_verify(
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
):
    chain = get_chain()
    ok, issues = chain.verify_chain()
    return {
        "is_valid": ok,
        "issues": issues,
        "length": chain.get_chain_length(),
        "difficulty": chain.difficulty,
        "latest_hash": chain.get_latest_block().hash,
        "method": "full re-compute of SHA-256 + PoW + linkage",
    }


@router.get("/statistics")
def chain_statistics(
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
):
    return get_chain().get_statistics()


@router.get("/network")
def chain_network(
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "I4C_ADMIN")),
):
    return ChainNetwork(get_chain()).network_status()


@router.post("/record")
def chain_record(
    payload: RecordIn,
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
):
    if not payload.record_type or not payload.data:
        raise HTTPException(status_code=422, detail="record_type and data required")
    chain = get_chain()
    block = chain.add_record(payload.data, payload.record_type, created_by=payload.created_by)
    return {
        "mined": True,
        "index": block.index,
        "hash": block.hash,
        "previous_hash": block.previous_hash,
        "nonce": block.nonce,
        "difficulty": chain.difficulty,
        "timestamp": block.timestamp,
    }


@router.get("/history/{alert_id:path}")
def chain_alert_history(
    alert_id: str,
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
):
    history = get_chain().get_alert_history(alert_id)
    return {"alert_id": alert_id, "record_count": len(history), "records": [b.to_dict() for b in history]}


@router.post("/tamper-demo")
def chain_tamper_demo(
    index: int | None = None,
    user=Depends(require_auth("I4C_ADMIN")),
):
    return get_chain().tamper_demo(index)


@router.post("/restore")
def chain_restore(
    index: int | None = None,
    user=Depends(require_auth("I4C_ADMIN")),
):
    return get_chain().restore_demo(index)
