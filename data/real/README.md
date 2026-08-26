# data/real/ — Real-data validation inputs (Phase 2 grounding)

This directory is the plug-in point for **real/public aggregate complaint data**.
The harness `backend/eval/real_data_harness.py` reads any CSV here and validates
the framework's predicted hotspot density against it. Nothing is invented:
when this directory is empty, `artifacts/real_validation.json` reports
`PENDING_REAL_DATA` — an honest, runnable harness instead of a promise.

## Schema (one file is enough)

| column          | type   | meaning                                   |
|-----------------|--------|-------------------------------------------|
| `district`      | str    | district name (see matching rule below)   |
| `date`          | date   | ISO date (YYYY-MM-DD) of the aggregate    |
| `complaint_count` | int  | complaints filed in that district/date    |

Example row:

```csv
district,date,complaint_count
Northsagar,2026-08-01,47
Metro-West,2026-08-01,31
```

## Matching rule

- `district` values that match the framework's **fictional** districts
  (Northsagar, Metro-West, Greenfield, District-3, Eastvale) enable a direct
  Spearman correlation between predicted hotspot density and real complaint
  density (written to `artifacts/real_validation.json`).
- Real NCRP/I4C district names can be supplied together with a mapping to the
  fictional districts in a second column (`fictional_district`) — add that
  column and the harness will prefer it if present.
- Any other content → `PENDING_REAL_DATA` with the mismatch listed (no invented
  numbers, ever).

## Where real data would come from in production

- I4C / NCRP aggregate complaint dashboards (district-level counts are
  published in aggregate form; raw PII stays access-controlled).
- RBI financial-fraud trend publications (national/state aggregates).
- State police cyber-crime cells' published district bulletins.

Drop files here, re-run `python -m backend.eval.real_data_harness`, and the
validation result lands in `artifacts/real_validation.json`.