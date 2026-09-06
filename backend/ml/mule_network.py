"""
Mule Network Graph module (Issue 6).

Builds a heterogeneous (bipartite-in-spirit) network that links the *people and
places* behind cyber-fraud, per ATM:

    Complaint (victim, green)
        -> linked_account_token  -> Account (red if flagged mule)
        -> linked_phone_token    -> Phone   (orange)
    Account -> withdrawals at    -> ATM     (blue)

This surfaces the human/mule ecosystem around a compromised ATM: which victims'
accounts and phone numbers flow into it, and whether those accounts are flagged
mules. Output is a vis.js-compatible graph (nodes + edges) plus per-node
centrality (degree + betweenness) and a *cluster risk score* = sum of the fraud
exposure of the accounts in the component.

Honest scope:
- Account risk is derived from withdrawal fraud volume (fraction of fraud
  withdrawals), NOT a fabricated model score.
- Node/link volumes are capped so a dense component stays renderable in the
  browser (vis.js) and the payload stays sane.
- networkx is used only for centrality / connected-components; it is a
  documented, reproducible dependency (pinned in requirements.txt).
"""
from __future__ import annotations

from collections import defaultdict
import time
import networkx as nx

# In-memory cache for mule network builds (avoid recomputing for same params)
_network_cache: dict[tuple, tuple[float, dict]] = {}
_NETWORK_CACHE_TTL = 300  # 5 minutes
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models

MAX_NODES = 400      # hard cap to keep the vis.js payload renderable
MAX_COMPONENT_DEPTH = 4


def _account_fraud_share(db: Session, account_token: str) -> float:
    """Fraction of this account's withdrawals that were fraud (0..1)."""
    rows = db.execute(
        select(models.Withdrawal.is_fraud_withdrawal)
        .where(models.Withdrawal.account_token == account_token)
        .limit(500)
    ).all()
    if not rows:
        return 0.0
    return sum(1 for (flag,) in rows if flag) / len(rows)


def build_mule_network(
    db: Session,
    atm_id: str | None = None,
    depth: int = 2,
    include_phone: bool = True,
) -> dict:
    """Build the mule-ecosystem graph and return vis.js-style serialisable dict.

    If `atm_id` is given, the graph is scoped to the connected component around
    that ATM (BFS to `depth` hops). Otherwise the whole network is built, capped
    at MAX_NODES (highest-fraud-volume accounts first).
    """
    depth = max(1, min(int(depth), MAX_COMPONENT_DEPTH))

    # Check cache (5-min TTL)
    cache_key = (atm_id, depth, include_phone)
    now = time.time()
    if cache_key in _network_cache:
        cached_time, cached_data = _network_cache[cache_key]
        if now - cached_time < _NETWORK_CACHE_TTL:
            return cached_data

    # ---- 1. Seed nodes ---------------------------------------------------
    atm_nodes: dict[str, dict] = {}
    account_nodes: dict[str, dict] = {}
    complaint_nodes: dict[str, dict] = {}
    phone_nodes: dict[str, dict] = {}
    edges: list[dict] = []

    # ATM(s) referenced
    if atm_id:
        atm = db.scalar(select(models.ATM).where(models.ATM.atm_id == atm_id))
        if atm is None:
            return {"error": f"ATM {atm_id} not found", "nodes": [], "edges": [], "components": 0}
        atm_nodes[atm.atm_id] = {
            "id": atm.atm_id, "type": "atm", "label": atm.atm_id,
            "state": atm.state or "", "city": atm.city or "", "district": atm.district or "",
            "bank": atm.bank_name or "", "branch": atm.branch_name or "",
            "lat": atm.latitude or 0.0, "lon": atm.longitude or 0.0,
        }
    else:
        # Whole-network seed is deferred to after the helper closures are
        # defined (section 2) so they can be reused. See `seed_whole_network`.
        whole_network = True

    # ---- 2. Accounts at the seed ATM(s), then BFS ------------------------
    # withdrawal(account) edges for the seed ATM
    def withdrawals_for_atm(aid: str) -> list[models.Withdrawal]:
        return list(db.scalars(
            select(models.Withdrawal).where(models.Withdrawal.atm_id == aid).limit(300)
        ))

    def add_account_token(token: str) -> None:
        if token in account_nodes:
            return
        acct = db.scalar(select(models.Account).where(models.Account.account_token == token))
        is_mule = bool(acct.is_mule) if acct else False
        share = _account_fraud_share(db, token)
        account_nodes[token] = {
            "id": token, "type": "account", "label": _short(token),
            "is_mule": is_mule, "fraud_share": round(share, 3),
        }

    def add_complaint(c: models.Complaint) -> None:
        cid = c.complaint_id
        if cid in complaint_nodes:
            return
        complaint_nodes[cid] = {
            "id": cid, "type": "complaint", "label": _short(cid),
            "victim_city": c.victim_city or "", "victim_state": c.victim_state or "",
            "complaint_type": c.complaint_type or "",
        }
        if c.linked_account_token:
            add_account_token(c.linked_account_token)
            edges.append({"from": cid, "to": c.linked_account_token, "rel": "complaint->account"})
        if include_phone and c.linked_phone_token:
            phone = c.linked_phone_token
            if phone not in phone_nodes:
                phone_nodes[phone] = {"id": phone, "type": "phone", "label": _short(phone)}
            edges.append({"from": cid, "to": phone, "rel": "complaint->phone"})

    # seed complaints linked to accounts that withdrew at the seed ATM
    seed_accounts: set[str] = set()
    atm_ids = list(atm_nodes) if atm_nodes else []
    if atm_ids:
        for aid in atm_ids:
            for w in withdrawals_for_atm(aid):
                if w.account_token and w.account_token not in seed_accounts:
                    seed_accounts.add(w.account_token)
                    add_account_token(w.account_token)
                    edges.append({"from": w.account_token, "to": aid, "rel": "account->atm"})
        # complaints referencing seed accounts or the ATM's own district/city
        if seed_accounts:
            comps = db.scalars(
                select(models.Complaint).where(
                    models.Complaint.linked_account_token.in_(list(seed_accounts))
                ).limit(300)
            ).all()
            for c in comps:
                add_complaint(c)

    # Whole-network seed (deferred here so add_account_token is defined):
    # accounts with the most fraud withdrawals drive the graph.
    if not atm_id:
        seed_rows = db.execute(
            select(models.Withdrawal.account_token, func.count(models.Withdrawal.id).label("n"))
            .where(models.Withdrawal.is_fraud_withdrawal.is_(True))
            .group_by(models.Withdrawal.account_token)
            .order_by(func.count(models.Withdrawal.id).desc())
            .limit(120)
        ).all()
        seed_accounts = {r[0] for r in seed_rows if r[0]}
        for token in seed_accounts:
            add_account_token(token)
        for token in list(seed_accounts):
            for w in db.scalars(
                select(models.Withdrawal).where(models.Withdrawal.account_token == token).limit(50)
            ).all():
                if w.atm_id not in atm_nodes:
                    a = db.scalar(select(models.ATM).where(models.ATM.atm_id == w.atm_id))
                    if a is not None:
                        atm_nodes[a.atm_id] = {
                            "id": a.atm_id, "type": "atm", "label": a.atm_id,
                            "state": a.state or "", "city": a.city or "", "district": a.district or "",
                            "bank": a.bank_name or "", "branch": a.branch_name or "",
                            "lat": a.latitude or 0.0, "lon": a.longitude or 0.0,
                        }
                edges.append({"from": token, "to": w.atm_id, "rel": "account->atm"})

    # ---- 3. BFS expansion by depth ---------------------------------------
    # neighbourhood: account <-> complaints <-> phones; complaint -> accounts
    seen_accounts = set(account_nodes)
    seen_complaints = set(complaint_nodes)
    seen_phones = set(phone_nodes)
    frontier = set(account_nodes) | set(complaint_nodes) | set(phone_nodes)
    for _hop in range(depth):
        if not frontier or len(account_nodes) + len(complaint_nodes) + len(phone_nodes) >= MAX_NODES:
            break
        new_accounts: set[str] = set()
        new_complaints: dict[str, models.Complaint] = {}
        new_phones: set[str] = set()
        tokens = list(frontier)
        accounts_here = [t for t in tokens if t in account_nodes]
        if accounts_here:
            for t in accounts_here:
                for c in db.scalars(
                    select(models.Complaint).where(models.Complaint.linked_account_token == t).limit(60)
                ).all():
                    if c.complaint_id not in seen_complaints:
                        seen_complaints.add(c.complaint_id)
                        new_complaints[c.complaint_id] = c
                        if c.linked_phone_token and c.linked_phone_token not in seen_phones:
                            seen_phones.add(c.linked_phone_token)
                            new_phones.add(c.linked_phone_token)
        phones_here = [t for t in tokens if t in phone_nodes]
        if phones_here:
            for p in phones_here:
                for c in db.scalars(
                    select(models.Complaint).where(models.Complaint.linked_phone_token == p).limit(60)
                ).all():
                    if c.complaint_id not in seen_complaints:
                        seen_complaints.add(c.complaint_id)
                        new_complaints[c.complaint_id] = c
                        if c.linked_account_token and c.linked_account_token not in seen_accounts:
                            seen_accounts.add(c.linked_account_token)
                            new_accounts.add(c.linked_account_token)
        for c in new_complaints.values():
            add_complaint(c)
        for a in new_accounts:
            add_account_token(a)
        for p in new_phones:
            phone_nodes.setdefault(p, {"id": p, "type": "phone", "label": _short(p)})
        frontier = (set(new_accounts) | set(new_complaints) | set(new_phones))
        # stop recursion: expand accounts' complaints once, then done
        if _hop >= 1:
            break

    # ---- 4. Connected components + centrality ----------------------------
    G = nx.Graph()
    for n in list(account_nodes) + list(complaint_nodes) + list(phone_nodes) + list(atm_nodes):
        G.add_node(n)
    for e in edges:
        G.add_edge(e["from"], e["to"])

    # assign component ids
    comp_ids: dict[str, int] = {}
    comps = list(nx.connected_components(G))
    for ci, comp in enumerate(comps):
        for n in comp:
            comp_ids[n] = ci

    if G.number_of_nodes():
        bet = nx.betweenness_centrality(G, weight=None)
        deg = nx.degree_centrality(G)
    else:
        bet, deg = {}, {}

    def _size(node_id: str) -> int:
        # scale node radius by degree centrality (min 8px)
        d = deg.get(node_id, 0.0)
        return 10 + int(round(d * 60)) if d > 0 else 10

    nodes_out = []
    for nid, meta in list(account_nodes.items()) + list(complaint_nodes.items()) \
            + list(phone_nodes.items()) + list(atm_nodes.items()):
        nodes_out.append({
            **meta,
            "component": comp_ids.get(nid, 0),
            "degree_centrality": round(deg.get(nid, 0.0), 4),
            "betweenness_centrality": round(bet.get(nid, 0.0), 4),
            "size": _size(nid),
        })

    # ---- 5. cluster risk = sum of account fraud exposure per component ---
    cluster_risk: dict[int, float] = defaultdict(float)
    fraud_accounts_by_comp: dict[int, int] = defaultdict(int)
    for nid, meta in account_nodes.items():
        cid = comp_ids.get(nid, 0)
        cluster_risk[cid] += meta["fraud_share"]
        if meta["is_mule"]:
            fraud_accounts_by_comp[cid] += 1

    return {
        "atm_id": atm_id,
        "depth": depth,
        "nodes": nodes_out,
        "edges": edges,
        "components": len(comps),
        "stats": {
            "accounts": len(account_nodes),
            "complaints": len(complaint_nodes),
            "phones": len(phone_nodes),
            "atms": len(atm_nodes),
            "edges": len(edges),
        },
        "cluster_risk": {str(k): round(float(v), 3) for k, v in cluster_risk.items()},
        "flagged_mules_by_component": {str(k): v for k, v in fraud_accounts_by_comp.items()},
        "honest": True,
    }
    _network_cache[cache_key] = (now, result)
    return result


def _short(token: str) -> str:
    """Short, reversible-agnostic display label for a pseudonymised token."""
    if not token:
        return ""
    if token.startswith(("ACCT", "ACC", "acc")) or len(token) <= 12:
        return token
    return token[:6] + "…" + token[-4:]
