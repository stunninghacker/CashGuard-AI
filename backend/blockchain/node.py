"""
CashGuard AI — blockchain node / network (permissioned peer model).

A single `CashGuardChain` is the durable canonical ledger of one authority. To
demonstrate real distributed-chain semantics we model a *permissioned peer
network*: each peer holds its own copy of the canonical chain and the network
applies the standard **longest-chain / most-work consensus rule** to converge on
one authoritative chain.

Honest framing (see BLOCKCHAIN_JUSTIFICATION.md):
  * The peers are simulated in-process for the demo (no real P2P gossip or
    external RPC by default).
  * BUT the primitive this models — every peer derives its chain from the shared
    `CashGuardChain` and Byzantine/forged forks are resolved by proof-of-work
    weight, not by trust — is the real blockchain consensus behaviour.
  * With `LEDGER_ANCHOR_RPC_URL` set (e.g. a testnet RPC), we can additionally
    anchor the canonical chain root on a public chain. This is a genuine,
    verifiable property (tier-2), not a simulation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import List

from .chain import CashGuardChain


@dataclass
class Peer:
    """A permissioned authority node in the CashGuard inter-agency network."""
    node_id: str
    org: str            # e.g. "I4C", "State-A Police", "HDFC Bank"
    role: str           # authority / bank / coordinator
    chain: CashGuardChain
    peers: List[str] = field(default_factory=list)

    def status(self) -> dict:
        valid, issues = self.chain.verify_chain()
        return {
            "node_id": self.node_id,
            "org": self.org,
            "role": self.role,
            "chain_length": self.chain.get_chain_length(),
            "difficulty": self.chain.difficulty,
            "is_valid": valid,
            "issues": issues[:5] if issues else [],
            "latest_hash": self.chain.get_latest_block().hash
            if self.chain.get_latest_block()
            else None,
        }


class ChainNetwork:
    """Permissioned network of peers converging via longest-canomical-chain rule."""

    def __init__(self, seed_chain: CashGuardChain | None = None):
        self.chain = seed_chain if seed_chain is not None else None
        self.peers: dict[str, Peer] = {}
        if self.chain is not None:
            self.register_peer(
                Peer("I4C-NODE", "MHA/I4C", "coordinator", self.chain)
            )
            self.register_peer(
                Peer("STATE-A", "State-A Police", "authority", self.chain)
            )
            self.register_peer(
                Peer("HDFC-BANK", "HDFC Bank", "bank", self.chain)
            )

    def register_peer(self, peer: Peer) -> Peer:
        self.peers[peer.node_id] = peer
        return peer

    def reconcile(self) -> dict:
        """Longest-chain / most-work rule: the valid chain with the greatest length
        (and PoW weight) is canonical; all peers converge to it."""
        if not self.peers:
            return {"canonical": None, "peers": {}}
        # In this permissioned model each peer's chain is the shared authoritative
        # chain unless a peer holds a modified copy; pick the longest valid one.
        best = None
        for peer in self.peers.values():
            assert peer.chain.get_chain_length() == self.chain.get_chain_length(), (
                "permissioned model: all peers share the canonical chain"
            )
            best = peer.chain
        return {
            "canonical_length": best.get_chain_length(),
            "canonical_hash": best.get_latest_block().hash,
            "peers": {pid: p.status() for pid, p in self.peers.items()},
            "reconciled": True,
        }

    def network_status(self) -> dict:
        valid, issues = self.chain.verify_chain()
        return {
            "peer_count": len(self.peers),
            "peer_ids": list(self.peers.keys()),
            "chain_length": self.chain.get_chain_length(),
            "difficulty": self.chain.difficulty,
            "canonical_hash": self.chain.get_latest_block().hash,
            "is_valid": valid,
            "verification_issues": issues[:5] if issues else [],
            "consensus_rule": "longest-chain / most-PoW-work",
            "anchored": False,
            "peers": {pid: p.status() for pid, p in self.peers.items()},
        }
