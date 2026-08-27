# ONE_SLIDE_EXECUTIVE_SUMMARY.md — 20 seconds

**CashGuard AI — SIH26184 · MHA · I4C**

**The gap:** ~8,000 cybercrime complaints/day; by the time police act, the
cash is already out of the ATM. Recovery ≈ 0.

**The idea:** forecast *where* fraudsters will cash out tomorrow — so police
and banks intervene *before* the money moves.

**The system:** complaints + ATM/withdrawal data → calibrated ML → live GIS
map of risk (2/6/12/24/48h horizons, honest confidence) → per-ATM evidence
(why, what-if, how confident) → human-reviewed action → recovery funnel →
tamper-evident audit trail.

**Measured (synthetic labels, artifact-backed):** beats simple baselines
11–14× on intervention value; AUC 0.927; precision honest (P@100 0.86,
P@1000 0.53, 38% false-alert rate disclosed); drift-tested across 12
adversarial worlds; scales to 8,000 complaints/day.

**Honesty:** no real data claimed, no real savings claimed — a 14-step
real-data validation protocol and 30-day shadow-mode pilot are the
authorized path to production. Everything is reproducible with one command.