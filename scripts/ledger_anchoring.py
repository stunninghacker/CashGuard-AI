"""Ledger anchoring + replication demo (Blockchain & Cybersecurity theme).

Shows, live:
  1. the existing tamper-evident hash chain replicated across 3 nodes
     (majority-quorum writes, per-node verification),
  2. fault tolerance: 1 node down -> writes still succeed; 2 nodes down ->
     writes fail (no quorum) — honest failure,
  3. periodic anchoring: the consensus root is committed as an anchor record
     (integration point for a real testnet RPC — not exercised here).

Run: python scripts/ledger_anchoring.py
Out: artifacts/deep_eval/ledger_replication.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.database import SessionLocal  # noqa: E402
from backend import repositories as repo  # noqa: E402
from backend.ledger_replication import ReplicaNetwork  # noqa: E402
from backend.eval.deep_evaluation import OUT  # noqa: E402


def main():
    db = SessionLocal()
    try:
        records = repo.ledger_chain(db)
    finally:
        db.close()
    print(f"replicating {len(records)} existing ledger blocks across 3 nodes...")

    net = ReplicaNetwork()
    for r in records:
        net.replicate(r.actor, r.event_type, r.payload_hash)

    status0 = net.network_status()
    print(f"  nodes: {[(s['node'], s['blocks'], s['intact']) for s in status0['nodes']]}")
    print(f"  consensus root: {status0['consensus_root'][:16]}...")

    # anchor #1
    a1 = net.anchor_record("anchor-1")
    print(f"  anchor-1: ok={a1['ok']} acks={a1.get('acks')} hash={a1.get('block', {}).get('hash', '')[:16]}")

    # fault tolerance: node-C down
    net.set_down("node-C", True)
    a2 = net.anchor_record("anchor-2")
    print(f"  node-C down -> anchor-2: ok={a2['ok']} acks={a2.get('acks')} (expect ok, quorum 2/2)")
    a3 = net.anchor_record("anchor-3")
    net.set_down("node-B", True)  # now 1 alive of 3
    a4 = net.anchor_record("anchor-4")
    print(f"  node-B+C down -> anchor-4: ok={a4['ok']} error={a4.get('error')} (expect no-quorum)")
    net.set_down("node-B", False)
    net.set_down("node-C", False)

    # tamper detection on one node: flip a block
    target = net.nodes["node-C"].log[len(net.nodes["node-C"].log) // 2]
    target["payload_hash"] = ("0" * 64) if target["payload_hash"] != ("0" * 64) else ("1" * 64)
    status1 = net.network_status()
    print(f"  tamper node-C -> intact: {[(s['node'], s['intact']) for s in status1['nodes']]} (expect node-C False)")

    out = {
        "label": "DEMO-GRADE REPLICATION + ANCHORING SIMULATION - not a public/permissioned blockchain",
        "replicated_blocks": len(records),
        "network": status1,
        "anchors": {
            "anchor_1": {"ok": a1["ok"], "acks": a1.get("acks"), "hash": a1.get("block", {}).get("hash")},
            "anchor_2_nodeC_down": {"ok": a2["ok"], "acks": a2.get("acks")},
            "anchor_4_no_quorum": {"ok": a4["ok"], "error": a4.get("error")},
        },
        "honest_notes": {
            "real": "replicated append-only log, majority-quorum writes, per-node tamper detection, fault tolerance",
            "simulated": "in-process transport (single machine); external testnet anchoring is an integration point (config LEDGER_ANCHOR_RPC_URL), NOT exercised",
            "tamper_evidence": "the original SHA-256 chain remains the authoritative audit trail; replication adds redundancy and consensus-style anchoring",
        },
    }
    (OUT / "ledger_replication.json").write_text(json.dumps(out, indent=2))
    print("saved:", OUT / "ledger_replication.json")


if __name__ == "__main__":
    main()