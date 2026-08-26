"""
Standalone alert scheduler process (alternative to the in-app scheduler).

Usage:
    python scripts/run_scheduler.py

Runs one alert cycle immediately, then every SCHEDULER_INTERVAL_MINUTES.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.alerts.scheduler import start_scheduler  # noqa: E402
from backend.config import SCHEDULER_INTERVAL_MINUTES  # noqa: E402
from backend.database import SessionLocal  # noqa: E402
from backend.services import run_alert_cycle  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        print(run_alert_cycle(db))
    finally:
        db.close()
    start_scheduler()
    print(f"Standalone scheduler running (cycle every {SCHEDULER_INTERVAL_MINUTES} min). Ctrl+C to stop.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()