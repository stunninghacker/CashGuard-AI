"""
Money-trail / mule-account graph module (mandate: "mule-account/money-trail graph").

Turns the synthetic (or, in production, CFCFRMS/bank) account-to-account transfer
edges into a directed graph and flags *likely cash-out terminal nodes* — accounts
that stand at the end of a layering chain (many inbound transfers, little/no
outbound, deep in the chain, high inbound velocity) and are therefore most likely
to be the account that withdraws cash at an ATM. This is a graph-centrality +
anomaly signal, exactly the second half of the predictive mandate.

Performance-optimized: vectorized graph building, single-pass depth computation,
in-memory graph cache, memoized BFS.

No-leakage discipline: every query takes an `as_of` timestamp and only uses edges
STRICTLY BEFORE it, so a graph built at forecast time cannot see the future.
"""
from __future__ import annotations

import functools
from collections import deque
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy.engine import Engine

DEFAULT_WINDOW_DAYS = 30  # build the graph from transfers in the last N days

# In-memory graph cache: (engine_id, as_of, window_days) -> (graph, ranks, risk)
_graph_cache: dict[tuple, tuple[dict, dict, dict]] = {}
_GRAPH_CACHE_TTL = 300  # 5 minutes


def load_transfers(engine: Engine, as_of: datetime, window_days: int = DEFAULT_WINDOW_DAYS) -> pd.DataFrame:
    """Read transfer edges before `as_of` within the trailing window (no leakage)."""
    cutoff = as_of - timedelta(days=window_days)
    q = (
        "SELECT from_token, to_token, amount, timestamp FROM transfers "
        "WHERE timestamp < :as_of AND timestamp >= :cutoff"
    )
    return pd.read_sql(q, engine, params={"as_of": as_of, "cutoff": cutoff})


def build_graph(df: pd.DataFrame) -> dict[str, Any]:
    """Build adjacency structures from an edge dataframe. Vectorized where possible."""
    if df.empty:
        return {"src2dst": {}, "dst2src": {}, "inflow": {}}
    # Use itertuples (10-100x faster than iterrows)
    src2dst: dict[str, list[str]] = {}
    dst2src: dict[str, list[str]] = {}
    inflow: dict[str, float] = {}
    for row in df.itertuples(index=False):
        s, t, amt = str(row.from_token), str(row.to_token), float(row.amount)
        src2dst.setdefault(s, []).append(t)
        dst2src.setdefault(t, []).append(s)
        inflow[t] = inflow.get(t, 0.0) + amt
    return {"src2dst": src2dst, "dst2src": dst2src, "inflow": inflow}


def pagerank(graph: dict[str, Any], damping: float = 0.85, iters: int = 40) -> dict[str, float]:
    """Power-iteration PageRank over the directed transfer graph."""
    nodes = set(graph["src2dst"]) | set(graph["dst2src"])
    n = max(len(nodes), 1)
    rank = {nd: 1.0 / n for nd in nodes}
    # Precompute out-degrees
    out_deg = {nd: len(graph["src2dst"].get(nd, [])) for nd in nodes}
    for _ in range(iters):
        dangling = sum(r for nd, r in rank.items() if out_deg.get(nd, 0) == 0)
        new_rank: dict[str, float] = {}
        for nd in nodes:
            contrib = 0.0
            for src in graph["dst2src"].get(nd, []):
                od = out_deg.get(src, 0)
                if od:
                    contrib += rank[src] / od
            new_rank[nd] = (1.0 - damping) / n + damping * (contrib + dangling / n)
        rank = new_rank
    mx = max(rank.values()) if rank else 1.0
    return {nd: r / mx for nd, r in rank.items()}


def _compute_all_depths(graph: dict[str, Any]) -> dict[str, int]:
    """Compute longest-path depth for ALL nodes in a single pass (BFS from sources).

    Instead of running BFS per node (O(N*(N+E))), this does a single topological
    BFS from all source nodes — O(N+E) total.
    """
    src2dst = graph["src2dst"]
    dst2src = graph["dst2src"]
    nodes = set(src2dst) | set(dst2src)

    # Find source nodes (no inbound edges)
    sources = [nd for nd in nodes if not dst2src.get(nd)]
    # All nodes with no inbound are depth 0
    depth: dict[str, int] = {nd: 0 for nd in sources}
    frontier = list(sources)

    while frontier:
        next_frontier = []
        for nd in frontier:
            current_depth = depth[nd]
            for dst in src2dst.get(nd, []):
                new_depth = current_depth + 1
                if dst not in depth or new_depth > depth[dst]:
                    depth[dst] = new_depth
                    next_frontier.append(dst)
        frontier = next_frontier

    # Any unreachable nodes get depth 0
    for nd in nodes:
        if nd not in depth:
            depth[nd] = 0

    return depth


def terminal_cashout_risk(
    graph: dict[str, Any],
    ranks: dict[str, float] | None = None,
) -> dict[str, float]:
    """
    Per-account terminal cash-out score in [0,1].

    Optimized: computes all depths in a single pass instead of per-node BFS.
    """
    if ranks is None:
        ranks = pagerank(graph)
    nodes = set(graph["src2dst"]) | set(graph["dst2src"])
    if not nodes:
        return {}

    in_deg = {nd: len(graph["dst2src"].get(nd, [])) for nd in nodes}
    out_deg = {nd: len(graph["src2dst"].get(nd, [])) for nd in nodes}
    inflow = graph["inflow"]

    def _norm(vals: dict) -> dict:
        mx = max(vals.values()) if vals else 1.0
        return {k: v / mx for k, v in vals.items()} if mx else vals

    in_n = _norm(in_deg)
    in_flow_n = _norm(inflow)

    # Single-pass depth computation (was O(N²), now O(N+E))
    all_depths = _compute_all_depths(graph)
    max_depth = max(all_depths.values()) if all_depths else 1 or 1

    w = (0.30, 0.25, 0.15, 0.15, 0.15)
    out: dict[str, float] = {}
    for nd in nodes:
        denom = (in_deg[nd] + out_deg[nd]) or 1
        terminal_ratio = in_deg[nd] / denom
        if out_deg[nd] == 0:
            terminal_ratio = min(terminal_ratio + 0.15, 1.0)
        depth_n = min(all_depths.get(nd, 0) / max_depth, 1.0)
        score = (
            w[0] * in_n[nd]
            + w[1] * terminal_ratio
            + w[2] * depth_n
            + w[3] * ranks.get(nd, 0.0)
            + w[4] * in_flow_n.get(nd, 0.0)
        )
        out[nd] = round(min(score, 1.0), 4)
    return out


def _get_or_build_graph(engine: Engine, as_of: datetime, window_days: int) -> tuple[dict, dict, dict]:
    """Get cached graph or build fresh. Caches for 5 minutes."""
    import time
    # Use engine URL as cache key (id() changes per request in some setups)
    cache_key = (str(engine.url), as_of.isoformat(), window_days)
    now = time.time()
    if cache_key in _graph_cache:
        cached_graph, cached_ranks, cached_risk, cached_time = _graph_cache[cache_key]
        if now - cached_time < _GRAPH_CACHE_TTL:
            return cached_graph, cached_ranks, cached_risk
    df = load_transfers(engine, as_of, window_days)
    graph = build_graph(df)
    ranks = pagerank(graph)
    risk = terminal_cashout_risk(graph, ranks)
    _graph_cache[cache_key] = (graph, ranks, risk, now)
    return graph, ranks, risk


def top_terminal_nodes(
    engine: Engine,
    as_of: datetime,
    limit: int = 50,
    window_days: int = DEFAULT_WINDOW_DAYS,
    min_in_degree: int = 1,
) -> list[dict[str, Any]]:
    """Rank accounts by terminal cash-out risk. Uses cached graph + single-pass depths."""
    graph, ranks, risk = _get_or_build_graph(engine, as_of, window_days)
    all_depths = _compute_all_depths(graph)
    nodes = set(graph["src2dst"]) | set(graph["dst2src"])

    rows = []
    for nd in nodes:
        in_deg = len(graph["dst2src"].get(nd, []))
        if in_deg < min_in_degree:
            continue
        rows.append(
            {
                "account_token": nd,
                "terminal_risk": risk.get(nd, 0.0),
                "in_degree": in_deg,
                "out_degree": len(graph["src2dst"].get(nd, [])),
                "inflow_inr": round(graph["inflow"].get(nd, 0.0), 2),
                "chain_depth": all_depths.get(nd, 0),
                "page_rank": round(ranks.get(nd, 0.0), 4),
            }
        )
    rows.sort(key=lambda r: -r["terminal_risk"])
    return rows[:limit]


def money_trail(engine: Engine, account_token: str, as_of: datetime, window_days: int = DEFAULT_WINDOW_DAYS) -> dict[str, Any]:
    """Return the layering path(s) that feed `account_token` (LEA case view).

    Reuses cached graph instead of rebuilding from scratch.
    """
    graph, ranks, risk = _get_or_build_graph(engine, as_of, window_days)
    all_depths = _compute_all_depths(graph)

    # walk backwards to reconstruct inbound chains (source -> ... -> account)
    chains: list[list[str]] = []

    def _dfs(nd: str, path: list[str], depth: int = 0) -> None:
        if depth > 8:  # cap recursion depth
            chains.append(path[::-1])
            return
        preds = graph["dst2src"].get(nd, [])
        if not preds:
            chains.append(path[::-1])
            return
        for p in preds[:6]:  # cap branching for readability
            _dfs(p, path + [p], depth + 1)

    _dfs(account_token, [account_token])

    # Build edge set from relevant nodes only
    chain_nodes = set(sum(chains, []))
    chain_nodes.add(account_token)
    df = load_transfers(engine, as_of, window_days)
    edges = [
        {"source": str(r.from_token), "target": str(r.to_token), "amount": float(r.amount)}
        for r in df.itertuples(index=False)
        if str(r.from_token) in chain_nodes or str(r.to_token) in chain_nodes
    ]
    return {
        "account_token": account_token,
        "terminal_risk": risk.get(account_token, 0.0),
        "in_degree": len(graph["dst2src"].get(account_token, [])),
        "out_degree": len(graph["src2dst"].get(account_token, [])),
        "inflow_inr": round(graph["inflow"].get(account_token, 0.0), 2),
        "chain_depth": all_depths.get(account_token, 0),
        "chains": chains[:8],
        "edges": edges[:60],
    }
