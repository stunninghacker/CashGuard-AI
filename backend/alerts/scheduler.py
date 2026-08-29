"""
Alert scheduler — runs the risk engine periodically and generates alerts.

APScheduler BackgroundScheduler triggers an alert cycle every
SCHEDULER_INTERVAL_MINUTES (default 60). Each cycle:
    1. scores every ATM for the next 24h
    2. flags ATMs above RISK_THRESHOLD
    3. dedupes against open alerts (cooldown window)
    4. creates Alert records + mock SMS/email logs

Additionally, runs auto-escalation for stale unacknowledged alerts
(every cycle, checks alerts older than ALERT_AUTO_ESCALATE_MINUTES).

The same cycle can be triggered on demand (POST /api/alerts/run-now) — used
in the demo to show the full alert pipeline live.

Production: the scheduler would also push to I4C webhooks and bank APIs.
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from ..config import SCHEDULER_INTERVAL_MINUTES, ALERT_AUTO_ESCALATE_MINUTES
from ..database import SessionLocal
from ..services import run_alert_cycle, auto_escalate_stale_alerts

_scheduler: BackgroundScheduler | None = None


def _job() -> None:
    """Scheduled task — open its own session (runs off the request thread)."""
    db: Session = SessionLocal()
    try:
        summary = run_alert_cycle(db)
        print(f"[scheduler] Alert cycle done: {summary}", flush=True)
        # Auto-escalate stale alerts
        escalated = auto_escalate_stale_alerts(db, ALERT_AUTO_ESCALATE_MINUTES)
        if escalated:
            print(f"[scheduler] Auto-escalated {escalated} stale alerts", flush=True)
    except Exception as exc:  # pragma: no cover - keep the loop alive
        print(f"[scheduler] Alert cycle failed: {exc}", flush=True)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    """Idempotent scheduler start (called from FastAPI lifespan)."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    _scheduler.add_job(_job, "interval", minutes=SCHEDULER_INTERVAL_MINUTES, id="alert_cycle")
    _scheduler.start()
    print(f"[scheduler] Started — alert cycle every {SCHEDULER_INTERVAL_MINUTES} min", flush=True)
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None