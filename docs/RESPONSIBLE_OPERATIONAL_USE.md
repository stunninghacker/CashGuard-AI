# RESPONSIBLE OPERATIONAL USE — CashGuard AI (SIH26184 prototype)

**Date:** 2026-08-30 · **Integrity:** all numbers are the honest, post-leakage-fix values from
`artifacts/metrics.json`. The earlier 0.92x ROC-AUC was invalidated by a same-day label-leakage fix
and is not valid (see `docs/FINAL_LEAKAGE_AUDIT.md`). Everything below is on **synthetic**
single-region labels (`REAL_DATA_GAP.md`, `LABEL_VALIDITY.md`).

This document sets out the guardrails within which the prototype may be operated and presented. It
does **not** claim production operational maturity.

---

## 1. Sim-chrome invariant (SIMULATED banner / watermark) — preserved

Every screen that shows populated alert/evidence/dispatch content in simulated mode must carry an
unmissable **SIMULATED SCENARIO — NOT LIVE** banner/watermark, and there must be an "Exit Simulated
Mode" control back to the honest sparse live view. This invariant is preserved and verified in the
demo flow — scripted alerts are never presented as live system output. A calm live day must show the
sparse, honest view, not fabricated alerts.

## 2. No-alerts-on-calm-days honesty

On a calm day the leak-corrected model scores every ATM low and produces **no alerts**. The honest
behaviour is to say this out loud up front and then load a simulated scenario to demonstrate the
workflow. The maximum calibrated risk on such a calm day is ~0.0627 (just above the synthetic base
rate of 0.0522), which sits below every dispatch threshold (0.5+), so nothing is flagged. Presenting
scripted alerts as live output would be dishonest and is prohibited.

## 3. Threshold guidance (honest operating points from `metrics.json`)

| Threshold | Alerts | Precision | Recall | False-alert rate |
|---|---|---|---|---|
| 0.85 | 3 | 0.6667 | 0.0007 | 0.3333 |
| 0.7 | 32 | 0.75 | 0.0081 | 0.25 |
| 0.6 | 47 | 0.6383 | 0.0101 | 0.3617 |
| 0.5 | 62 | 0.6613 | 0.0138 | 0.3387 |

Guidance:
- **Dispatch-grade (>= 0.85):** very low volume (~3/candidate cycle) and ~0.8% recall in the
  synthetic window. Use for the most confident dispatches only; never treat ~0.7% recall as "the
  system catches most fraud".
- **Analyst triage (0.5-0.7):** 30-60 ATM/cycle at 67-75% precision. A reasonable operating band for
  human triage, fully aware recall is low and ~25-36% of flags are false positives.
- All thresholds are provisional on synthetic labels; **re-derive thresholds only after a real-data
  pilot** (`REAL_DATA_GAP.md`, `REAL_DATA_VALIDATION_PROTOCOL.md`).

## 4. Human-in-the-loop (mandatory)

Alerts are advisory. Every alert state change (acknowledged / actioned / dismissed / escalated)
requires a recorded human reason and is written to the tamper-evident ledger. Fund-block
recommendations require an explicit bank-officer action; there is no automated enforcement. On
synthetic, uncalibrated probabilities, an automated dispatch decision is not justified — human
judgement is required at every escalation.

## 5. RBAC scoping — verified

Row-level RBAC is enforced in the repository layer and live-verified:
- district officer sees only own district (Northsagar rows only),
- bank sees only own bank,
- state officer sees only own state (State-A),
- I4C admin sees the national view;
- `/train` is I4C_ADMIN-only; `/alerts/run-now` is I4C_ADMIN + POLICE_STATE.

Because the pilot is single-district, true cross-jurisdiction routing still needs real
multi-jurisdiction data (see `FINAL_EXTERNAL_LIMITATIONS.md`); the scoping mechanism itself is
verified.

## 6. Ethics — no real PII, PoC-only

All data is synthetic; account identifiers are pseudonymised tokens (`acct_…`, `tel_…`); no raw PII
is stored or displayed; there are no demographic/community/religion/caste features (anti-profiling by
design). Operation is PoC-only, in-scope for the SIH-26184 prototype, and must not be pointed at real
victim or bank data without an authorized data-access agreement.

## 7. Refusal to overstate operational maturity

This is a demo prototype: synthetic single-region, 180 ATMs, demo-scale, no live traffic, no real
per-ATM fraud benchmark, and no calibration against a real baseline possible on synthetic labels.
Any claim of field readiness, real-world precision, national-scale multi-jurisdiction operations, or
live-traffic maturity would overstate it and is declined. Maturity is reached only through the
authorized real-data pilot path (`REAL_DATA_GAP.md`).

---

*Operate and present this prototype honestly: synthetic labels, honest 0.6273 ROC-AUC, human-in-the-loop,
and simulated-content labelling.*
