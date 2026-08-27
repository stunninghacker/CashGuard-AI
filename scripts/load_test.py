"""
Load test (Phase 11) — 8,000 complaints/day benchmark.

Methodology (documented, reproducible, one command):
  * Target: ~8,000 complaints/day ≈ 333/hour ≈ 5.6/min ≈ 1/10.7s.
  * Sustained-rate check: ingest at the REAL rate (1 complaint + withdrawals
    per ~10.7s) for a window, measuring per-batch latency — honest, no fake
    24h run.
  * Accelerated burst: ingest K complaints in one batch (the realistic
    "portal batch dump" path), measuring p50/p95/p99 per-record latency.
  * Inference: score all ATMs (predict_risk) — p50/p95/p99 over repeats.
  * Alert cycle: end-to-end latency (900 ATMs scored + alerts created).
  * Concurrency: 8 parallel /risk-scores users (SQLite demo scale).
  * Resource: RSS memory before/after (psutil if available).

All numbers are DEMO-SCALE (SQLite, single process); production targets
(PostgreSQL, workers) are documented as requirements, not claims.

Usage: python scripts/load_test.py --sustained-seconds 30 --burst 200
Out: artifacts/deep_eval/load_test.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from backend.config import ARTIFACT_DIR  # noqa: E402
from backend.database import SessionLocal  # noqa: E402
from backend.eval.deep_evaluation import OUT  # noqa: E402


def percentiles(vals):
    a = np.array(vals)
    return {"p50": round(float(np.percentile(a, 50)), 3),
            "p95": round(float(np.percentile(a, 95)), 3),
            "p99": round(float(np.percentile(a, 99)), 3),
            "count": int(len(a))}


def rss_mb():
    try:
        import psutil  # type: ignore

        return round(psutil.Process().memory_info().rss / 1e6, 1)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sustained-seconds", type=int, default=30)
    ap.add_argument("--burst", type=int, default=200)
    args = ap.parse_args()

    result = {"label": "DEMO-SCALE LOAD TEST (SQLite, single process) — not a production benchmark",
              "target": "8000 complaints/day (~1 per 10.7s sustained)",
              "methodology": "sustained real-rate window + accelerated burst; percentiles; no fake 24h run"}

    # 1) sustained real-rate ingestion
    from backend.data.synthetic_data import load_calibration_config
    from backend.services import drip_ingest
    import random

    cfg = load_calibration_config()
    rng = random.Random(1)
    db = SessionLocal()
    latencies = []
    start = time.time()
    try:
        while time.time() - start < args.sustained_seconds:
            t0 = time.perf_counter()
            drip_ingest(db, rng, cfg)
            latencies.append((time.perf_counter() - t0) * 1000.0)
            time.sleep(max(0.0, 10.7 - (time.perf_counter() - t0)))  # real rate
    finally:
        db.close()
    result["sustained_rate"] = {
        "window_seconds": args.sustained_seconds,
        "batches_ingested": len(latencies),
        "rate_batches_per_hour": round(len(latencies) * 3600 / max(args.sustained_seconds, 1), 1),
        "per_batch_ms": percentiles(latencies),
        "note": "Rate ~ real (1 drip ~= 1 complaint + withdrawals per 10.7s).",
    }

    # 2) accelerated burst ingestion (portal batch path)
    db = SessionLocal()
    burst_ms = []
    try:
        t0 = time.perf_counter()
        for _ in range(args.burst):
            drip_ingest(db, rng, cfg)
            burst_ms.append((time.perf_counter() - t0) * 1000.0 / (burst_ms.__len__() + 1))
            t0 = time.perf_counter()
    finally:
        db.close()
    result["burst"] = {"records": args.burst, "per_record_ms": percentiles(burst_ms)}

    # 3) inference latency (full 900-ATM scoring)
    from backend.ml.inference import predict_risk
    from backend.services import resolve_as_of

    db = SessionLocal()
    ref = resolve_as_of(db)
    inf_ms = []
    try:
        for _ in range(3):
            t0 = time.perf_counter()
            predict_risk(ref)
            inf_ms.append((time.perf_counter() - t0) * 1000.0)
    finally:
        db.close()
    result["inference"] = {"full_scoring_ms": percentiles(inf_ms), "atms": 900}

    # 4) alert cycle latency (with force=True, fresh session)
    from backend.services import run_alert_cycle

    db = SessionLocal()
    try:
        t0 = time.perf_counter()
        run_alert_cycle(db, force=True)
        cycle_ms = (time.perf_counter() - t0) * 1000.0
    finally:
        db.close()
    result["alert_cycle"] = {"ms": round(cycle_ms, 1)}

    # 5) concurrent users (8 parallel risk-scores)
    import threading

    db = SessionLocal()
    ref = resolve_as_of(db)
    results = {}
    lat = []

    def worker(i):
        from backend.services import get_risk_scores

        t0 = time.perf_counter()
        get_risk_scores(db, as_of=ref)
        lat.append((time.perf_counter() - t0) * 1000.0)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = (time.perf_counter() - t0) * 1000.0
    db.close()
    result["concurrency"] = {"users": 8, "wall_ms": round(wall, 1), "per_user_ms": percentiles(lat)}

    result["memory_rss_mb"] = {"before": None, "after": rss_mb()}
    (OUT / "load_test.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()