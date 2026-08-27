# LIMITATIONS.md — One File, Under a Minute to Read

This prototype is built for a hackathon demonstration. This file states, in one
place, what it does **not** claim — read before quoting any metric or feature.

---

## 1. Evaluation ceiling (the most important one)

**Precision@K, baseline lift and lead-time are measured on synthetic labels
generated from behaviours calibrated to published fraud patterns. This does
NOT equal real-world precision.**

Our claim is:
1. **Methodological rigor** — time-based split with a validation slice (early
   stopping + calibration never touch the test set), precision@K, baseline
   lifts (volume: 14–18×; complaint-proximity: 17× at P@100 — the model
   massively beats a naive "near recent complaints" heuristic, disclosed
   honestly), median lead-time (14.9 h; IQR 9.4–20.0 — annotated
   `lead_time_is_horizon_dependent: true`, a horizon design-property of the
   24h forecast, not an independent accuracy claim), calibration curve +
   confusion matrix, robustness-to-perturbation
   (`artifacts/robustness_check.png`, `calibration_and_confusion.png`).
2. **Honest separability (numbers read from `artifacts/metrics.json`)**
   — the label-leaking feature `fraud_withdrawals_24h` was removed; the
   regenerated held-out-test numbers are: `precision@20/50/100/1000 =
   0.90 / 0.86 / 0.83 / 0.52; threshold(≥0.7) precision = 0.62; max
   single-feature AUC = 0.8447 (feature: counterparty_count_24h)`.
   - **De-separation (iteration 4):** an earlier perfect top-K (P@100 = 1.0)
     was investigated and traced to generator structure (static hot-ATM set +
     demo-wave concentration), NOT to a leak feature. The generator now
     rotates hot-ATM membership, blocks a larger share of mule cash-outs
     (no-label bursts), adds busy high-traffic ATMs as false-positive cases,
     and widens amount/timing noise. Result: P@100 0.83, threshold precision
     0.62, false-alert rate 0.38 — strong-but-imperfect, decaying honestly
     across the band. Full write-up: "Why precision@K is not artificially
     perfect" in MODEL_CARD.md.
   - **Ensemble disclosed**: rank-average XGB+Hawkes scores *worse*
     (Precision@100 0.41) than pure XGBoost (0.83); active model = xgboost.
     The Hawkes feature (single-feature AUC 0.5082, leak-free) remains in the
     feature set.
3. **Transfer-readiness** — schema, repository layer, ingestion adapters, and
   feature definitions are shaped for real NCRP/CFCFRMS + bank feeds.
4. **Not field-validated accuracy.** A real pilot would replace synthetic
   labels with investigation-confirmed withdrawals, re-evaluate precision@K and
   lead-time, and re-tune thresholds per city/bank via an ops review.

## 2. Data-access & jurisdiction limitations

- **Synthetic data only** — no real NCRP/CFCFRMS or bank data is accessed.
- The schema is jurisdiction-aware (`state`, `district`, `police_station_area`,
  `bank_name` on every ATM/alert/report) and RBAC row-scoping is enforced in
  the repository layer. **Full inter-agency routing/handoff and cross-state
  coordination are future work** — they depend on non-public MHA/I4C operational
  protocols. Alerts show *recommended recipients* only.
- **Live-stream ingestion** is a simulator (`StreamSimulatorAdapter` drips
  synthetic records); a KafkaAdapter for true scale (~8,000 complaints/day) is
  a Tier 2 stub.

## 3. Privacy (DPDP-Act posture) & anti-profiling

- **PII pseudonymization (Tier 1, live)**: accounts and phone numbers are
  stored as salted-hash tokens (`acct_…`, `tel_…`); raw values exist only in a
  mock re-identification vault with role-scoped access. Dashboards never show
  raw identifiers.
- **Anti-profiling (enforced in code)**: there are NO demographic, community,
  religion, caste, or similar features anywhere in the pipeline. Risk is driven
  by transaction behaviour + complaint linkage + transaction geography only.
- **Ethics guard**: "Advisory only — no automated enforcement; audited human
  decision required" is displayed in the UI and enforced by design (fund-block
  recommendations require an explicit bank-officer action). A geographic
  concentration monitor (`backend/eval/fairness_check.py`,
  `artifacts/fairness_report.json`) tracks alert concentration over time for
  ops review.
- Production notes: data minimization (only fields needed for forecasting),
  purpose limitation, access control + audit (ledger), and DPDP-Act
  assessments are documented here as the compliance posture the prototype
  scaffolds.

## 3b. Real-data validation status

- `backend/eval/real_data_harness.py` + `data/real/README.md` provide a
  concrete plug-in path for real/public aggregate complaint data (district,
  date, complaint_count). Current status: **PENDING_REAL_DATA** — no real file
  is supplied, so no correlation is claimed (see
  `artifacts/real_validation.json`; numbers are never invented).
- What is pilot-ready: the framework's transfer path (repository layer,
  schema, adapters, harness). What is NOT yet validated: any real-world
  precision claim — a pilot with NCRP/CFCFRMS data would replace synthetic
  labels with investigation-confirmed withdrawals and re-tune per city/bank.

## 4. Explainability method

- The evidence panel uses **global feature importance (XGBoost
  `feature_importances_`) + instance percentile** vs. the training set.
- It is **explicitly NOT SHAP** and does not imply per-instance causal
  attribution. True SHAP is future work (scaffolded, not built).

## 5. Ledger (Blockchain theme)

- The tamper-evident **SHA-256 hash chain** is live (alert lifecycle, evidence,
  reports, fund-block issuance, access events) with `/ledger/verify` integrity
  checking and a tamper-demo. Honest label: this is an **append-only hash chain
  providing tamper-evidence and chain-of-custody — not a cryptocurrency/public
  blockchain**. Tier 2 = anchor the chain root to a permissioned ledger
  (Hyperledger Fabric) for multi-organisation consensus.

## 6. Recovery funnel

- Fund-block recommendations and the flagged → held → recovered funnel use
  **synthetic/illustrative outcomes**. Real CFCFRMS / NCRP / core-banking APIs
  are the Tier 2 integration point (marked in code).

## 7. Operational caveats

- Notifications: SMS/email are mock logs; the **API channel is a REAL outbound
  webhook** (httpx) to a local mock I4C inbox — the path is real, the receiver
  is mock. All labelled "Simulated — hackathon prototype".
- Authentication is prototype-grade: bcrypt + JWT (access/refresh) with
  role-scoped RBAC — production replaces it with OAuth2.0/OIDC + org SSO.
- `DEMO_MODE=true` serves a pre-computed golden-path cache (stage fallback
  only; never in production).
- Prediction granularity is per-ATM per-day (24h horizon); finer hourly
  forecasts are future work.

---

*This document is the single consolidated limitations reference for judges.*