# REAL_DATA_VALIDATION_PROTOCOL.md

Formal protocol for moving from the synthetic demo to validation on authorized
real data (NCRP/CFCFRMS/bank feeds). It makes the distinction between the three
operating modes explicit and defines the 14 control points a real-data pilot
must pass before any operational recommendation is made.

## The three operating modes (explicit, never conflated)

| Mode | Data | Alerts/actions | Status today |
|---|---|---|---|
| **SYNTHETIC DEMO** | Generator (`backend/data/synthetic_data.py`, all parameters source-tagged in `calibration_config.yaml`) | Full demo channels (mock SMS/email/webhook, WS push) | **ACTIVE** — this repository |
| **REAL-DATA PILOT** | Authorized NCRP/CFCFRMS/bank feeds, ingested via the repository layer | Shadow mode first (predictions recorded, no dispatch); silent prediction; then human-reviewed interventions only | Not started — requires access agreements (external dependency) |
| **PRODUCTION** | Same real feeds, monitored pipelines | Human-gated decisions, full audit, drift/outcome monitoring | Not started — requires pilot outcomes + MHA/I4C approval |

`SHADOW_MODE=true` is the implemented switch that makes the pilot's Week 2
mechanically possible today: alerts are stored with `status="shadow"` and
SMS/email/dispatch/WS channels are suppressed.

## The 14 protocol steps

### 1. Data onboarding
- ETL/API pull per source: complaints (NCRP portal), withdrawals + ATM master
  (bank/NPCI feeds), CFCFRMS freeze/recovery events. Landing tables match the
  existing schema (`complaints`, `withdrawals`, `atms`, `recovery_recommendations`).
- Every pull is logged to the audit chain (actor = integration job, event_type = ingest).
- Repository layer is the single data door — no route/ML/UI changes required.

### 2. Schema validation
- Each feed is validated against the Pydantic contracts before commit:
  required columns, types, non-null keys, jurisdiction fields
  (`state`/`district`/`police_station_area`) populated, token fields non-empty.
- Rejected rows are quarantined (not dropped silently) with the rejection reason.

### 3. PII minimization
- Raw identifiers are salted-tokenized at ingestion (the existing
  `Pseudonymizer` path); raw values live only in the re-identification vault
  with role-scoped access, per DPDP-aligned minimization (see PRIVACY_MODEL.md).
- No demographic/community/religion/caste fields are collected, period.

### 4. Data quality checks
- Volume sanity per source (daily counts vs expected ranges), null-rate caps,
  duplicate-key detection, out-of-range amounts, timestamp sanity (future/before-epoch).
- A quality scorecard is produced per batch; batches below threshold are held.

### 5. Temporal alignment
- All tables are aligned on a single business-day axis; a data-freshness clock
  (`data_freshness_hours`) is computed per source at every forecast point.
- Stale sources degrade confidence and trigger HOLD ACTION (the freshness
  signal is already in the alert evidence block).

### 6. Label definition
- Ground truth: withdrawal records flagged as confirmed fraud by bank/I4C
  investigation (not by the model), joined to complaints by token linkage.
- The label contract is written down before the pilot: what counts as a fraud
  withdrawal, the confirmation window, and how UNKNOWN outcomes are handled.

### 7. Leakage checks
- Feature windows end strictly before the forecast point (asserted per feature);
  the label is the fraud in the 24h AFTER the forecast point.
- Per-feature AUC audit (the `metrics.json` diagnostic): any single feature at
  AUC ~1.0 is treated as a leak until proven otherwise.
- The leak-guard discipline from CALIBRATION_NOTES.md and MODEL_CARD.md
  ("Why precision@K is not artificially perfect") applies unchanged to real data.

### 8. Train/validation/test split
- Strictly chronological: train → validation (early stopping + calibration
  only) → test. No shuffling across time; no calibration on the test set.
- The split boundary and model version are stored with every alert.

### 9. Shadow mode
- Week 2 of the pilot: predictions run live in parallel with operations but
  nothing is dispatched (`SHADOW_MODE=true`). Alerts are stored with
  `status="shadow"`; channels and WS are suppressed.
- The shadow period produces the model-vs-reality baseline without touching
  operations.

### 10. Calibration
- Platt calibration is refitted on the real validation slice; the alert
  threshold is re-derived from the real operating curve (precision/recall
  trade-off chosen with ops), not carried over from the synthetic demo.
- Brier and the reliability curve are recomputed per month.

### 11. Drift monitoring
- Runtime monitors (see MODEL_OUTCOME_MONITOR.md): feature distribution
  (PSI per feature), prediction distribution, geographic distribution,
  confirmed-fraud rate, model disagreement (A vs B).
- Breach of any threshold → confidence reduction + review flag; the model is
  never silently continued.

### 12. Human review
- Every alert is reviewed by a trained officer before any action; dismiss and
  escalate require a recorded reason; all decisions land on the audit chain.
- No automated police action exists at any stage.

### 13. Success criteria (pilot KPIs)
- Precision@100 ≥ 0.60 and P@1000 ≥ 0.40 on confirmed outcomes (vs ~0.83/0.52
  synthetic — real-world is expected lower; the protocol's success bar is set
  with ops before the pilot, not after).
- Threshold-0.7 false-alert rate < 0.50 (synthetic: 0.38 — must not degrade
  materially).
- Lead time ≥ 6h median between alert and first confirmed withdrawal at
  covered ATMs.
- Intervention simulation re-run on real labels: top-10/day captures a
  material share of exposure vs the no-action baseline.
- Fairness: FPR spread across jurisdictions ≤ 0.01 (synthetic: ≤ 0.005).
- These are pre-registered targets; if a target is missed the pilot reports
  it, it is not redefined retroactively.

### 14. Rollback
- Rollback conditions (pre-agreed): outcome-calibration error rising for two
  consecutive weeks, any single-feature leak confirmed, FPR spread > 0.02,
  or any unauthorized data exposure.
- Rollback = stop recommendations, keep shadow predictions running, restore
  the last model version, document the reason on the audit chain.

## What this does and does not claim
- Claims: a concrete, mechanically executable path from authorized data to
  validated, human-gated operation; every control point is implemented or
  implementable with the existing code (repository layer, shadow mode,
  freshness, audit chain, outcome store).
- Does NOT claim: real data access, any real-world accuracy, any
  government/bank partnership, or that the pilot has started.