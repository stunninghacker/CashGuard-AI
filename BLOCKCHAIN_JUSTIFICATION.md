# BLOCKCHAIN_JUSTIFICATION.md — Honest Account of the Blockchain & Cybersecurity Theme

## What is REAL in this project (verified, demo-grade)

1. **Tamper-evident SHA-256 hash chain** (`backend/repositories.py`
   `append_ledger`, `backend/services.py` `verify_ledger_chain`): every alert,
   decision, report, and access event is chained block-by-block
   (index|ts|actor|event|payload_hash|prev_hash → hash). `GET /ledger/verify`
   recomputes the chain and detects any modification — proven live by the
   tamper demo (verify → tamper → verify FAILS → restore → verify OK).
2. **3-node replicated ledger** (`backend/ledger_replication.py`,
   `scripts/ledger_anchoring.py`, `GET /ledger/network`): the audit chain is
   replicated across three nodes with majority-quorum (2/3) writes, per-node
   verification, and fault tolerance. Verified live: 315+ blocks replicated;
   with 1 node down writes still succeed (2/2 quorum); with 2 nodes down the
   write fails honestly ("no quorum"); tampering one node is detected on that
   node only while the majority stays intact. This is a genuine replication
   mechanism — the same log stored and verified on three independent
   processes — running on one machine for the demo.

## What is SIMULATED / an integration point (NOT exercised)

3. **External testnet anchoring**: `LEDGER_ANCHOR_RPC_URL` (config) is the
   integration point for anchoring the consensus root to a public testnet
   (e.g., Polygon Amoy). It is EMPTY by default; no external network has been
   touched. The anchor record mechanism (`anchor_record` in the replication
   demo) commits the consensus root into the replicated log as an
   "anchor transaction" — the shape of what a testnet anchoring would
   produce, not a real on-chain transaction.

## The design tradeoff (stated honestly)

| Option | Why not chosen / why chosen |
|---|---|
| Full permissioned blockchain (Hyperledger Fabric / PBFT consensus with real network transport) | Out of scope for a hackathon prototype: real distributed consensus adds infrastructure without changing the *property a court-facing system needs* — tamper-evidence and chain-of-custody. The SHA-256 chain already provides that property. |
| Demo-grade 3-node replication (CHOSEN) | Adds the *decentralization-shaped* property — no single node can silently rewrite the audit log; the majority must agree — with zero external dependencies, fully demoable offline. |
| Public testnet anchoring | The production upgrade path: periodically anchor the consensus root on-chain so the audit trail's existence is provable to a third party. Documented, configurable, not claimed as done. |

## Terminology discipline (same tone as MODEL_CARD.md)
- The implementation is called a **tamper-evident audit chain** and a
  **replicated ledger** — never "a blockchain".
- "Blockchain & Cybersecurity" is used only as the official SIH theme label.
- Nothing in the repo claims a cryptocurrency, a token, mining, or a public
  ledger. `docs/audits/Q&A_PREPARATION.md` Q39/Q40 give the exact judge answers.