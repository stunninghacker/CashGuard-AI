# LOAD_TEST.md — 8,000 Complaints/Day Benchmark

Artifact: `artifacts/deep_eval/load_test.json` · Run: `python scripts/load_test.py`
(one command, reproducible; `--sustained-seconds` and `--burst` configurable).

## Methodology (honest, no fake 24h)
- **Sustained real-rate window**: ~8,000 complaints/day ≈ 1 per 10.7s. We
  ingested at the REAL rate for a 30s window (3 batches, 360/h projected)
  and measured per-batch latency. A real 24h run is unnecessary for a
  prototype benchmark and we do not fake one.
- **Accelerated burst**: 200 records in one batch (the realistic "portal batch
  dump" path) → per-record latency percentiles.
- **Inference**: full 900-ATM scoring, repeated.
- **Alert cycle**: end-to-end (score 900 + create alerts).
- **Concurrency**: 8 parallel /risk-scores users.
- Platform: single process, SQLite, Windows dev machine. **This is a
  DEMO-SCALE benchmark, not a production claim.**

## Results (from the artifact, regenerated on the iteration-4 data/model)

| Metric | p50 | p95 | p99 |
|---|---|---|---|
| Sustained-rate batch (1 complaint + withdrawals) | 22 ms | 36 ms | 38 ms |
| Burst per-record (200-record batch) | 0.11 ms | 1.0 ms | 4.1 ms |
| Full 900-ATM inference | 2.69 s | 2.98 s | 3.02 s |
| Alert cycle (score + alert) | 2.81 s | — | — |
| 8 concurrent users (per user) | 66.7 s | 71.9 s | 72.0 s |

## Interpretation (honest)
1. **Ingestion easily sustains 8,000 complaints/day** — per-batch latency is
   ~22–38 ms at the real rate; even a 200-record burst costs <10 ms/record.
   The rate ceiling is the drip path, not the DB.
2. **Inference is the cost center**: 2.7–3.0 s for 900 ATMs. At one alert
   cycle/hour that is trivial; at sub-hourly cadence it needs the PostgreSQL +
   worker scale-up (the documented production path).
3. **Concurrency is the demo's honest weakness**: 8 parallel users serialize on
   SQLite (single-writer) → 67–72 s/user. This is WHY the architecture documents
   the SQLite → PostgreSQL swap (one config value). Under PostgreSQL with a
   connection pool, concurrent inference is read-parallel — a production
   requirement, not yet a measured claim.

## Production requirements