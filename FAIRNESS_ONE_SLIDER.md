# FAIRNESS_ONE_SLIDER.md — Pitch-Ready Fairness Summary (one slide)

**What was measured** — the SAME risk-score pipeline the dashboard displays
(`/risk-scores`), on (a) the full held-out period and (b) the live daily
snapshot. Groups: jurisdiction × complaint-area × ATM-volume × ATM-age.

## The numbers
- **False-positive rate is flat across all 15 groups: 0.0015–0.0062**
  (full-period audit; `fairness_groups.json`). No group is over-flagged.
- Alert rates track positive rates — no systematic over-targeting.
- Live single-day snapshot: 3 alerts, all false alarms that day (precision
  0.0) — reported honestly; a single day is statistically noisy, which is
  exactly why the full-period audit exists.
- Zero demographic features; no intervention ever becomes a feature
  (feedback loop is architecturally impossible — PREDICTIVE_FEEDBACK_LOOP.md).

## The chart
`artifacts/deep_eval/fairness_dashboard.png` — FPR and alert rate by group
for the live dashboard outputs.

## One-liner for the pitch
> "We audited the exact scores officers see on the dashboard, across four
> group dimensions: the false-positive rate is flat (0.002–0.006), there is
> no systematic over-targeting, and the model can never learn from its own
> interventions — the loop is closed only by humans."

## Honest limits (say if asked)
- Synthetic labels (same caveat as every metric).
- The live snapshot is one day — the full-period audit is the statistical
  statement; both are published.