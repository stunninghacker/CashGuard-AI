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
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from ..alerts.scheduler import start_scheduler, stop_scheduler
from ..config import BASE_DIR, CORS_ORIGINS
from ..database import SessionLocal, init_db
from ..realtime import bind_loop
from .routes import (
    alerts,
    analytics,
    atms,
    auth,
    blockchain,
    complaints,
    drift,
    graph,
    i18n,
    ledger,
    metrics,
    mobile,
    mule_graph,
    realtime_routes,
    recovery,
    replay,
    reports,
    risk,
    routing,
    simulated,
    stats,
    train,
    withdrawals,
)


def _secure_boot_check() -> None:
    """SECURITY (red-team finding 1 / CRITICAL): never serve with the well-known
    default JWT secret. Anyone knowing this public value can forge an HS256 access
    token for any user (e.g. u-i4c) and gain full I4C_ADMIN privileges with zero
    credentials. Serving is refused unless the operator explicitly opts in for the
    demo (ALLOW_INSECURE_DEFAULT_JWT=1) or sets a strong JWT_SECRET."""
    from ..config import (
        ALLOW_INSECURE_DEFAULT_JWT,
        DEFAULT_JWT_SECRET_MARKER,
        JWT_SECRET,
    )

    if JWT_SECRET != DEFAULT_JWT_SECRET_MARKER:
        return  # operator supplied a real secret — fine
    if ALLOW_INSECURE_DEFAULT_JWT:
        import logging as _logging

        _logging.getLogger("cashguard.bootstrap").warning(
            "Serving with the INSECURE default JWT secret (demo opt-in). "
            "NOT acceptable for any non-demo deployment. Set JWT_SECRET >= 32 chars."
        )
        return
    raise RuntimeError(
        "Refusing to start: JWT_SECRET is the public default (used by a known red-team "
        "finding: HS256 token forgery => full I4C privilege escalation). Set a strong "
        "JWT_SECRET in the environment or explicitly set ALLOW_INSECURE_DEFAULT_JWT=1 "
        "for the hackathon demo only."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _secure_boot_check()
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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)
app.add_middleware(GZipMiddleware, minimum_size=500)


@app.middleware("http")
async def security_headers(request, call_next):
    """Add security headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def cache_headers(request, call_next):
    """Set appropriate cache headers: no-cache for frontend assets, short TTL for API data."""
    response = await call_next(request)
    path = request.url.path
    if path in ("/", "/index.html", "/app.js", "/style.css"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    elif path.startswith("/auth/"):
        response.headers["Cache-Control"] = "no-store"
    elif any(path.startswith(p) for p in ["/atms/banks", "/i18n/locales", "/train/status", "/drift/status"]):
        response.headers["Cache-Control"] = "public, max-age=60"
    elif any(path.startswith(p) for p in ["/risk-scores", "/alerts", "/stats/", "/hotspots", "/horizons", "/model/status", "/replay/"]):
        response.headers["Cache-Control"] = "private, max-age=10"
    return response


@app.middleware("http")
async def rate_limit(request, call_next):
    """Simple in-memory rate limiting (Phase 10): per-IP budget; stricter for
    the login endpoint to slow brute force. Demo-scale; production would use a
    distributed limiter."""
    from time import time

    from fastapi import HTTPException

    from ..config import LOGIN_RATE_LIMIT_PER_MINUTE, RATE_LIMIT_PER_MINUTE

    ip = request.client.host if request.client else "unknown"
    now = int(time())
    key = f"{ip}:{'login' if request.url.path.endswith('/auth/login') else 'api'}:{now // 60}"
    bucket = rate_limit._buckets
    bucket[key] = bucket.get(key, 0) + 1
    limit = LOGIN_RATE_LIMIT_PER_MINUTE if key.endswith("login") else RATE_LIMIT_PER_MINUTE
    if bucket[key] > limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded — try again shortly")
    return await call_next(request)


rate_limit._buckets = {}

# ---------------------------------- REST API ----------------------------------
app.include_router(auth.router)
app.include_router(complaints.router)
app.include_router(drift.router)
app.include_router(graph.router)
app.include_router(i18n.router)
app.include_router(atms.router)
app.include_router(analytics.router)
app.include_router(withdrawals.router)
app.include_router(risk.router)
app.include_router(alerts.router)
app.include_router(train.router)
app.include_router(stats.router)
app.include_router(reports.router)
app.include_router(ledger.router)
app.include_router(mobile.router)
app.include_router(recovery.router)
app.include_router(replay.router)
app.include_router(routing.router)
app.include_router(simulated.router)
app.include_router(realtime_routes.router)
app.include_router(mule_graph.router)
app.include_router(blockchain.router)
app.include_router(metrics.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "cashguard-ai"}


# ---------------------------------- Frontend ---------------------------------
app.mount("/", StaticFiles(directory=BASE_DIR / "frontend", html=True), name="dashboard")