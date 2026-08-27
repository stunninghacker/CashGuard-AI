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
13. Live WebSocket toast on new alerts.
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