# CashGuard AI — On-chain Audit Anchoring (`AuditLog.sol`)

## What this is

`AuditLog.sol` is a small permissioned contract that stores the **consensus root**
of the CashGuard off-chain blockchain (`backend/blockchain/chain.py`). The root is
the SHA-256 hash of the latest block, which transitively commits every earlier
block through the Proof-of-Work hash chain.

Once the live chain's root is anchored here, anything happens on a public ledger:
a tamper-evident, public, timestamped **proof-of-existence** for every policy
action mined into the CashGuard chain (alert ack / fund freeze / evidence /
report). To falsify history an attacker would have to break *both* the off-chain
PoW chain *and* the on-chain record.

## Honest scope

- **Permissioned writer.** Only the deployer `owner` EOA can call `anchor()`.
  This matches the permissioned nature of the CashGuard blockchain
  (`backend/blockchain/node.py`). It is **not** an open permissionless chain.
- **Reads open.** Anyone can call `verify()` / `latestAnchor()` with no trust.
- **No fake anchoring.** Until env vars are set, `/ledger/verify-onchain` and
  `/ledger/anchor` honestly report `configured: false`. Nothing pretends to
  reach Polygon.

## Interface (matches `backend/blockchain/onchain.py` ABI)

| Function | Signature | Notes |
|---|---|---|
| `anchor` | `(bytes32 rootHash, bytes32 blockHash, uint64 blockNumber)` | owner-only, monotonic |
| `latestAnchor` | `() -> (bytes32, bytes32, uint256)` | latest root/block/timestamp |
| `lastAnchoredBlock` | `() -> (uint256)` | latest anchored block index |
| `verify` | `(uint256 blockNumber) -> (bool)` | exists + non-empty |

## Deploy (once you have a funded Polygon Amoy testnet wallet)

No Foundry/Hardhat is required — `web3` is already in the venv.

```python
# scripts/deploy_auditlog.py (run once, after filling in your funded key)
import sys; sys.path.insert(0, ".")
from web3 import Web3

RPC = "https://rpc-amoy.polygon.technology"
KEY = "0x..."                     # funded Polygon Amoy account (test MATIC via faucet)
w3 = Web3(Web3.HTTPProvider(RPC))
acct = w3.eth.account.from_key(KEY)
assert w3.is_connected()

# compile offline with Remix, or use py-solc-x: solcx.compile_source
import solcx
solcx.install_solc("0.8.20")
compiled = solcx.compile_source(
    open("contracts/AuditLog.sol").read(), solc_version="0.8.20")
abi = compiled["<stdin>:AuditLog"]["abi"]
bytecode = compiled["<stdin>:AuditLog"]["bin"]

contract = w3.eth.contract(abi=abi, bytecode=bytecode)
tx = contract.constructor().build_transaction({
    "from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address),
    "gas": 3_000_000, "gasPrice": w3.eth.gas_price})
signed = acct.sign_transaction(tx)
h = w3.eth.send_raw_transaction(signed.raw_transaction)
receipt = w3.eth.wait_for_transaction_receipt(h, timeout=180)
print(receipt["contractAddress"])
```

Then wire the demo in `.env`:

```env
LEDGER_ANCHOR_RPC_URL=https://rpc-amoy.polygon.technology
LEDGER_ANCHOR_PRIVATE_KEY=0x...
LEDGER_ANCHOR_CONTRACT_ADDRESS=<contractAddress from receipt>
```

After which:

- `POST /ledger/anchor` -> submits the live chain root to the contract.
- `GET  /ledger/verify-onchain` -> compares the live root to the on-chain record
  and reports `root_matches_onchain: true/false` + the anchored timestamp.
