"""Restore the tamper-evident ledger after the DEMO tamper step.

Uses the exact-hash backup written by the tamper demo
(artifacts/ledger_tamper_backup.json). Flow: verify OK -> tamper -> verify
FAILS -> run this -> verify OK (the demo's restore story).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import ARTIFACT_DIR  # noqa: E402
from backend.database import SessionLocal  # noqa: E402
from backend import repositories as repo, services  # noqa: E402

db = SessionLocal()
try:
    backup_path = ARTIFACT_DIR / "ledger_tamper_backup.json"
    records = repo.ledger_chain(db)
    if not backup_path.exists():
        print("no tamper backup found - ledger may already be intact")
    else:
        backup = json.loads(backup_path.read_text(encoding="utf-8"))
        target = next((r for r in records if r.index == backup["index"]), None)
        if target is None:
            print(f"backup references index {backup['index']} not in chain")
        elif target.payload_hash == backup["original_payload_hash"]:
            print("ledger already intact at that block")
        else:
            target.payload_hash = backup["original_payload_hash"]
            db.commit()
            print(f"restored block {target.index} to its original payload_hash")
        backup_path.unlink(missing_ok=True)
    v = services.verify_ledger_chain(db)
    print(f"verify intact={v['intact']} records={v['records']}")
finally:
    db.close()