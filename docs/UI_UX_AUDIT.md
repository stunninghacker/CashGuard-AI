# CashGuard AI — UI/UX Audit

## Current Architecture
- **index.html** (281 lines) — Single-page with 3 dashboard shells (police, bank, i4c)
- **style.css** (376 lines) — Graphite/charcoal theme, IBM Plex Sans/Mono
- **app.js** (1487 lines) — Vanilla JS, Leaflet map, WebSocket, JWT auth
- **vendor/** — Leaflet (only dependency)

## Existing Components
| Component | Status | Issues |
|-----------|--------|--------|
| Login modal | Functional | Developer-oriented, no branding |
| Header | Functional | Too many buttons, no system status |
| Map (Leaflet) | Functional | 560px fixed height, no drawer |
| Hotspot table | Functional | No risk visualization |
| Alert table | Functional | Flat, no timeline/feed feel |
| Stats grid | Functional | All cards equal weight |
| Recovery queue | Functional | Flat list |
| Recovery funnel | Functional | Simple bars |
| Mule network (SVG) | Functional | Overwhelming, no drill-down |
| Mule graph table | Functional | Missing columns (shows —) |
| Ledger | Functional | Developer-oriented buttons |
| Drift panel | Functional | Too technical |
| Inbox | Functional | Raw messages |
| Handoffs | Functional | Flat list |
| Mobile nearby | Functional | Basic table |
| Evidence modal | Functional | Too much info at once |
| Toast | Functional | Minimal |
| Threshold explorer | Functional | Developer-oriented |
| i18n selector | Functional | Working |
| Simulated scenario | Functional | Clear labeling |

## Current UI Problems
1. **No sidebar navigation** — flat layout, hard to orient
2. **No information hierarchy** — all sections equal weight
3. **Tiny typography** — 11-13px throughout, hard to read on projector
4. **No ATM intelligence drawer** — clicking map marker opens popup, not drawer
5. **No intervention workflow visualization** — just status pills
6. **No Judge Mode** — no simplified demo flow
7. **No loading skeletons** — blank panels while loading
8. **No empty states** — just "muted" text
9. **No error states** — raw error messages
10. **No role-aware navigation** — same nav for all roles
11. **Header too busy** — too many buttons crammed together
12. **Login page not branded** — generic form
13. **No responsive design** — desktop-only
14. **Map not prominent enough** — shares space equally
15. **Recovery funnel too flat** — needs visual pipeline
16. **Model metrics section too technical** — needs professional framing
17. **No system status indicator** — no way to see if backend is healthy
18. **No toast system** — basic notifications only
19. **No drawer/panel system** — all info in modals
20. **No microinteractions** — no hover states, transitions

## Redesign Architecture

### App Shell
- Top command bar (compact)
- Left sidebar (role-aware navigation)
- Main workspace (scrollable)
- Right intelligence drawer (ATM detail, slide-in)

### New Components
- AppShell, Sidebar, TopBar
- StatCard (hero/normal variants)
- RiskBadge, RiskScore (large, prominent)
- AlertCard (timeline style)
- RiskMap (60-70% workspace)
- ATM Intelligence Drawer (right-side slide-in)
- FilterBar + FilterDrawer
- RecoveryFunnel (visual pipeline)
- ModelHealthCard
- DriftCard
- MuleGraph (investigation workspace)
- AuditLedger (professional)
- SystemStatus
- EmptyState, ErrorState, LoadingState (skeletons)
- Toast (professional notifications)
- Modal (evidence, technical details)
- Judge Mode (simplified interface)

### Design Tokens
- Dark navy/charcoal foundation
- Restrained gold/amber accent
- Controlled semantic risk colors
- IBM Plex Sans + Mono (preserved)
- Clear typography hierarchy (11-30px)
