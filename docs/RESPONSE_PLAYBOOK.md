# RESPONSE_PLAYBOOK — Graded Action Steps per Alert

Every alert carries `recommended_actions`: a **graded, escalation-bounded** step
list so an officer/bank operator knows exactly what to do next. All steps are
**advisory** — no automated enforcement exists anywhere in the system; an
audited human decision is required before any action that affects a citizen.

## Step ladder (applies per alert; escalate with risk score)

| Step | Action | Owner | When |
|------|--------|-------|------|
| 1 | **Notify branch** — inform branch manager + cash-in-charge of the flagged ATM | Bank | risk ≥ 0.70 |
| 2 | **Heighten transaction monitoring** — watch withdrawals at the ATM for mule-behavioural patterns (linked accounts, chunking, velocity) | Bank | risk ≥ 0.70 |
| 3 | **CCTV / pre-position request** — request CCTV review + optional visible police presence near the ATM window | Police (SHO) | risk ≥ 0.85 |
| 4 | **Tighten withdrawal verification** — for flagged linked-account tokens, require additional verification / hold on suspicious transactions per bank policy + CFCFRMS path | Bank + I4C | risk ≥ 0.85 |

## Jurisdiction & recipients

- `recommended_recipients` on the alert resolves state → district → police
  station area → owning bank. Cross-state coordination is Tier 2 (depends on
  non-public MHA/I4C protocols).
- Notifications are simulated (SMS/email) and the API channel POSTs to the
  local mock I4C inbox — the path is real, the gateways are mock.

## Ethics (non-negotiable)

1. **Advisory only** — the system recommends; humans decide and act.
2. **No automated freezing** — fund-block recommendations require a bank
   officer's explicit `held`/`recovered` action in the UI.
3. **Auditable** — every status change and report is appended to the
   tamper-evident ledger.
4. **Anti-profiling** — no demographic dimensions exist in any feature; risk is
   transaction behaviour + complaint linkage + transaction geography only.
5. **Concentration monitor** — `backend/eval/fairness_check.py` tracks
   geographic concentration of alerts over time (see
   `artifacts/fairness_report.json`).