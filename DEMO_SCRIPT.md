# DEMO_SCRIPT.md — Live Walkthrough for Judges + Failure Contingency

## 0. Evaluation-Honesty Opening Line (say this FIRST, 20–30 seconds)

> "Before the demo, one honest caveat. Every metric you'll see is measured on
> synthetic labels generated from *published* fraud patterns — I4C Suspect
> Registry clustering, IBA mule-account behaviour, and RBI's direction toward
> transfer time-delays. That proves our methodology — time-based splits,
> precision-at-K with baseline lift, lead-time, calibration, robustness to
> perturbation — but it is not real-world precision yet. The model is
> deliberately detuned so the numbers are strong but imperfect, and a real
> pilot with NCRP/CFCFRMS data would re-validate everything against
> investigation-confirmed withdrawals. Every parameter is source-tagged
> verified-vs-assumed and disclosed in the UI."

## 1. Pre-flight (on the demo machine)

```bash
cd "CashGuard AI"
.venv\Scripts\activate
python scripts/generate_data.py     # prints CALIBRATION SUMMARY (source-tagged + cited)
python scripts/train_model.py       # metrics incl. baseline lift + lead-time
python scripts/cache_demo_mode.py   # golden-path fallback cache
python -m uvicorn backend.api.main:app --port 8000
```
Open **http://localhost:8000**. (Also run `scripts/robustness_check.py` once
beforehand — static PNG for the deck.)

## 2. Live Walkthrough — the 16-step evidence-first scenario

1. **Login** as `officer.district1 / District1!1`.
2. (Simulated) batch of complaints arrives — the engine is re-scored.
3. New signals arrive → **emerging-risk badges** on hotspots ("▲ Emerging 62%" vs "● historical").
4. Top hotspots update — click #1. The row answers: where (ATM/city) · how high (risk %) ·
   how soon (24h horizon) · why (Details) · how confident (uncertainty block).
5. **Details** → 3-field evidence + **evidence graph** (complaint surge → velocity → mule
   concentration → proximity → temporal → forecast risk; each node: value, direction, source,
   observed/synthetic).
6. Uncertainty block: confidence · evidence strength n/5 · data freshness · model version ·
   horizon — and **INSUFFICIENT EVIDENCE — HOLD ACTION** on the weak band.
7. **Recommended actions** (graded, review-oriented).
8. Officer decides: **Acknowledge / Monitor / Dismiss / Escalate / More data** — dismiss and
   escalate **require a reason** (ledger-recorded).
9. **Bank login** → scoped alert + **fund-block queue** + recovery funnel; Hold/Recovered updates it.
10. After the 24h horizon: **Evaluate pending** → **Closed-Loop Outcomes** (predicted vs actual,
    FP/FN, drift).
11. **I4C**: national stats + model monitoring + **Verify Ledger ✓** → **Tamper-demo** → **Verify ✗**.
12. **PDF Intelligence Report** (ledger-fingerprinted) + **Situational Report**.
13. Live WebSocket toast on new alerts. **Sequencing note — important**: the
    alert engine deduplicates repeat alerts for the same ATM within 6h
    (`ALERT_COOLDOWN_HOURS`) unless risk rises by >0.1. If you click
    **⚡ Run Alert Cycle** twice in quick succession, the second run may fire
    no new alerts and push no WS event — that is the dedup working, not a
    broken live push. Either trigger the cycle **once** during the walkthrough
    (recommended), or narrate it if you trigger it twice: *"notice this second
    alert didn't fire — that's the dedup logic working, not a bug."*
14. Drill-downs: category chips, date replay, state→city→bank cascade, heat-vs-forecast toggle.
15. Deep-eval artifacts shown: ablation, adversarial worlds, horizons, calibration (ECE/Brier).
16. Close on the honesty opening (§0).

## 3. Fallback Plan — DEMO_MODE (if live inference breaks on stage)

```bash
set DEMO_MODE=true
python -m uvicorn backend.api.main:app --port 8000
```
The API serves the pre-computed golden path (`data/demo_cache/`: risk-scores,
alerts, evidence) with **zero live inference**. Same UI, pre-computed data —
the walkthrough continues seamlessly. Never set `DEMO_MODE=true` in production.

## 4. What to tell judges if something breaks

- Map tiles fail (no internet) → "Tiles need internet; data + API are local —
  here are the hotspots table and evidence panel."
- Scheduler hasn't fired → use **⚡ Run Alert Cycle** (same code path).
- Live inference hangs → switch to `DEMO_MODE=true` per the fallback plan.
- Ledger tamper-demo disabled → it's gated by `ALLOW_TAMPER_DEMO=true` for
  safety; the verify path is live.

## 5. Key URLs for judges

| URL | What |
|---|---|
| `http://localhost:8000` | Dashboard (role-based login) |
| `http://localhost:8000/docs` | Full REST API (Swagger) |
| `http://localhost:8000/ledger/verify` | Ledger integrity (JSON) |
| `http://localhost:8000/recovery/funnel` | Recovery funnel (JSON) |
| `http://localhost:8000/mock-i4c-inbox` | I4C inbox (webhook receiver) |
| `ws://localhost:8000/ws/alerts` | Live alert push (WebSocket) |

## 6. Rehearsed audience Q&A (preparation — internal)

**Q1 — "How do we know this isn't circular — synthetic labels proving your own patterns?"**
Every generator parameter is source-tagged verified-vs-assumed and cited (I4C Suspect
Registry, IBA mule characteristics, RBI time-delay direction). The model must beat TWO
naive baselines — recent-volume ranking (lift 14–18×) and complaint-proximity ranking
(17× at P@100) — on a time-based split with a validation slice that early stopping never
touches. The `real_data_harness` is runnable today: drop a district-level complaint CSV
in `data/real/` and it validates the predicted hotspot density against real complaint
density. Status is honestly PENDING_REAL_DATA until then.

**Q2 — "What's genuinely novel here?"**
A self-exciting (Hawkes) temporal intensity over complaint timestamps — λ(t) = μ +
Σα·exp(−β(t−tᵢ)) over PAST complaints only, fitted per location, future-free by
construction (asserted by a unit test). We disclose honestly that the XGB+Hawkes
ensemble does NOT beat pure XGBoost (Precision@100 0.41 vs 0.83) and that the feature
alone has 0.51 AUC — it earns its place inside the model, not as a headline. The
headline is the loop: prediction → evidence → graded response playbook → recovery
funnel → tamper-evident ledger.

**Q3 — "Isn't counterparty_count_24h the fraud label in disguise?"**
It counts complaint-linked accounts at the ATM in the trailing 24h — complaints are
filed before cash-out, so it's available at prediction time; its window ends before the
forecast point; its single-feature AUC is 0.8447, not 1.0; and the ranking decays to
0.52 at K=1000 — a real leak stays ≈1.0 throughout. (CALIBRATION_NOTES has the full
four-point rebuttal.)

**Q4 — "An officer gets an alert — then what?"**
The alert carries a graded response playbook (notify branch → heighten monitoring →
CCTV/pre-position → tighten withdrawal verification) with an evidence panel and feature
contributions (global importance + percentile, plus per-instance TreeSHAP); the Bank dashboard shows the
CFCFRMS fund-block queue and recovery funnel. Everything is advisory — a human action
is required and every action lands on the tamper-evident ledger.

**Q5 — "Why 'Blockchain & Cybersecurity' — is this a real blockchain?"**
Honest label: it's an append-only SHA-256 hash chain giving tamper-evidence and
chain-of-custody across agencies — the property a court-facing LEA system needs. We
demo it live: run alert cycle → verify chain ✓ → flip one block → verify fails ✗.
Anchoring to a permissioned ledger (Hyperledger Fabric) is the documented Tier-2 upgrade.

## 7. Team ownership (every member owns a slice)

| Member | Owns | Be ready for |
|--------|------|--------------|
| **A — ML** | features, Hawkes, ensemble, baselines, metrics, leakage rebuttal, de-separation story (MODEL_CARD "Why precision@K is not artificially perfect") | Q1, Q2, Q3 |
| **B — Security** | JWT/RBAC, ledger, tamper demo, evidence chain-of-custody | Q5, access-control questions |
| **C — Data & privacy** | synthetic generator, calibration notes, PII pseudonymization, real-data harness | Q1 follow-ups, DPDP/anti-profiling |
| **D — Product/demo lead** | dashboard flow, recovery funnel, response playbook, demo timekeeping | Q4, "what changed vs yesterday" |
