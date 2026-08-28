# JURISDICTION_ROUTING.md — Inter-Agency Jurisdiction Routing (Item 4)

## Purpose

Cybercrime is cross-jurisdictional by design: a person in **state X** falls for
a scam, the money moves through mule accounts, and the **cash gets withdrawn at
an ATM in state Y**. The police in the state where the victim filed the
complaint have jurisdiction over the fraud *report*, but the actionable lead
(the compromised ATM) sits in another state's territory. This module routes
that intelligence between state/LEA jurisdictions through an I4C-style
coordination queue.

## What was built

- **`backend/routing.py`** — the routing engine:
  - `origin_state_for_atm(db, atm)` — determines the *complaint-origin*
    jurisdiction that seeded an ATM's risk. Two independent signals:
    1. **Local seed**: modal `victim_state` of complaints whose
       `victim_district` / `victim_city` / `police_station_area` matches the
       ATM's own location (district → state → city → station precedence).
    2. **Account-linked (cross-state mule)**: modal `victim_state` of
       complaints whose `linked_account_token` has a withdrawal at this ATM in
       the window, **whose `victim_state` differs from the ATM's state**. This
       is the genuine layering/cross-state cash-out pattern.
  - `route_alert(...)` — creates an `AlertHandoff` when `origin_state !=
    alert.state`; idempotent (no duplicate handoffs).
  - `ack_handoff(...)` / `list_handoffs(...)` — queue lifecycle + provenance.
- **`AlertHandoff` model** — `origin_state` (complainant jurisdiction),
  `receiving_state` (predicted withdrawal state), status (`queued` / `ack` /
  `complete` / `rejected`), ack provenance.
- **`Alert.origin_state` / `Alert.routing_status`** — each alert records
  whether it is a cross-state case and its routing state (`none` / `handoff` /
  `handoff_ack` / `handoff_complete`).
- **Wired into the alert cycle** (`run_alert_cycle`): on alert creation the
  engine computes `origin_state`; if cross-state, the case is flagged and a
  handoff is created. Ledger-logged (`alert_handoff_created` / `alert_handoff_ack` /
  `alert_handoff_complete`).
- **API**:
  - `GET  /alerts/handoffs/list` — cross-state handoff queue (role/Jurisdiction
    scoped: police see handoffs touching their state; I4C sees all).
  - `POST /alerts/handoffs/{id}/ack` — receiving state-LEA acknowledges or
    completes the handoff (ledger-logged).
- **Frontend (I4C dashboard)** — "Inter-Agency Jurisdiction Handoffs" panel with
  queued/acked/completed state and Ack/Complete actions; alerts show a routing
  badge (`origin → state`) when cross-state.

## Honest verification (controlled, reproducible)

The **mechanism is unit-tested** (`scripts/test_jurisdiction_routing.py` style
fixture, reproduced in VERIFICATION_LOG):

| Case | Input | Expected | Actual |
|------|-------|----------|--------|
| Intra-state | `origin_state == state` | no handoff | `None` ✓ |
| Cross-state | `origin_state != state` | handoff created, `queued` | `HO-...`, `State-C → State-B`, queued ✓ |
| Ack/complete | receiving LEA acks | handoff `complete`, alert `handoff_complete` | ✓ |
| Idempotency | re-route same alert | single handoff, no duplicate | `1 == 1` ✓ |
| API list | cross-state present | 200, listed | ✓ |
| API ack | complete via HTTP | 200, status complete | ✓ |
| API error | unknown handoff | 404 | ✓ |

## IMPORTANT — honest scope (read carefully)

**The current synthetic generator produces intra-state data**: predicted
withdrawals cluster near complaint origin (the generated mule cash-outs stay in
the same state as the complaint). As a result, `route_alert` does **not
currently fire in production runs** — the handoff queue stays empty for real
synthetic alerts.

This is the *correct, honest* behavior, not a bug. It means:

- The **routing mechanism is implemented, correct, and verified** on controlled
  cross-state fixtures.
- The **signal (cross-state mule movement) is not present in the current
  synthetic data**, so there is nothing to route in production yet.
- **When** the data-generator is extended to model cross-state layering (or real
  inter-state complaints/withdrawal data arrives via REAL_DATA_GAP/onboarding),
  this module activates with **zero code changes** — it will detect the
  cross-state origin and create handoffs automatically.

We deliberately do **not** fabricate cross-state cases to make the queue look
busy. That would be dishonest and would misrepresent the current data.

This module models the **I4C coordination node** pattern. It performs in-app
routing/handoff with mock state-LEA forwarding — it does **not** call any real
inter-agency gateway (documented Tier 2 / production integration).

## Configuration

- `SEED_COMPLAINT_LOOKBACK_DAYS` (default 45) — complaint window used to seed an
  ATM's origin jurisdiction.

## Next step (when data supports it)

- Extend the generator / onboarding to model cross-state mule layering, then the
  handoff queue activates organically. Verify against `limitations`: this is
  synthetic evidence until REAL_DATA_GAP is closed.
