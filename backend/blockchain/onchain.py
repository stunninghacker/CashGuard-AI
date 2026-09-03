"""
CashGuard AI — on-chain audit anchoring (SIH 2024: Blockchain & Cybersecurity).

Tier-2 integration point: periodically commit the off-chain cashguard chain's
*consensus root* (the SHA-256 hash of the latest block, which transitively
commits every prior block through the PoW hash chain) to a permissioned
`AuditLog` contract on an Ethereum-compatible chain (Polygon Amoy testnet).

This gives a public, immutable, timestamped proof-of-existence: once an event
(alert ack / fund freeze / evidence / report) is mined into the cashguard chain
*and* that chain's root is anchored here, the two records must agree. Rewriting
the off-chain history would break the chain AND disagree with the on-chain
record.

Honest design
-------------
* When `LEDGER_ANCHOR_RPC_URL`, `LEDGER_ANCHOR_PRIVATE_KEY` and
  `LEDGER_ANCHOR_CONTRACT_ADDRESS` are all set, a real `web3` client is built
  and `anchor_latest()` submits a transaction. Nothing about that path is
  simulated.
* Otherwise (default), no fake hashes are minted: every function returns
  `configured: False` and an explicit reason. `verify_onchain()` reports
  "not anchored" rather than pretending data reached Polygon.

The contract ABI is pinned here to match `contracts/AuditLog.sol`.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from ..config import (
    LEDGER_ANCHOR_CONTRACT_ADDRESS,
    LEDGER_ANCHOR_PRIVATE_KEY,
    LEDGER_ANCHOR_RPC_URL,
)

# --------------------------------------------------------------------------
# Pinned minimal ABI (matches contracts/AuditLog.sol). Pinned inline here so
# the verifier runs without a separate compiled-artifacts step.
# --------------------------------------------------------------------------
AUDIT_LOG_ABI = [
            {
                "inputs": [
                    {"internalType": "bytes32", "name": "rootHash", "type": "bytes32"},
                    {"internalType": "bytes32", "name": "blockHash", "type": "bytes32"},
                    {"internalType": "uint64", "name": "blockNumber", "type": "uint64"},
                ],
                "name": "anchor",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function",
            },
            {
                "inputs": [],
                "name": "latestAnchor",
                "outputs": [
                    {"internalType": "bytes32", "name": "rootHash", "type": "bytes32"},
                    {"internalType": "bytes32", "name": "blockHash", "type": "bytes32"},
                    {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
                ],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [],
                "name": "lastAnchoredBlock",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [
                    {"internalType": "uint256", "name": "blockNumber", "type": "uint256"}
                ],
                "name": "verify",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function",
            },
]


def anchor_config() -> Dict[str, Optional[str]]:
    """Describe whether a real on-chain anchor is wired up (honest status)."""
    return {
        "network": LEDGER_ANCHOR_RPC_URL or None,
        "contract_address": LEDGER_ANCHOR_CONTRACT_ADDRESS or None,
        "signer_configured": bool(LEDGER_ANCHOR_PRIVATE_KEY),
        "configured": bool(
            LEDGER_ANCHOR_RPC_URL
            and LEDGER_ANCHOR_CONTRACT_ADDRESS
            and LEDGER_ANCHOR_PRIVATE_KEY
        ),
    }


def _client():
    """Build a web3 client + contract wrapper, or raise a clear error."""
    if not anchor_config()["configured"]:
        raise RuntimeError(
            "on-chain anchoring not configured: set LEDGER_ANCHOR_RPC_URL, "
            "LEDGER_ANCHOR_CONTRACT_ADDRESS and LEDGER_ANCHOR_PRIVATE_KEY"
        )
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(LEDGER_ANCHOR_RPC_URL))
    if not w3.is_connected():
        raise RuntimeError(f"web3 cannot reach RPC: {LEDGER_ANCHOR_RPC_URL}")
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(LEDGER_ANCHOR_CONTRACT_ADDRESS),
        abi=AUDIT_LOG_ABI,
    )
    account = w3.eth.account.from_key(LEDGER_ANCHOR_PRIVATE_KEY)
    return w3, contract, account


def _root_hash(chain) -> Tuple[str, int]:
    """Return (latest_block_hash, latest_block_index) from the cashguard chain."""
    latest = chain.get_latest_block()
    if latest is None:
        raise RuntimeError("cashguard chain is empty (no genesis)")
    return latest.hash, latest.index


def anchor_latest(chain, wait: bool = True) -> Dict:
    """Anchor the cashguard chain's latest root to the on-chain AuditLog."""
    cfg = anchor_config()
    if not cfg["configured"]:
        return {
            "anchored": False,
            "configured": False,
            "reason": "on-chain anchoring not configured (see backend/config.py)",
        }
    try:
        w3, contract, account = _client()
    except RuntimeError as exc:
        return {"anchored": False, "configured": True, "error": str(exc)}

    block_hash, block_index = _root_hash(chain)
    root_hash_bytes = bytes.fromhex(block_hash)
    block_hash_bytes = bytes.fromhex(block_hash)  # root == latest block hash == chain root

    nonce = w3.eth.get_transaction_count(account.address, "latest")
    tx = {
        "from": account.address,
        "nonce": nonce,
        "gas": 300_000,
        "gasPrice": w3.eth.gas_price,
    }
    try:
        fn = contract.functions.anchor(
            root_hash_bytes, block_hash_bytes, block_index
        )
        # EIP-1559 friendly: attach max fee + max priority if the chain accepts it.
        latest = w3.eth.get_block("latest")
        if "baseFeePerGas" in latest:
            base = latest["baseFeePerGas"]
            tx["maxPriorityFeePerGas"] = 1_000_000_000
            tx["maxFeePerGas"] = base + 1_000_000_000
        built = fn.build_transaction(tx)
        signed = w3.eth.account.sign_transaction(built, LEDGER_ANCHOR_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = None
        if wait:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        return {
            "anchored": True,
            "configured": True,
            "block_index": block_index,
            "root_hash": block_hash,
            "tx_hash": tx_hash.hex(),
            "receipt_tx_hash": receipt["transactionHash"].hex() if receipt else None,
            "block_number": receipt["blockNumber"] if receipt else None,
            "status": receipt["status"] if receipt else None,
        }
    except Exception as exc:  # noqa: BLE001 - report honestly, never fake success
        return {
            "anchored": False,
            "configured": True,
            "block_index": block_index,
            "root_hash": block_hash,
            "error": f"{type(exc).__name__}: {exc}",
        }


def verify_onchain(chain) -> Dict:
    """Compare the current cashguard root against the on-chain audit record.

    Honest outcomes:
      * configured=False -> {verified: False, configured: False, reason}
      * configured, on-chain empty -> {verified: False, anchored: False}
      * matches            -> {verified: True,  anchored: True}
      * mismatch           -> {verified: False, anchored: True, mismatch: True}
    """
    cfg = anchor_config()
    base = {"configured": cfg["configured"], "network": cfg["network"]}
    if not cfg["configured"]:
        base.update(
            {
                "verified": False,
                "anchored": False,
                "reason": "on-chain anchoring not configured — current chain root is "
                "NOT on Polygon; this is the honest pre-production state.",
            }
        )
        return base

    try:
        w3, contract, account = _client()
    except RuntimeError as exc:
        base.update({"verified": False, "anchored": "unknown", "error": str(exc)})
        return base

    current_hash, current_index = _root_hash(chain)

    try:
        last_anchored = contract.functions.lastAnchoredBlock().call()
        if last_anchored == 0:
            base.update(
                {
                    "verified": False,
                    "anchored": False,
                    "current_root": current_hash,
                    "current_block_index": current_index,
                    "note": "contract exists but no anchor has been submitted yet",
                }
            )
            return base
        root_hash_onchain, _, anchor_ts = contract.functions.latestAnchor().call()
        onchain_root = root_hash_onchain.hex() if isinstance(root_hash_onchain, bytes) else root_hash_onchain
        match = onchain_root.lower() == current_hash.lower()
        base.update(
            {
                "anchored": True,
                "verified": match,
                "root_matches_onchain": match,
                "current_root": current_hash,
                "onchain_root": onchain_root if isinstance(onchain_root, str) else onchain_root,
                "anchored_block_index": last_anchored,
                "anchored_timestamp": anchor_ts,
                "verifier": account.address,
                "detail": (
                    "on-chain record matches the live cashguard root"
                    if match
                    else "MISMATCH: live cashguard root differs from the on-chain anchor"
                ),
            }
        )
        return base
    except Exception as exc:  # noqa: BLE001
        base.update(
            {
                "verified": False,
                "anchored": "unknown",
                "current_root": current_hash,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        return base
