"""CashGuard AI — true lightweight blockchain (SIH 2024: Blockchain & Cybersecurity).

See `chain.py` (Proof-of-Work block chain) and `node.py` (permissioned peer
network with longest-chain consensus).
"""
from .chain import Block, CashGuardChain, get_chain
from .node import ChainNetwork, Peer

__all__ = ["Block", "CashGuardChain", "get_chain", "ChainNetwork", "Peer"]
