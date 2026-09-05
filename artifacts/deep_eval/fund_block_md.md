# Phase 6 — Fund-Block Recommendations & CFCFRMS Integration

**Phase 6** from the SIH specification — the recovery story. When an ATM is flagged as high-risk for
fraud withdrawals, linked mule accounts are identified and fund-block recommendations are issued
through the Bank dashboard and a CFCFRMS-style webhook stub.

## 1. Fund-Block Recommendation Process

### 1.1 Trigger
Fund-block recommendations are issued when an alert is created with `risk_score >= RISK_THRESHOLD`
(default 0.70). The recommendation scope is the flagged ATM and accounts linked to complaints that
seeded the ATM's risk profile.

### 1.2 Data Sources
The following repository queries are used to build the recommendation:

| Query | Purpose |
|---|---|
| `recent_withdrawals(db, atm_id=alert.atm_id, since=ref - timedelta(hours=24))` | All withdrawals at the flagged ATM in the last 24h |
| `repo.complaint_mule_account_tokens(db)` | Set of account tokens identified as mule accounts across all complaints |
| `repo.complaint_ids_for_account(db, token)[:5]` | Up to 5 complaint IDs linked to each mule account (for evidentiary trail) |
| `repo.bank_for_account(db, token)` | Home bank of each mule account |
| `repo.bank_for_account(db, token) or alert.bank_name` | Preferred bank, falls back to alert's bank |

### 1.3 Recommendation Logic
```python
linked = [
    w for w in wd_24h if w.account_token in mule_tokens
]

if not linked:
    return 0  # no mule accounts found at this ATM

counts = Counter(w.account_token for w in linked)
amounts = {}
for w in linked:
    amounts[w.account_token] = amounts.get(w.account_token, 0.0) + w.amount

created = 0
for token, n in counts.most_common(3):  # top-3 mule tokens by frequency
    complaint_ids = repo.complaint_ids_for_account(db, token)[:5]
    rec = repo.create_recovery_recommendation(
        db,
        rec_id=f"REC-{alert.atm_id}-{token[-6:]}-{datetime.utcnow().strftime('%H%M%S')}",
        alert_id=alert.alert_id,
        account_token=token,
        home_bank=repo.bank_for_account(db, token) or alert.bank_name,
        linked_complaint_ids=json.dumps(complaint_ids),
        amount_at_risk=round(amounts.get(token, 0.0), 2),
        suspected_atm=alert.atm_id,
        predicted_window="next 24h",
        recommended_action="freeze" if alert.risk_score >= 0.85 else "hold",
        status="freeze_requested",
    )
    # ... ledger log, webhook, WS broadcast
    created += 1
```

### 1.4 Top-3 Mule Account Selection
- Sorted by `counts.most_common(3)` — most frequently seen mule accounts at the flagged ATM first
- For each token, `amount_at_risk` = total withdrawal amount across all linked withdrawals in the last 24h
- `recommended_action` = `freeze` if `risk_score >= 0.85`, otherwise `hold`
- Status = `freeze_requested` — indicates the recommendation has been issued but not yet acted upon

## 2. CFCFRMS-Style Webhook Stub

Every fund-block recommendation triggers a webhook to a mock CFCFRMS inbox. The webhook payload includes:

| Field | Value |
|---|---|
| `action` | `"fund_block_recommendation"` |
| `account_token` | The mule account token |
| `amount_at_risk` | Total INR amount at risk (normalized) |
| `suspected_atm` | The flagged ATM ID |
| `recommended_action` | `"freeze"` or `"hold"` |

The webhook path is:
```
_hypothesize_({"channel": "cfcfrms", "payload": {...}}) 
→ httpx.post(CFCFRMS_WEBHOOK_URL, json payload, timeout=5)
→ stores + displays in local POST /api/mock-i4c-inbox
```

**Production**: Point `CFCFRMS_WEBHOOK_URL` at actual I4C/state-LEA/CFCFRMS gateways.

## 3. Live Push to Dashboards

After webhook dispatch, the recommendation is broadcast via WebSocket to connected dashboards:

```python
enqueue_broadcast("recovery", {
    "rec_id": rec.rec_id,
    "account_token": token,
    "amount_at_risk": rec.amount_at_risk,
    "suspected_atm": alert.atm_id,
    "recommended_action": rec.recommended_action,
    "status": rec.status,
})
```

The dashboard recovery panel shows:
- Suspected mule account tokens
- Amount at risk per token
- Recommended action (freeze/hold)
- Status (freeze_requested / hold_pending / etc.)
- Linked complaint IDs (evidentiary trail)

## 4. Recovery Funnel Tracking

The system monitors outcomes through a **recovery funnel** — from flagged → held → recovered:

| Stage | Metric | Description |
|---|---|---|
| Flagged | `amount_flagged` | Total amount at risk from all active recommendations |
| Held | `amount_held` | Amount where the fund-block recommendation was acted upon (frozen/held) |
| Recovered | `amount_recovered` | Amount where the frozen mule account resulted in actual recovery |
| `recovery_rate_pct` | `100 * recovered / flagged` | Illustrative ratio — clearly labelled as synthetic |

### 4.1 Recovery Funnel Report
```python
def recovery_funnel(db: Session, days: int = 7) -> dict:
    since = datetime.utcnow() - timedelta(days=7)
    recs = repo.list_recovery_recommendations(db, since=since)
    flagged = sum(r.amount_at_risk for r in recs)
    held = sum(r.amount_held for r in recs)
    recovered = sum(r.amount_recovered for r in recs)
    return {
        "window_days": 7,
        "amount_flagged": round(flagged, 2),
        "amount_held": round(held, 2),
        "amount_recovered": round(recovered, 2),
        "recovery_rate_pct": round(100 * recovered / flagged, 1) if flagged else 0.0,
        "note": "Synthetic/illustrative outcomes — real CFCFRMS/core-banking APIs are the Tier 2 integration point.",
    }
```

## 5. Honest Limits

- All outcomes are **synthetic/illustrative** — clearly labelled as such; real CFCFRMS/core-banking APIs are the Tier 2 integration point
- `amount_held` and `amount_recovered` fields are populated by the demo's mock flow, not real banking actions
- Recovery rate percentages should **not** be cited as operational performance — they are illustration-only
- The fund-block path requires real integration with core banking / CFCFRMS systems for production deployment
- Mule account identification depends on the `linked_account_token` trail from complaints; if this trail is broken
  in real data, the fund-block coverage will be lower than synthetic estimates

## 6. Artifacts Generated

| File | Description |
|---|---|
| `artifacts/deep_eval/fund_block_md.md` | This document — full fund-block process description |
| `artifacts/deep_eval/recovery_funnel.json` (sample) | Recovery funnel statistics from the 7-day evaluation window |
| `backend/services.py` | `create_fund_block_recommendations()` implementation (lines 400-457) |
| `backend/services.py` | `recovery_funnel()` implementation (lines 460-474) |
| `backend/services.py` | `run_alert_cycle()` fund-block loop (lines 319-320) |

**Phase 6 complete: fund-block recommendations and CFCFRMS integration documented.**