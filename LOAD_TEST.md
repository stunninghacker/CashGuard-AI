# LOAD_TEST.md — 8,000 Complaints/Day Benchmark (Phase 11)

Artifact: `artifacts/deep_eval/load_test.json` · Run: `python scripts/load_test.py`
(one command, reproducible; `--sustained-seconds` and `--burst` configurable).

## Methodology (honest, no fake 24h)
- **Sustained real-rate window**: ~8,000 complaints/day ≈ 1 per 10.7s. We
  ingested at the REAL rate for a 32s window (3 batches, 337.5/h projected)
  and measured per-batch latency. A real 24h run is unnecessary for a
  prototype benchmark and we do not fake one.
- **Accelerated burst**: 150 records in one batch (the realistic "portal batch
  dump" path) → per-record latency percentiles.
- **Inference**: full 900-ATM scoring, repeated.
- **Alert cycle**: end-to-end (score 900 + create alerts).
- **Concurrency**: 8 parallel /risk-scores users.
- Platform: single process, SQLite, Windows dev machine. **This is a
  DEMO-SCALE benchmark, not a production claim.**

## Results (from the artifact)

| Metric | p50 | p95 | p99 |
|---|---|---|---|
| Sustained-rate batch (1 complaint + withdrawals) | 52 ms | 87 ms | 90 ms |
| Burst per-record (150-record batch) | 0.18 ms | 2.2 ms | 8.5 ms |
| Full 900-ATM inference | 3.63 s | 4.03 s | 4.07 s |
| Alert cycle (score + alert) | 3.39 s | — | — |
| 8 concurrent users (per user) | 55.6 s | 65.2 s | 65.4 s |

## Interpretation (honest)
1. **Ingestion easily sustains 8,000 complaints/day** — per-batch latency is
   ~50–90 ms at the real rate; even a 150-record burst costs <10 ms/record.
   The rate ceiling is the drip path, not the DB.
2. **Inference is the cost center**: 3.6–4.1 s for 900 ATMs. At one alert
   cycle/hour that is trivial; at sub-hourly cadence it needs the PostgreSQL +
   worker scale-up (the documented production path).
3. **Concurrency is the demo's honest weakness**: 8 parallel users serialize on
   SQLite (single-writer) → 55 s/user. This is WHY the architecture documents
   the SQLite → PostgreSQL swap (one config value). Under PostgreSQL with a
   connection pool, concurrent inference is read-parallel — a production
   requirement, not yet a measured claim.

## Production requirements (documented, not claimed)
- PostgreSQL + connection pooling for concurrent reads.
- Inference cache (risk scores valid within a window; recompute hourly, not
  per request).
- Worker processes for scheduled retraining; Kafka for true stream ingestion.
- Load-test re-run on the production stack is a pilot-phase task.