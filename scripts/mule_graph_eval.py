"""
Standalone backtest for the money-trail / terminal cash-out graph signal.

Question answered honestly: if we rank accounts by terminal cash-out risk from
the transfer graph (built ONLY on edges before the split), how often is a top-K
account the SAME account that a few days later performs a real fraud ATM
cash-out? This is the graph module's own hit-rate / precision-at-K — the mandate's
"flag high-risk terminal nodes (likely cash-out points)" evaluated with a
numerical metric against the synthetic truth labels (fraud withdrawal rows).

Baselines for honesty:
  * random        — chance
  * by_inflow     — "busiest recipient" heuristic (graph volume only)
  * by_in_degree  — "most linked recipient" heuristic
Terminal-risk must beat these on precision@K / recall@K to prove the centrality +
anomaly blend adds value over simple graph volume or degree.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from backend.database import engine  # noqa: E402
from backend.ml import mule_graph  # noqa: E402

WINDOW_DAYS = 30         # graph built from transfers in the trailing 30 days before split
FORECAST_DAYS = 5        # check who cashes out in the 5 days AFTER the graph's as-of
K_VALUES = [20, 50, 100]


def _fraud_cashout_accounts(split: datetime) -> set[str]:
    """Accounts that performed a fraud ATM withdrawal in (split, split+FORECAST_DAYS]."""
    end = split + timedelta(days=FORECAST_DAYS)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT DISTINCT account_token FROM withdrawals "
                "WHERE is_fraud_withdrawal = 1 AND timestamp > :split AND timestamp <= :end"
            ),
            {"split": split, "end": end},
        ).scalars().all()
    return set(rows)


def _precision_at_k(ranked: list, positives: set, k: int) -> float:
    top = [r["account_token"] for r in ranked[:k]]
    if not top:
        return 0.0
    return sum(1 for t in top if t in positives) / len(top)


def _recall_at_k(ranked: list, positives: set, k: int) -> float:
    top = [r["account_token"] for r in ranked[:k]]
    if not positives:
        return 0.0
    return sum(1 for t in top if t in positives) / len(positives)


def main() -> None:
    # Split AS-OF = data-end minus the forecast horizon, so the forecast window of
    # FORECAST_DAYS actually sits INSIDE the synthetic timeline and has real fraud
    # cash-outs to hit. (Using "today" put the split at the very last day of data,
    # leaving an empty forecast window — a vacuous backtest.)
    with engine.connect() as conn:
        last_ts = conn.execute(
            text("SELECT MAX(timestamp) FROM withdrawals")
        ).scalar()
    # timestamp may be int (epoch) or ISO string
    if isinstance(last_ts, (int, float)):
        as_of = datetime.fromtimestamp(last_ts) - timedelta(days=FORECAST_DAYS)
    else:
        as_of = datetime.fromisoformat(last_ts.replace("Z", "+00:00")) - timedelta(days=FORECAST_DAYS)
    positives = _fraud_cashout_accounts(as_of)

    df = mule_graph.load_transfers(engine, as_of, WINDOW_DAYS)
    graph = mule_graph.build_graph(df)
    ranks = mule_graph.pagerank(graph)
    risk = mule_graph.terminal_cashout_risk(graph, ranks)

    nodes = set(graph["src2dst"]) | set(graph["dst2src"])
    ranked = sorted(
        ({"account_token": nd, **{k: risk[nd] for k in []}, "risk": risk[nd]} for nd in nodes),
        key=lambda r: -r["risk"],
    )

    # baselines
    by_inflow = sorted(
        ({"account_token": nd, "v": graph["inflow"].get(nd, 0.0)} for nd in nodes),
        key=lambda r: -r["v"],
    )
    by_deg = sorted(
        ({"account_token": nd, "v": len(graph["dst2src"].get(nd, []))} for nd in nodes),
        key=lambda r: -r["v"],
    )
    random_rank = [{"account_token": nd, "v": 0.0} for nd in nodes]
    import random as _r

    _r.shuffle(random_rank)

    print("=" * 78)
    print("MULE-GRAPH TERMINAL CASH-OUT BACKTEST (synthetic truth labels)")
    print("=" * 78)
    print(f"Graph window : last {WINDOW_DAYS} days of transfers, ending {as_of:%Y-%m-%d}")
    print(f"Forecast     : fraud cash-outs in next {FORECAST_DAYS} days ({as_of.date()} -> {as_of.date() + timedelta(days=FORECAST_DAYS)})")
    print(f"Edges        : {len(df):,}   Nodes: {len(nodes):,}   Fraud cash-out accts: {len(positives)}")
    print("-" * 78)
    print(f"{'K':>5} | {'terminal-risk  P@K  R@K':<22} | {'by-inflow  P@K':<15} | {'by-degree  P@K':<15} | {'random  P@K'}")
    print("-" * 78)
    for k in K_VALUES:
        tr_p = _precision_at_k(ranked, positives, k)
        tr_r = _recall_at_k(ranked, positives, k)
        bi_p = _precision_at_k(by_inflow, positives, k)
        bd_p = _precision_at_k(by_deg, positives, k)
        rd_p = _precision_at_k(random_rank, positives, k)
        print(
            f"{k:>5} | {tr_p:6.3f}  {tr_r:6.3f}  {tr_r / max(tr_p, 1e-9):6.3f}       "
            f"| {bi_p:6.3f} | {bd_p:6.3f} | {rd_p:6.3f}"
        )
    print("-" * 78)
    print("NOTE: terminal-risk is measured on the graph signal ALONE (secondary to the")
    print("main ATM-level XGBoost forecast — see MODEL_CARD.md). Synthetic labels only;")
    print("not a real-world accuracy claim.")

    # also save a small JSON snapshot for the dashboard / docs
    import json

    from pathlib import Path

    out = {
        "as_of": as_of.isoformat(),
        "window_days": WINDOW_DAYS,
        "forecast_days": FORECAST_DAYS,
        "n_edges": len(df),
        "n_nodes": len(nodes),
        "n_fraud_cashout_accounts": len(positives),
        "precision_at_k": {str(k): round(_precision_at_k(ranked, positives, k), 4) for k in K_VALUES},
        "recall_at_k": {str(k): round(_recall_at_k(ranked, positives, k), 4) for k in K_VALUES},
        "baseline_inflow_precision_at_k": {str(k): round(_precision_at_k(by_inflow, positives, k), 4) for k in K_VALUES},
        "top_terminal_nodes": [{"account_token": r["account_token"], "terminal_risk": round(risk[r["account_token"]], 4)} for r in ranked[:20]],
    }
    dest = Path("artifacts/deep_eval/mule_graph_eval.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2))
    print(f"\nsaved: {dest}")


if __name__ == "__main__":
    main()
