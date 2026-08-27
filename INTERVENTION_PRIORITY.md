# INTERVENTION_PRIORITY.md — "Where should an investigator act first?"

Raw risk ranking answers "which ATM is most likely to see fraud". It does NOT
answer "where should a scarce patrol-hour go first". This document defines the
Intervention Priority Score, its justification, normalization, assumptions,
and limitations.

## Formulation

For each ATM with calibrated risk `p`:

```
P = (0.40·p + 0.25·E + 0.15·U + 0.20·S) · Q
```

| Term | Definition | Range | Justification |
|---|---|---|---|
| `p` | calibrated probability of fraud withdrawal in next 24h | 0–1 | The core forecast; largest weight because it is the best-validated signal. |
| `E` (exposure) | min(amount_sum_24h / ₹1M, 1) — recent cash flowing through the ATM | 0–1 | The recovery story: all else equal, the ATM moving the most money is where a blocked cash-out saves the most. The ₹1M cap is a documented tunable assumption (no public per-ATM exposure data). |
| `U` (urgency) | emerging-risk score (rate-of-change of complaints, mule concentration, velocity) | 0–1 | Breaks ties between "usually risky" and "risk rising fast now" — a fast-rising ATM is the proactive win. |
| `S` (evidence) | 0.25 + 0.25·min(counterparty/8,1) + 0.25·linked_share + 0.25·min(city24h/40,1) | 0–1 | Actionability guard: only act where the evidence chain is strong. Thresholds are documented assumptions. |
| `Q` (confidence weight) | 1.0 if p≥0.80 · 0.7 if p≥0.70 · 0.4 otherwise | 0.4–1.0 | Uncertainty guard: a low-probability flag can never outrank a confident one. |

## Why it is preferable to raw risk ranking
1. **Exposure-aware**: two ATMs at p=0.85 — one moved ₹50k, one ₹2M — raw ranking
   treats them equally; priority does not (the ₹2M ATM prevents more loss).
2. **Proactive**: emerging-risk weighting surfaces *rising* hotspots before they
   become historical ones.
3. **Evidence-gated**: weak-evidence alerts are pushed down even if p is modest
   (and the HOLD ACTION band already flags p ∈ [0.70, 0.78)).
4. **Uncertainty-bounded**: no auto-escalation of low-confidence scores.

## Normalization & calibration
- All terms are already 0–1; the weighted sum is 0–1 before `Q`.
- The formulation is deterministic (same inputs → same priority), so it is
  auditable and reproducible.
- Weights were chosen by expert judgement, not fitted — stated openly; a pilot
  would tune them via an ops review (documented limitation).

## Assumptions (explicit)
- Exposure cap ₹1M/24h, counterparty cap 8, complaint cap 40/24h — tunable
  assumptions; no public per-ATM statistics.
- Weight vector (0.40/0.25/0.15/0.20) is a judgement call.
- Everything is CONTROLLED SYNTHETIC EVALUATION — priority ranking has NOT been
  validated against real outcomes.

## Limitations
- Does not model officer travel time, branch availability, or cash-cassette
  limits (future work).
- Exposure is derived from observed withdrawals, which may be incomplete at
  inference time (data freshness shown separately).
- The confidence weight uses probability bands, not the full uncertainty block;
  the evidence panel still shows the complete uncertainty metadata.