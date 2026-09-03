# DEMO_VIDEO.md — 3–5 Minute Demo Video (Submission Field)

**Status: PENDING UPLOAD** — the shot list and word-for-word narrated script
below are ready; the recording must be made on the demo machine and uploaded to
YouTube, then the link inserted in the SIH submission fields. This file keeps
the links in one place and the narration honest.

## Links (fill at submission)
- **Demo video (YouTube):** `[PENDING — insert URL]`
- **Sample dataset (placeholder):** `data/sample_dataset/` — exported by
  `python scripts/export_sample_dataset.py` (small, downloadable CSV package:
  complaints, withdrawals, ATMs; synthetic, ~1 MB). Upload the zip alongside
  the submission and put its link here: `[PENDING — insert URL]`

---

## Recording script — full narration (4:30 target)

> **Opening line (say this first — 20–30s, per DEMO_SCRIPT §0):**
> "Before we start, one honest caveat. Every metric you'll see is measured on
> synthetic labels generated from *published* fraud patterns — I4C Suspect
> Registry clustering, IBA mule-account behaviour, and RBI's direction toward
> transfer time-delays. That proves our methodology — time-based splits,
> precision-at-K with baseline lift, calibration, robustness to perturbation —
> but it is not real-world precision yet. The model is deliberately detuned so
> the numbers are strong but imperfect: our honest AUC is 0.68, not a fabricated
> 0.82. A real pilot with NCRP/CFCFRMS data would re-validate everything against
> investigation-confirmed withdrawals."

### Shot table (timing + what's on screen + narration)

| Time | Shot | What happens / what you say |
|---|---|---|
| 0:00–0:30 | **Value first** | "A cybercrime complaint arrives…" — ingest stream drip → engine re-scores → a hotspot appears. Keep the audio mnemonic to the 30s honesty line above. |
| 0:30–1:15 | **Map + risk + confidence** | Hotspot row: location, risk %, 24h horizon, confidence; the horizon strip (2/6/12h HOLD, 24/48h MEDIUM). *"Each row answers where, how high, how soon, and how confident."* |
| 1:15–2:00 | **Evidence** | Details panel: TreeSHAP contributions, counterfactual, evidence graph, per-feature source tags (verified vs assumed). |
| 2:00–2:30 | **Human review** | Officer decision — dismiss and escalate **require a reason**; HOLD/REVIEW/ACT policy visible; every action lands on the ledger. |
| 2:30–3:15 | **Bank + recovery** | Bank view, fund-block queue, hold → recovered; recovery funnel moves. |
| 3:15–4:00 | **Audit — tamper + on-chain** | Two-part ledger close (see below): (1) live tamper-evidence via `/ledger/verify`, then (2) **on-chain anchoring** via `/ledger/verify-onchain` — honestly shown in its not-yet-configured state. |
| 4:00–4:30 | **Evidence close** | Baseline war (beats volume/historical), fairness chart, real-data readiness + the honesty close. |

### Audit segment narration (3:15–4:00) — reflects the NEW on-chain anchoring (Issue 2)

> "Every action here is written to a tamper-evident chain. Watch — I'll flip one
> block and verify: the chain detects it immediately and we restore it. That's
> the court-facing property of a police system: immutability and chain-of-custody.
>
> Beyond that, our **Tier-2** is real on-chain anchoring. The endpoint
> `/ledger/verify-onchain` proves whether today's chain root is committed on a
> public ledger. Right now it honestly reports `configured: false` — because we
> have not been given a funded testnet wallet. The moment we wire a Polygon Amoy
> RPC, an owner key, and the deployed AuditLog contract (which comes with this
> repo), this endpoint compares the live chain root against the on-chain record
> and reports `root_matches_onchain: true`, with a public timestamped
> proof-of-existence. We don't fake that step — it's genuinely pending real
> infrastructure."

> **Note for the recorder:** do NOT claim the chain is already on Polygon. Show
> the endpoint returning the honest `configured:false` reason on screen — that is
> the credibility point.

---

## Recording checklist
- [ ] Fresh machine: `python run.py` → server up (or `DEMO_MODE=true` fallback)
- [ ] 1080p screen capture, local audio on
- [ ] No real PII on screen (synthetic only); no credentials shown beyond the
      demo login screen
- [ ] If anything breaks: narrate the dedup/fallback honestly (DEMO_SCRIPT §4)
- [ ] Verify the on-chain segment matches `GET /ledger/verify-onchain` *live*
      (it must say `configured:false` and the honest reason)
- [ ] Upload unlisted → insert link above → add to SIH submission fields

## References (keep in the 4:30 budget)
- DEMO_SCRIPT.md §0 (honesty opening), §2 (16-step walkthrough), §4 (breakage),
  §5 (URLs for judges)
- REAL_DATA_GAP.md + REAL_DATA_READINESS.md + REAL_DATA_VALIDATION_PROTOCOL.md
  (do not over-claim real-world readiness)
- contracts/AuditLog.sol + backend/blockchain/onchain.py (Tier-2 anchoring)
