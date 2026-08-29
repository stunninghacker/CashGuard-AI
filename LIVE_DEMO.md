# LIVE_DEMO.md — Live Demo (deployment status, honest)

This file is the **live demo deployment tracker**. It exists to be explicit and
honest: a production-grade **deployment package is shipped** (multi-stage
`Dockerfile`, `render.yaml`, `fly.toml`), but **no live URL has been cut yet**.

## Status

| Item | Status |
|------|--------|
| Deployment package (Dockerfile / render.yaml / fly.toml) | **READY** (in-repo, this commit) |
| Live URL | **PLACEHOLDER — not yet deployed** |
| Health endpoint | `/health` (FastAPI, returns 200 once up) |
| Demo data | Synthetic-only (see REAL_DATA_GAP.md — no real personal data) |

**Placeholder live URL (to be replaced when a deploy is cut):**
```
<LIVE-DEMO-URL-PLACEHOLDER>
```

## How to deploy (when authorized)
- **Render** — push this repo to GitHub, create a Web Service from the
  Blueprint (`render.yaml`), attach the `/app/data` disk, and set
  `ALLOW_TAMPER_DEMO=false`. Render runs the Docker health check on `/health`.
- **Fly.io** — `fly launch --dockerfile Dockerfile`, then `fly deploy`
  (uses `fly.toml` + the attached volume).
- **Any Docker host** — `docker build -t cashguard .` && `docker run -p 8000:8000
  -v cashguard-volume:/app/data cashguard`.

## Deployment safety (non-negotiable before going live)
1. Set **`ALLOW_TAMPER_DEMO=false`** (the demo tamper-toggle must be OFF in any
   shared deployment).
2. Do **NOT** reuse the synthetic demo logins from `docs/DEMO_CREDENTIALS.md`.
3. Inject real secrets (JWT secret, webhook URLs) **only** via host environment —
   never ship them in code (see DATA_PROTECTION.md §5).
4. The demo remains **synthetic-data only**; enabling real I4C/bank/CFCFRMS data
   is governed by REAL_DATA_VALIDATION_PROTOCOL.md and I4C authorization —
   it is **not** part of this deployment.

## Why is it still a placeholder?
External hosting (YouTube upload, Render/Railway/Fly accounts, live NCRP/CFCFRMS
data) requires actions and accounts outside this repo. The code is
deployment-ready; the live endpoint requires an authorized deployment step. This
openly separates *what is ready in-repo* from *what requires an external action* —
we do not claim a live demo we have not stood up.
