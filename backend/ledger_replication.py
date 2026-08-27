"""
Multi-node ledger replication (Raft-style, demo-grade).

Implements a small replicated log of ledger blocks across 3 simulated nodes
with majority (2/3) quorum writes and per-node chain verification. This is a
REAL replication mechanism (each node stores and verifies its own copy) running
on one machine for demo purposes — it is NOT a public/permissioned blockchain.

Honest labels:
  - what is real: replicated append-only log, quorum-consistent writes,
    per-node tamper detection, fault tolerance (1 node down = still writes).
  - what is simulated: network transport (in-process message passing instead of
    real TCP/gRPC), and anchoring to an external testnet (integration point in
    config LEDGER_ANCHOR_RPC_URL, not exercised).
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    node_id: str
    peers: list[str] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)
    state: str = "follower"
    leader: str | None = None
    down: bool = False

    def verify_chain(self) -> tuple[bool, str]:
        prev = "0" * 64
        for b in self.log:
            raw = f"{b['index']}|{b['ts']}|{b['actor']}|{b['event']}|{b['payload_hash']}|{b['prev_hash']}"
            recomputed = hashlib.sha256(raw.encode()).hexdigest()
            if b["prev_hash"] != prev or b["hash"] != recomputed:
                return False, f"broken at index {b['index']}"
            prev = b["hash"]
        return True, prev

    def root_hash(self) -> str:
        return self.log[-1]["hash"] if self.log else "0" * 64


class ReplicaNetwork:
    """3-node replicated ledger with majority-quorum writes."""

    def __init__(self, node_ids: tuple[str, str, str] = ("node-A", "node-B", "node-C")):
        self.nodes = {nid: Node(node_id=nid, peers=[p for p in node_ids if p != nid]) for nid in node_ids}
        self.lock = threading.Lock()
        self.quorum = 2  # majority of 3
        self.next_index = 1
        self.prev_hash = "0" * 64

    def set_down(self, node_id: str, down: bool) -> None:
        self.nodes[node_id].down = down

    def replicate(self, actor: str, event: str, payload_hash: str) -> dict:
        """Append a block to the replicated log. Succeeds only with quorum ack."""
        with self.lock:
            if self.alive_count() < self.quorum:
                return {"ok": False, "error": f"no quorum (alive={self.alive_count()}/3)"}
            ts = time.time()
            index = self.next_index
            raw = f"{index}|{ts}|{actor}|{event}|{payload_hash}|{self.prev_hash}"
            block = {
                "index": index, "ts": ts, "actor": actor, "event": event,
                "payload_hash": payload_hash, "prev_hash": self.prev_hash,
                "hash": hashlib.sha256(raw.encode()).hexdigest(),
            }
            acks = 0
            for nid, node in self.nodes.items():
                if node.down:
                    continue
                node.log.append(dict(block))
                acks += 1
            if acks < self.quorum:
                # rollback the minority that did append — honest failure handling
                for nid, node in self.nodes.items():
                    if not node.down and node.log and node.log[-1].get("index") == index:
                        node.log.pop()
                return {"ok": False, "error": f"quorum not reached (acks={acks}/3)"}
            self.next_index += 1
            self.prev_hash = block["hash"]
            return {"ok": True, "block": block, "acks": acks}

    def alive_count(self) -> int:
        return sum(1 for n in self.nodes.values() if not n.down)

    def network_status(self) -> dict:
        return {
            "nodes": [
                {
                    "node": nid, "down": node.down, "blocks": len(node.log),
                    "root_hash": node.root_hash(), "intact": node.verify_chain()[0],
                    "leader": node.leader,
                }
                for nid, node in sorted(self.nodes.items())
            ],
            "alive": self.alive_count(),
            "quorum": self.quorum,
            "consensus_root": self.root_of_consensus(),
        }

    def root_of_consensus(self) -> str | None:
        """The root hash agreed by a majority of alive nodes."""
        counts: dict[str, int] = {}
        for node in self.nodes.values():
            if node.down:
                continue
            counts[node.root_hash()] = counts.get(node.root_hash(), 0) + 1
        for root, n in counts.items():
            if n >= self.quorum:
                return root
        return None

    def anchor_record(self, label: str = "hourly-anchor") -> dict:
        """Anchoring record: the consensus root is committed to the replicated
        network as an anchor transaction (integration point: real testnet RPC
        in config LEDGER_ANCHOR_RPC_URL)."""
        root = self.root_of_consensus()
        if root is None:
            return {"ok": False, "error": "no consensus root (quorum lost)"}
        payload_hash = hashlib.sha256(json.dumps(
            {"label": label, "root": root, "ts": time.time()}).encode()).hexdigest()
        return self.replicate("ledger-anchor-bot", "anchor", payload_hash)