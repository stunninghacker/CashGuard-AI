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

## 2. Live Walkthrough (click-by-click, ~5 minutes)

1. **Login** as `officer.district1 / District1!1` (Northsagar police).
2. **Map** — ATMs colored by risk. Click a red ATM → popup with jurisdiction
   (fictional state/district/PS area) + risk %.
3. **Drill-down panel (deliverable b)**:
   - Toggle **crime category** chips (e.g., phishing) → complaint heat changes.
   - **Date + ⟲ Replay** → forecast map recomputed for a past date
     (temporal drill-down).
   - **State / City / Bank** cascade filters.
   - Toggle **Complaint heat** (observed) vs **Forecast risk** (predicted).
4. **Top High-Risk ATMs (next 24h)** — top-20 table.
5. **⚡ Run Alert Cycle** — watch the **live WebSocket toast** arrive, then the
   alert feed fill with SMS/email/dispatch logs.
6. **Click Details** on an alert → **3-field evidence panel**: complaint
   activity · withdrawal activity · context signal with **VERIFIED/ASSUMED
   disclosure**; CFCFRMS freeze intel (masked account tokens); feature
   contributions (**NOT SHAP**); jurisdiction + recipients.
7. **Acknowledge / Actioned** — status changes, appended to the ledger.
8. **📄 Generate Intelligence Report (PDF)** — downloads via the chain-of-custody
   path.
9. **Log out → Login as `bank.hdfc / HdfcBank!1`** — only HDFC ATMs visible
   (server-side RBAC). Show the **Fund-Block Recommendations queue**; click
   **Hold / Recovered** and watch the **Recovery Funnel** move.
10. **Log out → Login as `i4c.admin / I4cAdmin!1`**:
    - National stats + recovery funnel headline (₹ flagged / held / recovered).
    - **I4C Inbox** panel — intel received via the REAL webhook path
      (dispatch + cfcfrms channels).
    - **Verify Ledger** → "Ledger verified ✓ · N blocks". Click
      **Tamper-demo** → Verify again → "LEDGER TAMPERED ✗" (the chain caught it).
    - **Generate Situational Report (PDF)**.
11. (Time permitting) `http://localhost:8000/docs` — full API surface;
    `POST /ingest/stream/start` shows live ingestion dripping.

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