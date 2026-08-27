# DEMO_VIDEO.md — 3–5 Minute Demo Video (Submission Field)

**Status: PENDING UPLOAD** — the shot list and script below are ready; the
recording must be made on the demo machine and uploaded to YouTube, then the
link inserted in the SIH submission fields. This file keeps the two links in
one place.

## Links (fill at submission)
- **Demo video (YouTube):** `[PENDING — insert URL]`
- **Sample dataset (placeholder):** `data/sample_dataset/` — exported by
  `python scripts/export_sample_dataset.py` (small, downloadable CSV package:
  complaints, withdrawals, ATMs; synthetic, ~1 MB). Upload the zip alongside
  the submission and put its link here: `[PENDING — insert URL]`

## Recording script (follows DEMO_SCRIPT.md exactly; 4:30 target)

| Time | Shot | What happens |
|---|---|---|
| 0:00–0:30 | Value first | "A cybercrime complaint arrives…" — ingest stream drip → engine re-scores → hotspot appears |
| 0:30–1:15 | Map + risk + confidence | Hotspot row: location, risk %, 24h horizon, confidence; horizon strip (2/6/12h HOLD, 24/48h MEDIUM) |
| 1:15–2:00 | Evidence | Details panel: TreeSHAP contributions, counterfactual, evidence graph, source tags |
| 2:00–2:30 | Human review | Officer decision (dismiss requires a reason) → HOLD/REVIEW/ACT policy visible |
| 2:30–3:15 | Bank + recovery | Bank view, fund-block queue, hold → recovered; funnel moves |
| 3:15–3:45 | Audit | Verify Ledger ✓ → Tamper → Verify ✗ → restore → replicated network (GET /ledger/network) |
| 3:45–4:30 | Evidence close | Baseline war (beats volume/historical), fairness chart, real-data readiness + honesty close |

## Recording checklist
- [ ] Fresh machine: `python run.py` → server up (or DEMO_MODE=true fallback)
- [ ] 1080p screen capture, local audio on
- [ ] No real PII on screen (synthetic only); no credentials shown beyond the
      demo login screen
- [ ] If anything breaks: narrate the dedup/fallback honestly (DEMO_SCRIPT §4)
- [ ] Upload unlisted → insert link above → add to SIH submission fields