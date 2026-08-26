"""
CashGuard AI — FastAPI application entrypoint.

    * REST API: auth (bcrypt+JWT), data, ML, alerts, reports, recovery, ledger,
      webhooks + mock inbox, live-stream ingestion
    * WS /ws/alerts live push
    * APScheduler alert engine started on startup
    * Demo users seeded on startup (four roles, see README)

PRODUCTION NOTE: authentication would move to OAuth2/OIDC + org SSO (see
backend/security.py); the dependency-based RBAC structure already matches it.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..alerts.scheduler import start_scheduler, stop_scheduler
from ..config import BASE_DIR, CORS_ORIGINS
from ..database import SessionLocal, init_db
from ..realtime import bind_loop
from .routes import (
    alerts,
    atms,
    auth,
    complaints,
    ledger,
    realtime_routes,
    recovery,
    reports,
    risk,
    stats,
    train,
    withdrawals,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        from ..repositories import seed_demo_users

        seed_demo_users(db)
    finally:
        db.close()
    bind_loop(asyncio.get_running_loop())
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="CashGuard AI — Predictive Analytics Framework",
    description=(
        "Forecasts likely cash-withdrawal hotspots from cybercrime complaints "
        "for proactive law-enforcement and bank intervention (SIH | I4C)."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_frontend(request, call_next):
    """Prevent stale frontend assets: the dashboard is a hackathon demo that
    changes between rounds — a cached index.html/app.js breaks sign-in (old
    markup vs new JS). Force revalidation on every load."""
    response = await call_next(request)
    if request.url.path in ("/", "/index.html", "/app.js", "/style.css"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

# ---------------------------------- REST API ----------------------------------
app.include_router(auth.router)
app.include_router(complaints.router)
app.include_router(atms.router)
app.include_router(withdrawals.router)
app.include_router(risk.router)
app.include_router(alerts.router)
app.include_router(train.router)
app.include_router(stats.router)
app.include_router(reports.router)
app.include_router(ledger.router)
app.include_router(recovery.router)
app.include_router(realtime_routes.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "cashguard-ai"}


# ---------------------------------- Frontend ---------------------------------
app.mount("/", StaticFiles(directory=BASE_DIR / "frontend", html=True), name="dashboard")