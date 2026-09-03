// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// CashGuard AI — on-chain audit anchoring (SIH 2024: Blockchain & Cybersecurity).
//
// Purpose
// -------
// A permissioned anchor registry. CashGuard's off-chain ledger/blockchain
// periodically commits its *consensus root* (the SHA-256 hash of the latest
// block, which transitively commits every prior block via the hash chain) to
// this contract. This gives a public, immutable, timestamped proof-of-existence:
//
//   anchorHash = keccak256(abi.encodePacked(rootHash, blockHash, blockNumber))
//
// storage per anchor = { rootHash, blockHash, blockNumber, anchoredBy, timestamp }
//
// Once an event (alert ack / fund freeze / evidence / report) is mined into
// the CashGuard chain and that chain's root is anchored here, it cannot be
// silently rewritten without breaking the on-chain record AND the off-chain
// PoW chain — the two records must agree.
//
// Ownership / permissioning (honest label):
//   This is a *permissioned anchor registry*, not an open cryptocurrency or
//   public-chain consensus. The owner (the deploying I4C operator address)
//   is the sole writer, matching the permissioned nature of the CashGuard
//   blockchain (backend/blockchain/node.py). Reads are open to anyone.
//   Anyone can call verify() to prove a stored anchor matches the on-chain
//   record — no trust in the caller is required.
//
// Deployment targets
// ------------------
// Local dev : anvil / hardhat node
// Public    : Polygon Amoy testnet (via backend.blockchain.onchain with
//             LEDGER_ANCHOR_RPC_URL / LEDGER_ANCHOR_PRIVATE_KEY /
//             LEDGER_ANCHOR_CONTRACT_ADDRESS set) — see docs + onchain.py.
contract AuditLog {
    // The EOA permitted to write anchors. Set once at deploy.
    address public immutable owner;

    // One immutable anchor of the off-chain CashGuard chain.
    struct Anchor {
        bytes32 rootHash;     // SHA-256 consensus root of the CashGuard chain
        bytes32 blockHash;    // SHA-256 hash of a specific CashGuard block
        uint64  blockNumber;  // CashGuard block index that produced rootHash
        address anchoredBy;   // writer
        uint256 timestamp;    // UNIX seconds when anchored
    }

    // blockNumber -> Anchor  (each CashGuard block is anchored at most once)
    mapping(uint256 => Anchor) public anchors;

    // Latest anchored CashGuard block index (reverse lookup for "newest").
    uint256 public lastAnchoredBlock;

    event Anchored(
        uint256 indexed blockNumber,
        bytes32 rootHash,
        bytes32 blockHash,
        address indexed anchoredBy
    );

    constructor() {
        owner = msg.sender;
        lastAnchoredBlock = 0;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "AuditLog: not owner");
        _;
    }

    /// @notice Anchor a new CashGuard consensus root.
    /// @param rootHash    SHA-256 hash that transitively commits the whole chain
    /// @param blockHash   SHA-256 hash of the latest CashGuard block
    /// @param blockNumber CashGuard block index (must be strictly increasing)
    function anchor(
        bytes32 rootHash,
        bytes32 blockHash,
        uint64 blockNumber
    ) external onlyOwner {
        require(rootHash != bytes32(0), "AuditLog: empty root");
        require(blockHash != bytes32(0), "AuditLog: empty block");
        require(blockNumber > lastAnchoredBlock, "AuditLog: must be monotonic");

        Anchor memory a = Anchor({
            rootHash: rootHash,
            blockHash: blockHash,
            blockNumber: blockNumber,
            anchoredBy: msg.sender,
            timestamp: block.timestamp
        });
        anchors[blockNumber] = a;
        lastAnchoredBlock = blockNumber;
        emit Anchored(blockNumber, rootHash, blockHash, msg.sender);
    }

    /// @notice Prove that a CashGuard root was anchored at a given block index.
    /// @return true iff an anchor exists at blockNumber and its hashes are
    ///         non-empty (i.e. the on-chain record matches what was committed).
    function verify(uint256 blockNumber) external view returns (bool) {
        Anchor memory a = anchors[blockNumber];
        return a.rootHash != bytes32(0) && a.blockHash != bytes32(0);
    }

    /// @notice Latest anchored root (used by off-chain verifier).
    function latestAnchor() external view
        returns (bytes32 rootHash, bytes32 blockHash, uint256 timestamp)
    {
        Anchor memory a = anchors[lastAnchoredBlock];
        return (a.rootHash, a.blockHash, a.timestamp);
    }
}
