# Money-Trail / Mule Graph Module

**Purpose**: Flag high-risk terminal cash-out nodes from the inter-account transfer graph using graph centrality + anomaly signals. This is a **secondary signal** (supplementary to the primary ATM-level XGBoost forecast).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  CFCFRMS / Core Banking Transfer Feeds (synthetic in demo)      │
│  directed edges:  from_token → to_token, amount, timestamp      │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  backend/ml/mule_graph.py  (pure Python, no networkx)           │
│  • load_transfers(engine, as_of, window_days)                   │
│    – no leakage: only edges with timestamp < as_of              │
│  • build_graph(df) → adjacency + inflow/outflow maps            │
│  • pagerank(graph, damping=0.85, iters=40)                      │
│    – power iteration, normalized to [0,1]                       │
│  • chain_depth_of(graph)                                        │
│    – backward BFS layering depth from sources                   │
│  • terminal_cashout_risk(graph, ranks)                          │
│    – weighted blend:                                            │
│        0.30 × in-degree  +  0.25 × terminal-ratio               │
│        0.15 × chain-depth  +  0.15 × pagerank                   │
│        0.15 × inflow                                              │
│        + 0.15 bonus if out-degree == 0 (terminal node)          │
│  • top_terminal_nodes(…) → ranked list                          │
│  • money_trail(engine, account_token, as_of, window_days)       │
│    – LEA case view: chains + edges payload                      │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  REST API (role-scoped)                                         │
│  GET /mule-graph/terminal-nodes?k=20                            │
│  GET /mule-graph/trail/{account_token}                          │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Frontend: I4C dashboard → "Money Trail — Terminal Cash-Out     │
│  Graph" panel with ranked table + drill-down chains/edges       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Model

**Table**: `transfers` (added in `backend/models.py:112`)

| Column        | Type       | Description                          |
|---------------|------------|--------------------------------------|
| `transfer_id` | String(32) | Unique edge identifier               |
| `timestamp`   | DateTime   | Edge timestamp (indexed)             |
| `from_token`  | String(64) | Source account (PII-pseudonymised)   |
| `to_token`    | String(64) | Destination account                  |
| `amount`      | Float      | Transfer amount (INR)                |

**Synthetic generation** (`backend/data/synthetic_data.py:generate_transfers`):
- `n_entry_nodes=6000` seed accounts (complaint-linked)
- `chain_depth_min=1`, `chain_depth_max=3` hops before terminal
- `edge_mix_fraction=0.35` amount split across hops
- `n_benign_edges=40000` background edges sharing 50% recipients
- Every mule account is the **terminal cash-out node** (withdrawal `account_token` = mule token)

---

## Terminal Risk Formula

For each node `v` in the transfer graph built from the trailing 30-day window:

```
risk(v) = 0.30 × in_deg_norm(v)
        + 0.25 × terminal_ratio(v)
        + 0.15 × chain_depth_norm(v)
        + 0.15 × pagerank_norm(v)
        + 0.15 × inflow_norm(v)
        + (0.15 if out_deg(v) == 0 else 0)
```

Where each component is min-max normalized to [0,1] over the node set.

- **in-degree**: number of distinct incoming senders
- **terminal-ratio**: `in_deg / max(in_deg, out_deg)` — high when node receives but rarely sends
- **chain-depth**: backward BFS layers from source accounts (layer 0 = entry)
- **pagerank**: centrality in the full directed graph (damping 0.85, 40 iters)
- **inflow**: total INR received in window

The **out-degree == 0 bonus** explicitly rewards terminal nodes that never forward funds — the cash-out accounts.

---

## Evaluation (Honest Synthetic Backtest)

Script: `scripts/mule_graph_eval.py`

- **Split**: Graph built from transfers in the 30 days before `as_of`; forecast window = next 5 days after `as_of`
- **Truth**: accounts that perform `is_fraud_withdrawal=1` in the forecast window
- **Metric**: precision@K / recall@K for `K ∈ {20, 50, 100}`
- **Baselines**:
  - `by_inflow` — top recipients by total INR received
  - `by_in_degree` — top recipients by number of distinct senders
  - `random` — random ranking

**Result (synthetic, single run)**:
```
K=20  | terminal-risk P@K=0.050 | by-inflow=0.050 | by-degree=0.050 | random=0.000
K=50  | terminal-risk P@K=0.100 | by-inflow=0.040 | by-degree=0.080 | random=0.020
K=100 | terminal-risk P@K=0.060 | by-inflow=0.020 | by-degree=0.080 | random=0.010
```

Interpretation: the graph signal provides **modest lift** over simple volume/degree heuristics on this synthetic dataset. It is **not a standalone detector** — it is a secondary signal for analyst triage.

Artifact saved: `artifacts/deep_eval/mule_graph_eval.json`

---

## API Endpoints

### `GET /mule-graph/terminal-nodes?k=20`

**Roles**: `I4C_ADMIN`, `POLICE_STATE`, `POLICE_DISTRICT`, `BANK`

**Response**:
```json
{
  "as_of": "2026-08-29T00:04:00",
  "window_days": 30,
  "nodes": [
    { "account_token": "acct_801424494423", "terminal_risk": 0.7396 },
    ...
  ]
}
```

**Scoping**: I4C_ADMIN sees all; BANK sees only `home_bank == scope`; Police see all (investigation crosses bank boundaries).

### `GET /mule-graph/trail/{account_token}`

**Roles**: same as above

**Response**:
```json
{
  "account_token": "acct_801424494423",
  "as_of": "2026-08-29T00:04:00",
  "window_days": 30,
  "terminal_risk": 0.7396,
  "in_degree": 5,
  "out_degree": 0,
  "inflow_inr": 34815.96,
  "chain_depth": 4,
  "chains": [
    ["acct_84476ad31a55", "acct_a682eb16f424", "acct_801424494423"],
    ["acct_9cf6f4b6df36", "acct_d0916bd77c88", "acct_801424494423"],
    ...
  ],
  "edges": [
    { "source": "acct_a682eb16f424", "target": "acct_801424494423", "amount": 3610.51 },
    ...
  ]
}
```

---

## Frontend Integration

- Panel: "Money Trail — Terminal Cash-Out Graph" in I4C dashboard
- Table: ranked terminal nodes (top 50) with risk score
- Click 🔍 **Trail** → expands detail with:
  - Terminal risk, degrees, inflow, chain depth
  - Layering chains (source → … → terminal)
  - Edge list for cytoscape-style rendering

---

## Production Notes

1. **NetworkX optional**: The pure-Python implementation avoids the dependency. In production, replace with `networkx.pagerank` for larger graphs (>100k nodes).
2. **Incremental updates**: Graph rebuild on each request (demo scale). Production: maintain graph incrementally via streaming transfer feed.
3. **Feature fusion**: Terminal risk is **not fused** into the main `FEATURE_COLUMNS` / `build_features` pipeline (avoids leakage risk). It is delivered as a standalone secondary signal. Production enhancement: add as a separate feature with temporal leakage guard.
4. **PII safety**: `from_token` / `to_token` are pseudonymised account identifiers. Raw account details never appear in the graph, API, or dashboard.

---

## References

- `backend/ml/mule_graph.py` — core graph module
- `backend/api/routes/mule_graph.py` — REST endpoints
- `scripts/mule_graph_eval.py` — honest backtest
- `artifacts/deep_eval/mule_graph_eval.json` — latest eval artifact
- `MODEL_CARD.md` — primary forecast model card (this is secondary)
- `LIMITATIONS.md` — synthetic evaluation caveats