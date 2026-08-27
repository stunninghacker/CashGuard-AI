# LABEL_VALIDITY.md — What is the label, and can it leak?

## The label contract (synthetic world)

| Question | Answer |
|---|---|
| **WHAT is the label?** | `is_fraud_withdrawal` on the `withdrawals` table — the generator marks each withdrawal it created as a fraud cash-out (mule chunk) or not. Aggregated to the ATM-day target: "any fraud withdrawal at this ATM in the next 24h". |
| **WHO created it?** | The data generator (`backend/data/synthetic_data.py`), at transaction creation time — it is the *ground truth of the simulation*, not a report or a model output. |
| **WHEN?** | At generation; immutable. |
| **COULD IT LEAK INTO FEATURES?** | No — verified three ways: (1) the feature builder reads only windows strictly *before* the forecast point; (2) `is_fraud_withdrawal` appears in the feature module only as the label `y` (grep-verified); (3) the old `fraud_withdrawals_24h` leak feature was removed and its 1.0-style signature is the exact pattern the per-feature-AUC audit now treats as a red flag. |

## Could the model learn *reporting behaviour* instead of fraud?
This is the sharpest attack: if fraud labels were merely complaint-driven, the
model would be learning "where complaints are filed", not "where cash-outs
happen". Evidence against it:
- Ablation: complaints-only features give AUC **0.50** (random) — complaint
  features alone cannot separate.
- Permutation: re-tagging city complaint features changes AUC by <0.001 —
  the model does not lean on reporting geography.
- The decisive features are withdrawal-side behavioural signals
  (counterparty/mule concentration), which the generator creates
  independently of complaint volumes.
- Counterfactual: a +50% complaint surge moves mean risk by only +0.0013.

## Label taxonomy for the real pilot (REAL_DATA_VALIDATION_PROTOCOL.md §6)
Real data must separate the outcome ladder explicitly:
- **reported** (complaint filed) → not a fraud outcome
- **suspected** (bank flag) → candidate
- **confirmed** (investigation-confirmed fraud withdrawal) → the label
- **recovered** (funds recovered) → outcome, not label
- **unknown** (no confirmation within the window) → excluded from training,
  tracked in the outcome store (AlertOutcome.UNKNOWN)
The pilot pre-registers which ladder rung defines the label *before* looking
at the data, and the leakage checks (§7 of the protocol) re-run the
per-feature-AUC audit on the confirmed subset.

## Honest limits
- In the synthetic world, "confirmed fraud" is the generator's ground truth —
  the reporting-vs-fraud distinction is *simulated*, and the pilot is where
  it becomes real.
- If real reporting behaviour lags cash-outs differently than the generator's
  18h mean latency, the model must be recalibrated on real outcomes (protocol
  §10).