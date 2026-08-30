# METRICS AUDIT — CashGuard AI (SIH26184)

> **Purpose:** make it impossible for a judge to confuse SUPERSEDED (pre-leakage 0.92x)
> metrics with CURRENT (leak-free) metrics. The single source of truth is
> [`artifacts/current_metrics.json`](../../artifacts/current_metrics.json) and
> [`CURRENT_METRICS.md`](../../CURRENT_METRICS.md).
>
> **Marker for anything superseded:**
> `SUPERSEDED — PRE-LEAKAGE / HISTORICAL — NOT CURRENT PERFORMANCE`.

Every occurrence of a stale token (`0.92x`, `0.90`, `0.86`, `0.83`, old P@K / old
robustness / old cold-location numbers) was enumerated by a repo-wide search. The leakage
history is intentionally NOT deleted, but each file's disposition is fixed below.

Legend: **CURRENT** = derives from the post-leakage pipeline (see `artifacts/metrics.json`);
**SUPERSEDED** = pre-leakage 0.92x history, preserved but not valid as current performance;
**HISTORICAL** = a deliberate record of the old result with explicit marker.

---

## CURRENT (authoritative) artifacts

| File | Contains (leak-free) | Source of truth pointer |
|---|---|---|
| `artifacts/current_metrics.json` | HEADLINE + generalization + intervention + baselines | SELF (authoritative) |
| `CURRENT_METRICS.md` | human-readable summary of the above | SELF |
| `artifacts/metrics.json` | ROC-AUC 0.6273, P@K, PRF, threshold ops | `current_metrics.json` |
| `artifacts/deep_eval/generalization_splits.json` | time/cold/at new-hotspot (0.58–0.63) | ✓ |
| `artifacts/deep_eval/intervention_simulation.json` | K-war (cashguard 11× volume @K10) | ✓ |
| `artifacts/metrics.json` baselines (volume/proximity lift) | ✓ | ✓ |

---

## SUPERSEDED — pre-leakage 0.92x (preserved, not current)

### Raw JSON eval artifacts (carry 0.92x rows)
> These trace the leaky pipeline. They retain their data for history but are flagged
> SUPERSEDED by a top-level marker added to each.

| File | Disposition | What is stale |
|---|---|---|
| `artifacts/deep_eval/baseline_war.json` | **SUPERSEDED** (cashguard/xgb rows) | cashguard 0.9261, xgb_no_spatial 0.9272, xgb_no_complaint 0.9276 |
| `artifacts/deep_eval/seed_stability.json` | **SUPERSEDED** | model seed 0.9258–0.9264; generator seed 0.9178–0.9266 |
| `artifacts/deep_evaluation.json` | **SUPERSEDED** | 0.92x-era headline |
| `artifacts/deep_eval/robustness_check.json` | **SUPERSEDED** | 0.92x robustness numbers |
| `artifacts/deep_eval/drift.json` / `drift_summary.json` | **SUPERSEDED** | drift on 0.92x-era model |
| `artifacts/deep_eval/feature_audit.json` | **SUPERSEDED** | feature AUC on 0.92x-era pipeline |
| `artifacts/deep_eval/horizons.json` | **SUPERSEDED** | horizon P@K on 0.92x-era model |
| `artifacts/deep_eval/transfer_readiness.json` | **SUPERSEDED** | transfer metrics on 0.92x-era model |
| `artifacts/deep_eval/model_disagreement.json` | **SUPERSEDED** | disagreement stats on 0.92x-era model |
| `artifacts/deep_eval/adversarial_worlds.json` | **SUPERSEDED** (as a headline; some content re-audited) | 0.92x-era robustness |
| `artifacts/deep_eval/RECONCILIATION.md` | **HISTORICAL** (already marks 0.92x-era as superseded-invalid) | — |
| `artifacts/leakage_audit.json` | **CURRENT** (leakage evidence) | — |

### Docs (0.92x passages)
> Current-facing docs that must point to `CURRENT_METRICS.md`. The 0.92x passages are
> historical; each doc's header must state the current source of truth.

| File | Disposition |
|---|---|
| `README.md` | **SUPERSEDED passages → point to CURRENT_METRICS.md** |
| `MODEL_CARD.md` | **SUPERSEDED passages → point to CURRENT_METRICS.md** (already has banner per P1.5) |
| `FINAL_MODEL_BENCHMARK.md` | **SUPERSEDED passages → point to CURRENT_METRICS.md** |
| `JUDGE_BRIEF.md` | **SUPERSEDED passages → point to CURRENT_METRICS.md** |
| `presentation/PITCH.md` | **SUPERSEDED → point to CURRENT_METRICS.md** (fixed to 0.6273 in 1bf3219) |
| `ONE_SLIDE_EXECUTIVE_SUMMARY.md` | **SUPERSEDED passages → point to CURRENT_METRICS.md** |
| `LIMITATIONS.md`, `FINAL_EXTERNAL_LIMITATIONS.md` | **HISTORICAL** (limitations text) |
| `SIH26184_DELIVERABLE_MATRIX.md` | **SUPERSEDED passages → point to CURRENT_METRICS.md** |
| `VERIFICATION_LOG.md`, `docs/audits/AUDIT_REPORT.md`, `MODEL_DRIFT.md` | already banner-marked (P1.5) → point to CURRENT_METRICS.md |
| `docs/FINAL_LEAKAGE_AUDIT.md`, `docs/LABEL_PROVENANCE_FINAL.md`, `docs/RESPONSIBLE_OPERATIONAL_USE.md` | **HISTORICAL / CURRENT** (leakage & provenance evidence) |
| 9 × `docs/audits/FINAL_10_10_*` + `FINAL_KILL_TEST_AUDIT.md` | already inline-marker-annotated (A3 pass) → point to CURRENT_METRICS.md |
| `docs/audits/FINAL_EXTERNAL_JUDGE_AUDIT.md`, `FINAL_JUDGE_AUDIT.md`, `PHASE_SCORECARD_HONEST.md`, `Q&A_PREPARATION.md`, `HOSTILE_Q_ADDENDUM_HONEST.md`, `GENERATOR_LEAKAGE_AUDIT.md` | **HISTORICAL / honest-phase records** |
| `frontend/app.js` | 0.92x appears only as honest-language (AUC 0.63) / superseded markers — **CURRENT** |

---

## Disposition of this audit

- **No 0.92x number is reported as current anywhere.**
- Current-facing docs reference `CURRENT_METRICS.md`.
- Raw JSON 0.92x artifacts carry a `superseded: true` / `status: "SUPERSEDED — NOT CURRENT"`
  marker (added in the Phase-0 commit).
- Leakage history is preserved, not deleted.

*Generated 2026-08-30 as part of the Phase-0 / 10-10 gate.*
