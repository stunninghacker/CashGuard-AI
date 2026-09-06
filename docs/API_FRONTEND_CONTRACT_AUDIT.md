# CashGuard AI — API-Frontend Contract Audit

**Date:** September 5, 2026  
**Auditor:** HexStrike AI  
**Backend:** FastAPI (backend/api/main.py)  
**Frontend:** app.js v17

---

## Endpoint Contract Table

All endpoints verified with HTTP status codes. Token obtained via POST /auth/login.

### Authentication
| Method | Endpoint | Auth Required | RBAC | Frontend Usage |
|--------|----------|--------------|------|----------------|
| POST | /auth/login | No | — | `doLogin()` → stores JWT |

### Core Data
| Method | Endpoint | Auth Required | RBAC | Frontend Usage |
|--------|----------|--------------|------|----------------|
| GET | /stats/summary | Yes | I4C, State, District | `renderOverviewStats()` |
| GET | /risk-scores | Yes | All | `loadAll()` → main data load |
| GET | /alerts?limit=N | Yes | All | `loadAll()`, `renderAlertsView()` |
| POST | /alerts/{id}/status | Yes | All | `setAlertStatus()` |
| POST | /alerts/run-now | Yes | I4C, State, District | `runAlertCycle()` |
| GET | /alerts/handoffs/list | Yes | All | `renderHandoffs()` |
| POST | /alerts/handoffs/{id}/ack | Yes | All | `handoffAck()` |
| GET | /alerts/outcomes/summary | Yes | All | `renderRecoveryView()` |
| POST | /alerts/outcomes/evaluate | Yes | All | Evaluate button handler |
| GET | /alerts/{id}/evidence | Yes | All | `loadDrawerEvidence()` |
| GET | /atms?limit=N | Yes | All | `loadCityCoords()` |

### ML & Analytics
| Method | Endpoint | Auth Required | RBAC | Frontend Usage |
|--------|----------|--------------|------|----------------|
| GET | /train/status | Yes | I4C, State | `renderModelView()` |
| GET | /drift/status | Yes | I4C, State | `renderModelView()` |
| GET | /threshold-explorer | Yes | All | `loadThresholdCurve()` |
| GET | /horizons | Yes | All | `renderHorizonConfidence()` |

### Mule Graph
| Method | Endpoint | Auth Required | RBAC | Frontend Usage |
|--------|----------|--------------|------|----------------|
| GET | /mule-graph/terminal-nodes?k=N | Yes | All | `renderMuleGraph()` |
| GET | /mule-graph/trail/{token} | Yes | All | `loadMuleTrail()` |
| GET | /graph/mule-network | Yes | All | `renderMuleView()` |

### Recovery
| Method | Endpoint | Auth Required | RBAC | Frontend Usage |
|--------|----------|--------------|------|----------------|
| GET | /recovery/funnel?days=N | Yes | All | `renderRecoveryView()` |
| GET | /recovery/recommendations | Yes | All | `renderRecoveryView()` |
| POST | /recovery/{id}/status | Yes | All | `updateRecovery()` |

### Ledger
| Method | Endpoint | Auth Required | RBAC | Frontend Usage |
|--------|----------|--------------|------|----------------|
| GET | /ledger?limit=N&offset=N | Yes | I4C, State | `renderLedgerView()` |
| GET | /ledger/verify | Yes | I4C, State | `ledgerVerify()`, `renderLedgerView()` |
| POST | /ledger/tamper-demo | Yes | I4C, State | `ledgerTamper()` |
| POST | /ledger/restore | Yes | I4C, State | `ledgerRestore()` |

### Reports
| Method | Endpoint | Auth Required | RBAC | Frontend Usage |
|--------|----------|--------------|------|----------------|
| POST | /reports/situational | Yes | All | `generateSituationalReport()` |
| POST | /reports/hotspot/{alert_id} | Yes | All | `drawerGenerateReport()` |
| GET | /reports/{id}/download | Yes | All | PDF download link |

### Complaints
| Method | Endpoint | Auth Required | RBAC | Frontend Usage |
|--------|----------|--------------|------|----------------|
| GET | /complaints?date_from=N&limit=N | Yes | All | `loadComplaints()` |

### I18n
| Method | Endpoint | Auth Required | RBAC | Frontend Usage |
|--------|----------|--------------|------|----------------|
| GET | /i18n/locales | Yes | All | `initI18n()` |
| GET | /i18n/strings?lang=N | Yes | All | `setI18nLang()` |

### Mobile
| Method | Endpoint | Auth Required | RBAC | Frontend Usage |
|--------|----------|--------------|------|----------------|
| GET | /mobile/nearby?lat=N&lon=N&max_km=N&limit=N | Yes | All | `renderMobile()` |

### Mock / Demo
| Method | Endpoint | Auth Required | RBAC | Frontend Usage |
|--------|----------|--------------|------|----------------|
| GET | /mock-i4c-inbox | Yes | All | `renderInbox()` |
| GET | /simulated/scenario | Yes | All | `loadSimulatedScenario()` |

### WebSocket
| Protocol | Endpoint | Auth Required | Frontend Usage |
|----------|----------|--------------|----------------|
| WS | /ws/alerts?token=N | JWT in query | `connectWS()` — live alert push |

---

## Response Schema Validation

### SummaryStatsOut (GET /stats/summary)
```json
{
  "total_atms": 900,
  "total_complaints": 12265,
  "complaints_24h": 180,
  "total_withdrawals": 200001,
  "fraud_withdrawals_7d": 10714,
  "high_risk_atms": 85,
  "alerts_total": 142,
  "alerts_new": 23,
  "alerts_actioned": 119
}
```
**Frontend uses:** `total_atms`, `high_risk_atms`, `alerts_new`, `alerts_total`, `alerts_actioned`, `complaints_24h`, `total_complaints`, `fraud_withdrawals_7d`, `total_withdrawals`

### Risk Score Object (GET /risk-scores)
```json
{
  "atm_id": "ATM-HDFC-001",
  "bank_name": "HDFC Bank",
  "branch_name": "North Branch",
  "city": "Mumbai",
  "district": "Mumbai",
  "state": "Maharashtra",
  "latitude": 19.0760,
  "longitude": 72.8777,
  "risk_score": 0.87,
  "recommended_action": "Enhanced monitoring",
  "as_of": "2026-09-05T12:00:00Z",
  "police_station_area": "Andheri"
}
```
**Frontend uses:** `atm_id`, `bank_name`, `branch_name`, `city`, `district`, `state`, `latitude`, `longitude`, `risk_score`, `recommended_action`, `as_of`, `police_station_area`

### Alert Object (GET /alerts)
```json
{
  "alert_id": "ALT-...",
  "atm_id": "ATM-HDFC-001",
  "bank_name": "HDFC Bank",
  "city": "Mumbai",
  "district": "Mumbai",
  "risk_score": 0.87,
  "tier": "DISPATCH",
  "status": "new",
  "recommended_action": "Immediate dispatch",
  "actioned_at": null
}
```
**Frontend uses:** `alert_id`, `atm_id`, `bank_name`, `city`, `district`, `risk_score`, `tier`, `status`, `recommended_action`, `actioned_at`

---

## Error Handling

| HTTP Status | Frontend Action |
|------------|-----------------|
| 401 | `showLogin()` — session expired |
| 403 | `toast("Access denied for your role", "error")` |
| 4xx/5xx | `toast("Request failed (status)", "error")` |
| Network error | Console warn, skeleton remains visible |

---

## GZip Compression

Verified: All JSON responses compressed via FastAPI GZipMiddleware.  
Risk scores: 445KB uncompressed → 22KB compressed (95.2% reduction).

---

## Cache Headers

Static assets (CSS, JS, vendor) served via FastAPI StaticFiles with appropriate caching.  
API endpoints: No-cache (dynamic data).  
In-memory caches: Stats summary (30s), risk scores (600s), mule network (300s), terminal nodes (300s).
