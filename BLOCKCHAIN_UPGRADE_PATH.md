# BLOCKCHAIN_UPGRADE_PATH.md — Audit Integrity: Today → Permissioned Ledger

**Purpose.** The SIH theme is "Blockchain & Cybersecurity." This project does
**not** hand-wave: the audit-integrity layer works **today** as a tamper-evident
SHA-256 hash chain (verified, demo-grade), and this document is the honest,
staged **upgrade path** to a permissioned ledger anchor — mapping each stage to
what is real now, what is an integration point, and what would change in
production. Companion honesty doc: [BLOCKCHAIN_JUSTIFICATION.md](BLOCKCHAIN_JUSTIFICATION.md).

## Terminology discipline (read first)
- The current system is a **hash chain / append-only log** — **NOT a blockchain**.
  We say so deliberately (see BLOCKCHAIN_JUSTIFICATION.md §"Terminology discipline").
- "Blockchain" only applies to the **permissioned-ledger anchoring** stage below,
  which is an external integration (not yet exercised).

## Where audit integrity lives today (REAL, verified)
| Mechanism | Where | What it gives |
|-----------|-------|---------------|
| SHA-256 hash chain over every risk/alert/decision | `backend/repositories.py` `append_ledger` (index/ts/actor/event/payload_hash/prev_hash → SHA-256) | Tamper-evidence: any edit to any prior record breaks every subsequent hash — detectable, auditable |
| Queryable, replayable chain | `backend/api/routes/ledger.py` | Ops can review/verify the history |
| Model tamper key lifecycle | config/process | Weaker-hash/short-key risks flagged; JWT/secret tampering detectable |
| Multi-node replicated log (Raft-style) | `backend/ledger_replication.py` | Majority (2/3) quorum writes + per-node verification across 3 nodes — a real replication mechanism on one machine |

Honest boundary: the replication uses **in-process message passing, not
real TCP/gRPC**, and external testnet anchoring is an **integration point**
(`LEDGER_ANCHOR_RPC_URL` in config, not exercised). Both are stated — not hidden.

## The upgrade path (staged, each with a go/no-go)
**Stage 0 — Current (IN REPO, WORKING).** Single-node SHA-256 hash chain +
Raft-style replicated log on one host. Production-seedable for a single-lead
agency. *No external permissioned ledger required.*

**Stage 1 — Multi-party replicated ledger (permissioned).** Replace the
in-process replication with real network consensus among the participating
authorities (I4C, one or more state-LEA nodes, partner banks' nodes). Each party
keeps its own verified copy; writes require a quorum. **What changes:** network
transport (gRPC/TCP), key/cert management per node, real TCP listener in
`ledger_replication.py`. **What does not change:** the hash-chain block schema
(index/ts/actor/event/payload_hash/prev_hash) and the append/verify logic.

**Stage 2 — Anchor to a permissioned ledger / testnet.** Periodically publish a
**commitment** (a root hash / Merkle root of the local chain) to an external
permissioned chain (e.g., Geth-PoA, Hyperledger Fabric channel, or a monitored
testnet) so the system's integrity is independently provable to a third party.
**What is simulated today:** `LEDGER_ANCHOR_RPC_URL` integration point is not
exercised. **What is real:** the hash-commitment concept applies directly — a
root hash derived from Stage-0/1 chain state can be anchored without sending any
sensitive data (minimization preserved, see DATA_PROTECTION.md).

**Stage 3 — (Optional) Deep on-chain metadata.** Only if the program requires
it. Would store minimal, hashed, non-PII evidence references on-chain — never
raw data. Documented as optional because the SIH objective (tamper-evident
audit) is already met by Stages 0–2.

## Why "blockchain" is scoped carefully (honest design tradeoff)
- A full public blockchain is **inappropriate** here: the data is sensitive,
  the participants are a fixed, known set (I4C + banks + LEAs), and throughput
  is low. A **permissioned** ledger matches the trust model and keeps
  data-minimization/privacy controls intact.
- The prototype earns the theme by **showing a working tamper-evident chain +
  replication + a real upgrade path**, not by mislabeling the hash chain as a
  blockchain. This mirrors the honesty tone across MODEL_CARD.md and LIMITATIONS.md.

## Verification / traces
- Tamper-detection tests: security regression suite (`scripts/test_security_regression.py`, 14/14).
- Ledger replication eval: `scripts/` ledger-replication generator/artifact (see
  `artifacts/deep_eval/` ledger replication entry).
- Honesty about what is real vs. simulated: BLOCKCHAIN_JUSTIFICATION.md,
  LIMITATIONS.md, and this document's stages.
