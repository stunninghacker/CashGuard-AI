"""
CashGuard AI — real lightweight blockchain (SIH 2024 | Theme: Blockchain & Cybersecurity).

Implements a *true* chain of blocks with the full property set that a blockchain
needs, without Hyperledger/Ganache operational complexity — fully deployable as a
module of this FastAPI backend and persisted to SQLite:

  1. Immutability / Tamper-Evidence  — each block commits its `previous_hash` and
     its own content hash; altering any block breaks every subsequent block.
  2. Proof of Work (Nakamoto-style mining) — a block's hash must start with
     `DIFFICULTY` zero nibbles; forging a valid block at position `i` requires
     re-mining block `i` *and* every later block (real per-block compute).
  3. Append-only ordering — monotonically increasing `index`, genesis root.
  4. Detectability — `verify_chain()` recomputes hashes and returns exact issues
     (HASH_MISMATCH / CHAIN_BROKEN / INVALID_POW).
  5. Chain-of-custody — typed records (ALERT_GENERATED, ALERT_ACKNOWLEDGED,
     EVIDENCE_SUBMITTED, FUND_FREEZE_REQUESTED, FUND_FREEZE_CONFIRMED,
     REPORT_GENERATED, INVESTIGATION_OPENED) with `created_by` identity.

This is the **blockchain** (a tamper-evident, PoW-secured, ordered chain). It
replaces/augments the older SHA-256 hash-chain "ledger" whose blocks were
trivially mutable (no per-block work), which the SIH theme rightly penalises.

Consensus / distribution is layered separately in `node.py` (peer set, longest
canonical chain) and documented honestly in BLOCKCHAIN_JUSTIFICATION.md.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Block
# ---------------------------------------------------------------------------
@dataclass
class Block:
    index: int
    timestamp: float
    data: dict
    previous_hash: str
    nonce: int = 0
    hash: str = field(default="")

    def compute_hash(self) -> str:
        """Canonical, order-stable serialisation; ANY field change alters the hash."""
        block_string = json.dumps(
            {
                "index": self.index,
                "timestamp": self.timestamp,
                "data": self.data,
                "previous_hash": self.previous_hash,
                "nonce": self.nonce,
            },
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        return hashlib.sha256(block_string.encode("utf-8")).hexdigest()

    def mine_block(self, difficulty: int = 2) -> str:
        """Proof of Work — brute-force a nonce so hash starts with `difficulty` zeros."""
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.compute_hash()
        return self.hash

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Persistent, permissioned chain
# ---------------------------------------------------------------------------
class CashGuardChain:
    """A permissioned blockchain for immutable alert/evidence/audit records.

    Multi-node semantics live in `node.py`; this class is the single, durable,
    authoritative chain store (a node's canonical chain).
    """

    DEFAULT_DIFFICULTY = 2  # fast for demo; raise in prod (e.g. 4)
    GENESIS_PREV = "0" * 64

    def __init__(self, db_path: str | Path = "data/blockchain.db", difficulty: int | None = None):
        self.db_path: Path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.difficulty = difficulty if difficulty is not None else self.DEFAULT_DIFFICULTY
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
        if self.get_chain_length() == 0:
            self._create_genesis_block()

    # ------------------------- persistence helpers -------------------------
    def _connect(self) -> sqlite3.Connection:
        # Re-open per operation is simpler/thread-safe enough for a demo; a
        # threaded wrapper could share one conn with a lock.
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS blocks (
                    block_index INTEGER PRIMARY KEY,
                    timestamp REAL,
                    data TEXT,
                    previous_hash TEXT,
                    nonce INTEGER,
                    hash TEXT,
                    record_type TEXT,
                    created_by TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _save_block(self, block: Block, record_type: str, created_by: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO blocks
                   (block_index, timestamp, data, previous_hash, nonce, hash,
                    record_type, created_by)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    block.index,
                    block.timestamp,
                    json.dumps(block.data, default=str),
                    block.previous_hash,
                    block.nonce,
                    block.hash,
                    record_type,
                    created_by,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _row_to_block(row) -> Block:
        raw = row["data"]
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            # Tamper-evidence: keep the raw string so verify_chain() can flag
            # it as INVALID_DATA instead of crashing on an unparseable row.
            data = {"__corrupt_data__": raw}
        return Block(
            index=row["block_index"],
            timestamp=row["timestamp"],
            data=data,
            previous_hash=row["previous_hash"],
            nonce=row["nonce"],
            hash=row["hash"],
        )

    # ------------------------------ chain ops ------------------------------
    def _create_genesis_block(self) -> Block:
        genesis = Block(
            index=0,
            timestamp=time.time(),
            data={
                "message": "CashGuard-AI Genesis Block",
                "system": "SIH26184",
                "org": "MHA/I4C",
                "consensus": "proof-of-work",
            },
            previous_hash=self.GENESIS_PREV,
        )
        genesis.mine_block(self.difficulty)
        self._save_block(genesis, "genesis", "SYSTEM")
        return genesis

    def add_record(self, data: dict, record_type: str, created_by: str) -> Block:
        """Append an immutable record. See module docstring for record types."""
        previous_block = self.get_latest_block()
        new_block = Block(
            index=previous_block.index + 1,
            timestamp=time.time(),
            data=data,
            previous_hash=previous_block.hash,
        )
        new_block.mine_block(self.difficulty)
        self._save_block(new_block, record_type, created_by)
        return new_block

    def get_latest_block(self) -> Optional[Block]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM blocks ORDER BY block_index DESC LIMIT 1"
            ).fetchone()
            return self._row_to_block(row) if row else None
        finally:
            conn.close()

    def get_block(self, index: int) -> Optional[Block]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM blocks WHERE block_index = ?", (index,)
            ).fetchone()
            return self._row_to_block(row) if row else None
        finally:
            conn.close()

    def get_chain_length(self) -> int:
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) FROM blocks").fetchone()
            return int(row[0])
        finally:
            conn.close()

    def get_full_chain(self) -> List[Block]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM blocks ORDER BY block_index").fetchall()
            return [self._row_to_block(r) for r in rows]
        finally:
            conn.close()

    # ----------------------------- verification ----------------------------
    def verify_chain(self) -> Tuple[bool, List[dict]]:
        """Full chain verification:
        1. Hash integrity (stored hash == recomputed)
        2. Chain linkage (previous_hash round-trips)
        3. Proof of work (hash starts with DIFFICULTY zeros)
        Returns (is_valid, issues).
        """
        chain = self.get_full_chain()
        issues: List[dict] = []
        if not chain:
            return True, issues
        if chain[0].index != 0 or chain[0].previous_hash != self.GENESIS_PREV:
            issues.append(
                {"block": 0, "issue": "BAD_GENESIS", "detail": "Genesis block malformed"}
            )
        for i in range(1, len(chain)):
            current = chain[i]
            previous = chain[i - 1]
            if isinstance(current.data, dict) and "__corrupt_data__" in current.data:
                issues.append(
                    {
                        "block": i,
                        "issue": "INVALID_DATA",
                        "detail": "Stored block data is not valid JSON (tampered)",
                    }
                )
            if current.hash != current.compute_hash():
                issues.append(
                    {
                        "block": i,
                        "issue": "HASH_MISMATCH",
                        "detail": "Block data has been tampered",
                    }
                )
            if current.previous_hash != previous.hash:
                issues.append(
                    {
                        "block": i,
                        "issue": "CHAIN_BROKEN",
                        "detail": "Chain linkage broken - tampering detected",
                    }
                )
            target = "0" * self.difficulty
            if not (current.hash or "").startswith(target):
                issues.append(
                    {
                        "block": i,
                        "issue": "INVALID_POW",
                        "detail": "Proof of work invalid",
                    }
                )
        return len(issues) == 0, issues

    # ------------------------------ queries --------------------------------
    def get_alert_history(self, alert_id: str) -> List[Block]:
        """Complete immutable history of an alert (its chain of custody)."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM blocks WHERE data LIKE ? ORDER BY block_index",
                (f"%{alert_id}%",),
            ).fetchall()
            return [self._row_to_block(r) for r in rows]
        finally:
            conn.close()

    def get_records_by_type(self, record_type: str, limit: int = 100) -> List[Block]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM blocks WHERE record_type = ? ORDER BY block_index DESC LIMIT ?",
                (record_type, limit),
            ).fetchall()
            return [self._row_to_block(r) for r in rows]
        finally:
            conn.close()

    def get_statistics(self) -> dict:
        """Chain statistics for the dashboard + verify status."""
        conn = self._connect()
        try:
            total = conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
            by_type = conn.execute(
                "SELECT record_type, COUNT(*) FROM blocks GROUP BY record_type"
            ).fetchall()
            latest = conn.execute(
                "SELECT block_index, hash FROM blocks ORDER BY block_index DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        ok, issues = self.verify_chain()
        return {
            "total_blocks": total,
            "chain_length": total,
            "difficulty": self.difficulty,
            "records_by_type": dict((str(k), v) for k, v in by_type),
            "latest_index": latest["block_index"] if latest else None,
            "latest_hash": latest["hash"] if latest else None,
            "is_valid": ok,
            "verification_issues": issues,
        }

    # --------------------------- tamper demo -------------------------------
    def tamper_demo(self, index: int | None = None) -> dict:
        """DEMO ONLY: corrupt one block's stored data (re-write raw without a new
        hash) so verify_chain() reports it. Backs up the original row first and
        returns it so `restore_demo()` can repair the chain exactly."""
        index = index if index is not None else 1  # avoid corrupting genesis normally
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM blocks WHERE block_index = ?", (index,)
            ).fetchone()
            if row is None:
                return {"error": f"block {index} not found"}
            backup = {
                "index": row["block_index"],
                "timestamp": row["timestamp"],
                "data": row["data"],
                "previous_hash": row["previous_hash"],
                "nonce": row["nonce"],
                "hash": row["hash"],
                "record_type": row["record_type"],
                "created_by": row["created_by"],
            }
            (self.db_path.parent / "blockchain_tamper_backup.json").write_text(
                json.dumps(backup), encoding="utf-8"
            )
            # Corrupt the stored data string without recomputing hash.
            corrupted = row["data"].replace(":", "-") if ":" in row["data"] else row["data"] + "!"
            conn.execute(
                "UPDATE blocks SET data=? WHERE block_index=?",
                (corrupted, index),
            )
            conn.commit()
        finally:
            conn.close()
        return {
            "tampered_index": index,
            "backup_written": "blockchain_tamper_backup.json",
            "note": "verify_chain() should now report HASH_MISMATCH/_CHAIN_BROKEN",
        }

    def restore_demo(self, index: int | None = None) -> dict:
        """DEMO ONLY: restore the tampered block from its backup file."""
        from backend.config import ARTIFACT_DIR  # local import to avoid cycle at import time

        backup_file = self.db_path.parent / "blockchain_tamper_backup.json"
        if not backup_file.exists():
            # also try the artifact dir used by the older ledger demo
            alt = ARTIFACT_DIR / "blockchain_tamper_backup.json"
            if alt.exists():
                backup_file = alt
            else:
                return {"error": "no backup file found"}
        import json as _json

        backup = _json.loads(backup_file.read_text(encoding="utf-8"))
        index = index or backup["index"]
        conn = self._connect()
        try:
            conn.execute(
                """UPDATE blocks SET timestamp=?, data=?, previous_hash=?, nonce=?,
                   hash=?, record_type=?, created_by=? WHERE block_index=?""",
                (
                    backup["timestamp"],
                    backup["data"],
                    backup["previous_hash"],
                    backup["nonce"],
                    backup["hash"],
                    backup["record_type"],
                    backup["created_by"],
                    index,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        ok, issues = self.verify_chain()
        return {"restored_index": index, "is_valid": ok, "issues": issues}


# ---------------------------------------------------------------------------
# Singleton / accessor
# ---------------------------------------------------------------------------
_chain: Optional[CashGuardChain] = None


def get_chain() -> CashGuardChain:
    """Process-wide singleton chain bound to the configured SQLite file."""
    global _chain
    if _chain is None:
        from backend.config import BLOCKCHAIN_DB_PATH, BLOCKCHAIN_DIFFICULTY

        _chain = CashGuardChain(db_path=BLOCKCHAIN_DB_PATH, difficulty=BLOCKCHAIN_DIFFICULTY)
    return _chain
