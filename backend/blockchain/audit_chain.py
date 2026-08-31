'''Blockchain audit logger for CashGuard AI

Implements a simple on‑chain anchoring of alerts using the Ethereum Sepolia
testnet. The logger is deliberately lightweight – it signs a transaction
with a test private key (kept in .env.example) and stores only the hash of
the alert payload. This provides an immutable, publicly verifiable proof
that an alert was generated at a specific time.
''' 

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from web3 import Web3
from web3.exceptions import TransactionNotFound


class BlockchainAuditLogger:
    """Log alert metadata on Sepolia testnet.

    The class reads a private key and associated address from environment
    variables. If the variables are missing, the logger falls back to a mock
    mode that returns a deterministic placeholder hash – this allows the UI
    to display a hash even when the user has not supplied real credentials.
    """

    def __init__(self) -> None:
        # Load credentials – developers should place them in .env
        self.private_key = os.getenv("SEPOLIA_PRIVATE_KEY")
        self.account_address = os.getenv("SEPOLIA_ACCOUNT_ADDRESS")
        self.w3 = Web3(Web3.HTTPProvider("https://rpc.sepolia.org"))
        self.mock_mode = not (self.private_key and self.account_address)
        if self.mock_mode:
            # Simple deterministic placeholder – useful for demos
            self.placeholder_hash = "0xdeadbeef" * 8
        else:
            # Ensure the connection works
            if not self.w3.isConnected():
                raise RuntimeError("Unable to connect to Sepolia RPC endpoint")
            # Verify that the supplied address matches the private key
            derived = self.w3.eth.account.from_key(self.private_key).address
            if derived.lower() != self.account_address.lower():
                raise ValueError("SEPOLIA_ACCOUNT_ADDRESS does not match SEPOLIA_PRIVATE_KEY")

    def log_alert(self, alert_id: str, risk_score: float, atm_id: str, timestamp: str) -> str:
        """Anchor an alert on‑chain and return the transaction hash.

        Parameters
        ----------
        alert_id: str
            Unique identifier for the alert (e.g. "ALT‑001").
        risk_score: float
            The risk probability produced by the model.
        atm_id: str
            Identifier of the ATM the alert concerns.
        timestamp: str
            ISO‑8601 timestamp string of when the alert was generated.
        """
        data = f"{alert_id}|{risk_score}|{atm_id}|{timestamp}"
        data_hash = self.w3.keccak(text=data).hex()

        if self.mock_mode:
            # Return a deterministic placeholder that still looks like a tx hash
            return self.placeholder_hash

        # Build a minimal transaction – sending 0 ETH to self to embed the data
        txn = {
            "to": self.account_address,
            "value": 0,
            "data": data_hash,
            "chainId": 11155111,  # Sepolia chain ID
            "nonce": self.w3.eth.get_transaction_count(self.account_address),
            "gas": 21000,
            "gasPrice": self.w3.eth.gas_price,
        }
        signed = self.w3.eth.account.sign_transaction(txn, private_key=self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        # Wait for the transaction receipt (simple polling – testnet is fast)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            raise RuntimeError("Transaction failed on Sepolia")
        return tx_hash.hex()
