"""
Money-trail / mule-account graph module (mandate: "mule-account/money-trail graph").

Turns the synthetic (or, in production, CFCFRMS/bank) account-to-account transfer
edges into a directed graph and flags *likely cash-out terminal nodes* — accounts
that stand at the end of a layering chain (many inbound transfers, little/no
outbound, deep in the chain, high inbound velocity) and are therefore most likely
to be the account that withdraws cash at an ATM. This is a graph-centrality +
anomaly signal, exactly the second half of the predictive mandate.

Implementation is pure-Python (no networkx) to keep the demo dependency-light and
fully auditable: adjacency maps + power-iteration PageRank + simple centrality /
anomaly arithmetic. `networkx` (or a real graph store) is an optional production
upgrade — see MULE_GRAPH.md.

No-leakage discipline: every query takes an `as_of` timestamp and only uses edges
STRICTLY BEFORE it, so a graph built at forecast time cannot see the future.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy.engine import Engine

DEFAULT_WINDOW_DAYS = 30  # build the graph from transfers in the last N days


def load_transfers(engine: Engine, as_of: datetime, window_days: int = DEFAULT_WINDOW_DAYS) -> pd.DataFrame:
    """Read transfer edges before `as_of` within the trailing window (no leakage)."""
    cutoff = as_of - timedelta(days=window_days)
    q = (
        "SELECT from_token, to_token, amount, timestamp FROM transfers "
        "WHERE timestamp < :as_of AND timestamp >= :cutoff"
    )
    return pd.read_sql(q, engine, params={"as_of": as_of, "cutoff": cutoff})


def build_graph(df: pd.DataFrame) -> dict[str, Any]:
    """Build adjacency structures from an edge dataframe."""
    src2dst: dict[str, list[str]] = {}
    dst2src: dict[str, list[str]] = {}
    inflow: dict[str, float] = {}
    for _, r in df.iterrows():
        s, t = str(r["from_token"]), str(r["to_token"])
        src2dst.setdefault(s, []).append(t)
        dst2src.setdefault(t, []).append(s)
        inflow[t] = inflow.get(t, 0.0) + float(r["amount"])
    return {"src2dst": src2dst, "dst2src": dst2src, "inflow": inflow}


def pagerank(graph: dict[str, Any], damping: float = 0.85, iters: int = 40) -> dict[str, float]:
    """Power-iteration PageRank over the directed transfer graph (pure Python)."""
    nodes = set(graph["src2dst"]) | set(graph["dst2src"])
    n = max(len(nodes), 1)
    rank = {nd: 1.0 / n for nd in nodes}
    for _ in range(iters):
        new_rank: dict[str, float] = {}
        dangling = sum(r for nd, r in rank.items() if not graph["src2dst"].get(nd))
        for nd in nodes:
            contrib = 0.0
            for src in graph["dst2src"].get(nd, []):
                out_deg = len(graph["src2dst"].get(src, []))
                if out_deg:
                    contrib += rank[src] / out_deg
            new_rank[nd] = (1.0 - damping) / n + damping * (contrib + dangling / n)
        rank = new_rank
    mx = max(rank.values()) if rank else 1.0
    return {nd: r / mx for nd, r in rank.items()}  # normalised to [0,1]


def chain_depth_of(graph: dict[str, Any], node: str) -> int:
    """Depth of the longest directed path ending at `node` (layering depth).

    BFS backwards through inbound edges; entry/source nodes have depth 0.
    """
    seen = {node}
    frontier = [node]
    depth = 0
    while frontier:
        nxt: list[str] = []
        for nd in frontier:
            for src in graph["dst2src"].get(nd, []):
                if src not in seen:
                    seen.add(src)
                    nxt.append(src)
        if nxt:
            depth += 1
        frontier = nxt
    return depth


def terminal_cashout_risk(
    graph: dict[str, Any],
    ranks: dict[str, float] | None = None,
) -> dict[str, float]:
    """
    Per-account *terminal cash-out* score in [0,1] — the anomaly/centrality blend:

        risk = w1*in_degree_norm + w2*terminal_ratio + w3*chain_depth_norm
               + w4*page_rank + w5*inflow_norm

    where terminal_ratio = high for nodes with many inbound edges and little/no
    outbound (money stops here -> cash-out). Nodes with a large out-degree are
    penalised (they're onward routers, not cash-out terminals).
    """
    if ranks is None:
        ranks = pagerank(graph)
    nodes = set(graph["src2dst"]) | set(graph["dst2src"])
    if not nodes:
        return {}

    in_deg = {nd: len(graph["dst2src"].get(nd, [])) for nd in nodes}
    out_deg = {nd: len(graph["src2dst"].get(nd, [])) for nd in nodes}
    inflow = graph["inflow"]

    def _norm(vals: dict, key) -> dict:
        mx = max(vals.values()) if vals else 1.0
        return {k: v / mx for k, v in vals.items()} if mx else vals

    in_n = _norm(in_deg, None)
    in_flow_n = _norm(inflow, None)
    max_depth = max((chain_depth_of(graph, nd) for nd in nodes), default=0) or 1

    w = (0.30, 0.25, 0.15, 0.15, 0.15)
    out: dict[str, float] = {}
    for nd in nodes:
        # terminal_ratio: inbound-heavy AND outbound-light
        denom = (in_deg[nd] + out_deg[nd]) or 1
        terminal_ratio = in_deg[nd] / denom
        if out_deg[nd] == 0:
            terminal_ratio = min(terminal_ratio + 0.15, 1.0)  # money stops here
        depth_n = min(chain_depth_of(graph, nd) / max_depth, 1.0)
        score = (
            w[0] * in_n[nd]
            + w[1] * terminal_ratio
            + w[2] * depth_n
            + w[3] * ranks.get(nd, 0.0)
            + w[4] * in_flow_n.get(nd, 0.0)
        )
        out[nd] = round(min(score, 1.0), 4)
    return out


def top_terminal_nodes(
    engine: Engine,
    as_of: datetime,
    limit: int = 50,
    window_days: int = DEFAULT_WINDOW_DAYS,
    min_in_degree: int = 1,
) -> list[dict[str, Any]]:
    """
    Rank accounts by terminal cash-out risk. Returns sorted list of dicts with
    node metrics so the LEA case view can show the ranked cash-out points.
    """
    df = load_transfers(engine, as_of, window_days)
    graph = build_graph(df)
    ranks = pagerank(graph)
    risk = terminal_cashout_risk(graph, ranks)
    nodes = set(graph["src2dst"]) | set(graph["dst2src"])

    rows = []
    for nd in nodes:
        in_deg = len(graph["dst2src"].get(nd, []))
        if in_deg < min_in_degree:
            continue
        rows.append(
            {
                "account_token": nd,
                "terminal_risk": risk[nd],
                "in_degree": in_deg,
                "out_degree": len(graph["src2dst"].get(nd, [])),
                "inflow_inr": round(graph["inflow"].get(nd, 0.0), 2),
                "chain_depth": chain_depth_of(graph, nd),
                "page_rank": round(ranks.get(nd, 0.0), 4),
            }
        )
    rows.sort(key=lambda r: -r["terminal_risk"])
    return rows[:limit]


def money_trail(engine: Engine, account_token: str, as_of: datetime, window_days: int = DEFAULT_WINDOW_DAYS) -> dict[str, Any]:
    """Return the layering path(s) that feed `account_token` (LEA case view)."""
    df = load_transfers(engine, as_of, window_days)
    graph = build_graph(df)
    ranks = pagerank(graph)
    risk = terminal_cashout_risk(graph, ranks)

    # walk backwards to reconstruct inbound chains (source -> ... -> account)
    chains: list[list[str]] = []

    def _dfs(nd: str, path: list[str]) -> None:
        preds = graph["dst2src"].get(nd, [])
        if not preds:
            chains.append(path[::-1])  # path is [nd, ..., source]; reverse to source-first
            return
        for p in preds[:6]:  # cap branching for readability
            _dfs(p, path + [p])

    _dfs(account_token, [account_token])

    # export edges for a lightweight cytoscape-style rendering payload
    edges = [
        {"source": str(r["from_token"]), "target": str(r["to_token"]), "amount": float(r["amount"])}
        for _, r in df.iterrows()
        if account_token in (str(r["from_token"]), str(r["to_token"]))
        or str(r["from_token"]) in set(sum(chains, []))
        and str(r["to_token"]) in set(sum(chains, []))
    ]
    return {
        "account_token": account_token,
        "terminal_risk": risk.get(account_token, 0.0),
        "in_degree": len(graph["dst2src"].get(account_token, [])),
        "out_degree": len(graph["src2dst"].get(account_token, [])),
        "inflow_inr": round(graph["inflow"].get(account_token, 0.0), 2),
        "chain_depth": chain_depth_of(graph, account_token),
        "chains": chains[:8],
        "edges": edges[:60],
    }
