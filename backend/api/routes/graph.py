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
    limit: int = Query(default=100, ge=10, le=500, description="Max nodes to return"),
    user=Depends(require_auth("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")),
    db: Session = Depends(get_db),
):
    # Use cached build_mule_network — RBAC scoping for non-I4C is done in-place
    payload = mule_network_mod.build_mule_network(db, atm_id=atm_id, depth=depth, include_phone=include_phone)
    if "error" in payload:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=payload["error"])

    # Role scoping: narrow-role users only see accounts in scope AND their
    # connected subgraph (drop out-of-scope account nodes + dangling edges).
    if user.role != "I4C_ADMIN":
        in_scope = set(repo.accounts_in_user_scope(db, user))
        # Shallow copy nodes/edges to avoid mutating cache
        payload = {**payload, "nodes": list(payload["nodes"]), "edges": list(payload["edges"])}
        scoped_ids = {n["id"] for n in payload["nodes"] if n["type"] == "account" and n["id"] in in_scope}
        scoped_ids |= {n["id"] for n in payload["nodes"] if n["type"] != "account"}
        ids_keep = set(scoped_ids)
        for e in payload["edges"]:
            if e["to"] in ids_keep or e["from"] in ids_keep:
                ids_keep.add(e["from"]); ids_keep.add(e["to"])
        payload["nodes"] = [n for n in payload["nodes"] if n["id"] in ids_keep]
        payload["edges"] = [e for e in payload["edges"] if e["from"] in ids_keep and e["to"] in ids_keep]

    # Limit nodes to prevent huge payloads
    if len(payload.get("nodes", [])) > limit:
        # Keep highest-risk nodes
        nodes = payload["nodes"]
        nodes.sort(key=lambda n: n.get("risk", 0), reverse=True)
        keep_ids = {n["id"] for n in nodes[:limit]}
        payload["nodes"] = [n for n in nodes if n["id"] in keep_ids]
        payload["edges"] = [e for e in payload["edges"] if e["from"] in keep_ids and e["to"] in keep_ids]

    return payload
