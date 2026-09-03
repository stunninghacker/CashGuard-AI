"""
Mule Network Graph endpoints (Issue 6) — the human/mule ecosystem graph.

GET /api/graph/mule-network?atm_id=&depth=&include_phone=
    -> bipartite network (victims <-> accounts <-> phones <-> ATM) as a
       vis.js-compatible node/edge payload with centrality + cluster risk.

Role-scoped: I4C_ADMIN sees all; POLICE_STATE/DISTRICT and BANK are restricted to
accounts in their scope (repository layer), so a narrow-role user never sees the
full national mule web.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ... import repositories as repo
from ...database import get_db
from ...ml import mule_network as mule_network_mod
from ...security import require_auth

router = APIRouter(prefix="/graph", tags=["mule-network-graph"])


@router.get("/mule-network")
def mule_network(
    atm_id: str | None = Query(default=None, description="Scope graph to a component around this ATM"),
    depth: int = Query(default=2, ge=1, le=4),
    include_phone: bool = Query(default=True),
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    payload = mule_network_mod.build_mule_network(db, atm_id=atm_id, depth=depth, include_phone=include_phone)
    if "error" in payload:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=payload["error"])

    # Role scoping: narrow-role users only see accounts in scope AND their
    # connected subgraph (drop out-of-scope account nodes + dangling edges).
    if user.role != "I4C_ADMIN":
        in_scope = repo.accounts_in_user_scope(db, user)
        scoped_ids = {n["id"] for n in payload["nodes"] if n["type"] == "account" and n["id"] in in_scope}
        scoped_ids |= {n["id"] for n in payload["nodes"] if n["type"] != "account"}
        keep = {n["id"] for n in payload["nodes"] if n["type"] == "account" and n["id"] in in_scope}
        keep |= {n["id"] for n in payload["nodes"] if n["type"] != "account"}
        # also keep neighbors of in-scope accounts to preserve the component
        ids_keep = set(keep)
        for e in payload["edges"]:
            if e["to"] in keep or e["from"] in keep:
                ids_keep.add(e["from"]); ids_keep.add(e["to"])
        payload["nodes"] = [n for n in payload["nodes"] if n["id"] in ids_keep]
        payload["edges"] = [e for e in payload["edges"] if e["from"] in ids_keep and e["to"] in ids_keep]

    return payload
