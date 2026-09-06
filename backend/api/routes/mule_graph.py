"""
Money-trail / terminal cash-out graph endpoints (deliverable: graph module).

GET /api/mule-graph/terminal-nodes  -> top-K terminal-risk accounts (role-scoped)
GET /api/mule-graph/trail/{token}   -> money-trail chains + edges for a token

Role-scoped: I4C_ADMIN sees all; POLICE_STATE sees state; POLICE_DISTRICT sees district;
BANK sees own. Scoping is enforced in the repository layer (like risk-scores).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from ... import repositories as repo, services
from ...database import get_db
from ...ml import mule_graph
from ...security import require_auth

router = APIRouter(prefix="/mule-graph", tags=["mule-graph"])


@router.get("/terminal-nodes")
def terminal_nodes(
    k: int = Query(default=20, ge=1, le=200),
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    """Top-K accounts by terminal cash-out risk from the transfer graph.
    Uses the same 30-day trailing window as the live dashboard."""
    # Scope filtering via repo: the repo layer returns only accounts in user's scope
    in_scope = repo.accounts_in_user_scope(db, user)

    from datetime import datetime, timedelta
    as_of = services.resolve_as_of(db)

    from ...database import engine
    graph, ranks, risk = mule_graph._get_or_build_graph(engine, as_of, window_days=30)
    if not graph:
        return {"nodes": [], "note": "no transfers in window"}

    scoped_risk = {acc: risk.get(acc, 0.0) for acc in in_scope if acc in risk}
    top = sorted(scoped_risk.items(), key=lambda kv: -kv[1])[:k]

    return {
        "as_of": as_of.isoformat(),
        "window_days": 30,
        "nodes": [
            {"account_token": acc, "terminal_risk": round(r, 4)}
            for acc, r in top
        ],
    }


@router.get("/trail/{account_token}")
def money_trail(
    account_token: str = Path(..., description="Pseudonymised account token"),
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    """Money-trail for a specific account: chains (entry->...->terminal) and edges.
    Role-scoped: user must have access to the account_token."""
    in_scope = repo.accounts_in_user_scope(db, user)
    if account_token not in in_scope:
        raise HTTPException(status_code=403, detail="Account not in your scope")

    from datetime import timedelta
    from ...database import engine

    as_of = services.resolve_as_of(db)
    trail = mule_graph.money_trail(engine, account_token, as_of, window_days=30)

    return {
        "account_token": account_token,
        "as_of": as_of.isoformat(),
        "window_days": 30,
        **trail,
    }