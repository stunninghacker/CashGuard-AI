# CashGuard AI — 5-Minute Demo Pitch (Judges' Walkthrough)

> **Source of truth for current metrics:** `CURRENT_METRICS.md` + `artifacts/current_metrics.json`.
> Honest, leak-free ROC-AUC **0.6456** (5-fold CV 95% CI: [0.6350, 0.6463]); any 0.92x is SUPERSEDED pre-leakage history.
> Theme: Blockchain & Cybersecurity · Ministry of Home Affairs · I4C, CIS Division
> Team positioning: "We turn 8,000 reactive complaints/day into proactive police deployments."

---

## Slide 0 — Hook (30 sec)
"Every hour, fraudsters cash out victim funds from an ATM somewhere in India. By the time
police act on the complaint, the money is gone. **What if we could tell the SHO tonight
which ATM the fraudster will use tomorrow?** That's CashGuard AI."

## Slide 0b — Evaluation Honesty (20-30 sec, say FIRST)
"Before the numbers: every metric is measured on synthetic labels generated from
*published* fraud patterns — I4C Suspect Registry clustering, IBA mule behaviour, RBI's
2026 lag-credit rule. That proves our methodology — time-based splits, precision-at-K,
robustness-to-perturbation — but it is not real-world precision yet. A pilot with real
NCRP/CFCFRMS data would re-validate everything against investigation-confirmed
withdrawals. Every parameter is source-tagged verified-vs-assumed and disclosed in the UI."

## Slide 1 — Problem (30 sec)
- NCRP: ~8,000 complaints/day, rising.
- Complaints → LEAs → banks act → **cash already withdrawn** → unrecoverable.
- Ask the panel: "If you could predict the *withdrawal location*, recovery rate changes
  from ~0% to interceptable."

## Slide 2 — Solution Flow (45 sec)
`Complaint data + ATM/withdrawal patterns → ML risk engine → 24h hotspot forecast → GIS heatmap + alerts → police deployment & bank monitoring`

- **4 layers**: Data (synthetic NCRP/bank feeds) · ML (XGBoost, 44 features, time-split eval)
  · API (FastAPI, repo-layer swappable to PostgreSQL/real APIs) · Frontend (role-based).

## Slide 3 — Live Demo (2 min 30 sec)
> **Honesty-first default (post-leak-fix):** on a calm demo day the leak-corrected model
> scores every ATM low and shows **no alerts** — say this out loud *up front*, then click
> **"Load Simulated Scenario"** to demonstrate the populated alert → evidence →
> SMS/email/dispatch → bank → action workflow. Every screen in that mode carries an
> unmissable **SIMULATED SCENARIO — NOT LIVE** banner/watermark; "Exit Simulated Mode"
> returns to the honest sparse live view. Do NOT present the scripted alerts as live output.
1. `python run.py` — show pipeline logs (calibration summary → data → train → serve).
2. **Police view**: Leaflet heatmap (red = critical), city filter, top-20 hotspots table.
3. **Run Alert Cycle** → SMS/email mock logs for SHOs & branch managers, dedupe cooldown.
4. **Alert → Details → 3-field evidence panel**: complaint activity, withdrawal activity,
   context signal with **VERIFIED/ASSUMED source disclosure**, fired rule, feature
   contributions (global importance + percentile, plus per-instance TreeSHAP via native pred_contribs).
5. **Acknowledge / Actioned** — state persists (audit trail).
6. **Bank view**: pick a bank → only its ATMs, risk + suggested actions.
7. `/docs` — full REST API (integration-ready contracts).

## Slide 4 — The Numbers (30 sec)
- 200k transactions, 12.4k complaints, 900 ATMs, 5 fictional cities, 6 months.
- **Honest ROC-AUC: 0.6456** (5-fold CV 95% CI: [0.6350, 0.6463]).
- **Precision@K** (post-correction):
  P@20/50/100/200/500/1000 = 0.70/0.70/0.67/0.57/0.434/0.329.
- **Lift vs baselines**: 7.9× random, 3.2× historical hotspot, 17.8× volume at P@100.
- **Lead time**: median 12.8h (P25 8.7h, P75 17.6h) — early-warning, not after-the-fact.
- **Hawkes feature**: single-feature AUC 0.51 — leak-free; ensemble (rank-average XGB+Hawkes)
  scores worse (P@100 0.41 vs 0.67); active model = pure XGBoost.
- Every metric is measured on **synthetic labels** — lead with that, always.
- **Real-data harness**: `backend/eval/real_data_harness.py` is runnable
  today; status PENDING_REAL_DATA until a real aggregate CSV is supplied —
  nothing invented.

## Slide 5 — Production Path & Future (45 sec)
- Swap repositories → live NCRP/CFCFRMS + bank/NPCI feeds (schema-compatible, jurisdiction fields included).
- Mock SMS/email → NIC SMS / SendGrid / I4C webhook (one file).
- OAuth2/JWT roles; PostgreSQL via `DATABASE_URL`; Dockerized; DEMO_MODE fallback is stage-only.
- **Future**: blockchain-based tamper-evident alert audit log; model drift monitoring;
  federated learning across banks; inter-agency routing per MHA protocols.

### Why `counterparty_count_24h` is not a leak
(a) Built from complaint-linked accounts — complaints are filed *before*
cash-out, so the signal is available at prediction time; (b) it is a
trailing-window aggregate ending before the forecast point, not the label
window; (c) its single-feature AUC is **0.5571** on the leak-fixed build —
no single feature is decisive (the strongest single feature, `mule_reuse_count_7d`,
is 0.6008, and `days_since_epoch` is 0.5604) — a leak would show ~1.0; (d) the overall
model is only ROC-AUC 0.6456 with P@20 0.70 decaying to P@1000 0.329 — a
genuine leak would stay ≈1.0/≈high throughout.

## Closing (15 sec)
"CashGuard AI doesn't react to crime — it **intercepts the cash before the criminal can touch it**.
Proactive policing, funded-loss prevention, and a data-driven defense for India's cybercrime ecosystem."

---

### Expected audience questions (preparation)
- **Why XGBoost?** Tabular spatio-temporal data, fast training, built-in early stopping; histogram trees handle 160k rows in seconds; interpretable via feature importance.
- **Why not deep learning?** Hackathon scope — classical ML with engineered features gives better explainability to LEAs and needs no GPU.
- **How is this different from a fraud-detection system?** Fraud detection flags *past* transactions; we predict *future locations* and drive *deployments*.
- **Data privacy?** All synthetic; production uses anonymized/aggregated complaint fields, role-based access, audit logs.
- **False positives?** The system's job is *triage*: the monitor/review band (≥0.5–0.7)
  keeps a tiny absolute queue (30–60 ATMs/cycle, 67–75% precision) in front of an analyst,
  with alert cooldown dedupe and a human confirm before any dispatch. Rank-based precision
  (7.9× lift over random baselines) is what makes the queue actionable;
  we tune so deployments that do happen pay off, never for volume.
- **5-fold CV confidence interval?** [0.6350, 0.6463] — the honest range of model performance across different data partitions.