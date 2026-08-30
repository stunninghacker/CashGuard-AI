# ONE_SLIDE_EXECUTIVE_SUMMARY.md — 20 seconds

**CashGuard AI — SIH26184 · MHA · I4C**
> **Source of truth for current metrics:** `CURRENT_METRICS.md`. Honest leak-free ROC-AUC **0.6273**.

**The gap:** ~8,000 cybercrime complaints/day; by the time police act, the
cash is already out of the ATM. Recovery ≈ 0.

**The idea:** forecast *where* fraudsters will cash out tomorrow — so police
and banks intervene *before* the money moves.

**The system:** complaints + ATM/withdrawal data → calibrated ML → live GIS
map of risk (2/6/12/24/48h horizons, honest confidence) → per-ATM evidence
(why, what-if, how confident) → human-reviewed action → recovery funnel →
tamper-evident audit trail.

**Measured (synthetic labels, artifact-backed):** a same-day label-leakage bug was
found and fixed (see `MODEL_CARD.md`); the honest forecast-safe **ROC-AUC is 0.6273**
(P@20/50/100/200/500/1000 = 0.65/0.64/0.61/0.57/0.372/0.261 · prf@0.7 = 32 alerts / P 0.75 /
FAR 0.25). On calm demo days the live model reports low risk and **no alerts**; the populated
alert workflow is shown only via the opt-in, clearly-labelled **"Load Simulated Scenario"**
button (SCRIPTED, not live output). Any earlier "0.927" figure is superseded.

**Honesty:** no real data claimed, no real savings claimed — a 14-step
real-data validation protocol and 30-day shadow-mode pilot are the
authorized path to production. Everything is reproducible with one command.