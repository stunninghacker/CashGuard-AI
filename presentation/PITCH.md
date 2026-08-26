# CashGuard AI — 5-Minute Demo Pitch (Judges' Walkthrough)

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

- **4 layers**: Data (synthetic NCRP/bank feeds) · ML (XGBoost, 20 features, time-split eval)
  · API (FastAPI, repo-layer swappable to PostgreSQL/real APIs) · Frontend (role-based).

## Slide 3 — Live Demo (2 min 30 sec)
1. `python run.py` — show pipeline logs (calibration summary → data → train → serve).
2. **Police view**: Leaflet heatmap (red = critical), city filter, top-20 hotspots table.
3. **⚡ Run Alert Cycle** → SMS/email mock logs for SHOs & branch managers, dedupe cooldown.
4. **Alert → Details → 3-field evidence panel**: complaint activity, withdrawal activity,
   context signal with **VERIFIED/ASSUMED source disclosure**, fired rule, feature
   contributions (global importance + percentile — **NOT SHAP**).
5. **Acknowledge / Actioned** — state persists (audit trail).
6. **Bank view**: pick a bank → only its ATMs, risk + suggested actions.
7. `/docs` — full REST API (integration-ready contracts).

## Slide 4 — The Numbers (30 sec)
- 200k transactions, 12k complaints, 900 ATMs, 5 **fictional** cities, 6 months.
- **ROC-AUC 0.9362 · lift vs volume 1.176–2.128× · lift vs proximity 8.333–10.0×** (the
  model crushes both naive baselines, disclosed) · **median lead-time 14.1 h**
  — annotated as horizon-dependent, a design property not an accuracy claim.
- **Novelty**: Hawkes self-exciting intensity over past complaints
  (single-feature AUC 0.52 — leak-free). The ensemble is honestly disclosed as
  NOT beating pure XGBoost (0.8153 vs 0.9362) — active model = xgboost.
- **Leak-free metrics (from `artifacts/metrics.json`)**: `precision@20/50/100/
  1000 = 1.0/1.0/1.0/0.782; threshold(≥0.7) precision = 0.81; max single-feature
  AUC = 0.85 (counterparty_count_24h, complaint-linked activity — available at
  prediction time)`. Residual top-K certainty is disclosed as a known
  limitation, not claimed as a virtue.
- Every metric is measured on **synthetic labels** — lead with that, always.
- **Real-data harness**: `backend/eval/real_data_harness.py` is runnable
  today; status PENDING_REAL_DATA until a real aggregate CSV is supplied —
  nothing invented.

## Slide 5 — Production Path & Future (45 sec)
- Swap repositories → live NCRP/CFCFRMS + bank/NPCI feeds (schema-compatible, jurisdiction fields included).
- Mock SMS/email → NIC SMS / SendGrid / I4C webhook (one file).
- OAuth2/JWT roles; PostgreSQL via `DATABASE_URL`; Dockerized; DEMO_MODE fallback is stage-only.
- **Future**: blockchain-based tamper-evident alert audit log; model drift monitoring;
  federated learning across banks; true SHAP; inter-agency routing per MHA protocols.

### Why `counterparty_count_24h` is not a leak (numbers from `artifacts/metrics.json`)
(a) Built from complaint-linked accounts — complaints are filed *before*
cash-out, so the signal is available at prediction time; (b) it is a
trailing-window aggregate ending before the forecast point, not the label
window; (c) its single-feature AUC is **0.8457**, not 1.0 — no single feature
is decisive; (d) the ranking decays to **0.782 at K=1000** (threshold ≥0.7
precision 0.7927) — a genuine leak would stay ≈1.0 throughout.

## Closing (15 sec)
"CashGuard AI doesn't react to crime — it **intercepts the cash before the criminal can touch it**.
Proactive policing, funded-loss prevention, and a data-driven defense for India's cybercrime ecosystem."

---

### Judge Q&A cheat sheet
- **Why XGBoost?** Tabular spatio-temporal data, fast training, built-in early stopping; histogram trees handle 160k rows in seconds; interpretable via feature importance.
- **Why not deep learning?** Hackathon scope — classical ML with engineered features gives better explainability to LEAs and needs no GPU.
- **How is this different from a fraud-detection system?** Fraud detection flags *past* transactions; we predict *future locations* and drive *deployments*.
- **Data privacy?** All synthetic; production uses anonymized/aggregated complaint fields, role-based access, audit logs.
- **False positives?** Precision@K is the operational metric — we tune for "deployments that pay off", plus alert cooldown dedupe.