"""
CashGuard AI — Predictive Analytics Framework for Cybercrime Cash-Withdrawal Hotspots
Smart India Hackathon 2024 | Theme: Blockchain & Cybersecurity
Ministry of Home Affairs | I4C, CIS Division

Central configuration. Every value can be overridden by environment variables
or a `.env` file placed in the project root (see .env.example).

PRODUCTION NOTE (NCRP/CFCFRMS integration):
  * DATABASE_URL would point at the NCRP/CFCFRMS reporting store or a curated
    data lake (PostgreSQL/ClickHouse) instead of the local SQLite file.
  * API keys for real NCRP / CFCFRMS / bank data feeds would be injected here.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
# Hackathon default: local SQLite file.
# Production:  export DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/cashguard
# Nothing else in the codebase changes — all data access goes through
# repositories (backend/repositories.py), so the storage engine is swappable.
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{(BASE_DIR / 'data' / 'cashguard.db').as_posix()}",
)

# --------------------------------------------------------------------------
# ML artifacts
# --------------------------------------------------------------------------
ARTIFACT_DIR: Path = Path(os.getenv("ARTIFACT_DIR", str(BASE_DIR / "artifacts")))
MODEL_PATH: Path = ARTIFACT_DIR / os.getenv("MODEL_FILE", "model.joblib")
METRICS_PATH: Path = ARTIFACT_DIR / os.getenv("METRICS_FILE", "metrics.json")
DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))

# --------------------------------------------------------------------------
# Alert engine
# --------------------------------------------------------------------------
RISK_THRESHOLD: float = float(os.getenv("RISK_THRESHOLD", "0.7"))  # alert when P(fraud in 24h) >= 0.7
ALERT_COOLDOWN_HOURS: int = int(os.getenv("ALERT_COOLDOWN_HOURS", "6"))  # no duplicate alert for same ATM within N hours
ALERT_DEDUP_RISK_DELTA: float = float(os.getenv("ALERT_DEDUP_RISK_DELTA", "0.1"))  # dedup is bypassed when risk rose by more than this
SCORE_CACHE_SECONDS: int = int(os.getenv("SCORE_CACHE_SECONDS", "600"))  # risk-score inference cache TTL (scores valid within a window; recompute on data change)
SCHEDULER_INTERVAL_MINUTES: int = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "60"))
ALERT_AUTO_ESCALATE_MINUTES: int = int(os.getenv("ALERT_AUTO_ESCALATE_MINUTES", "120"))  # auto-escalate unacknowledged alerts after N minutes
HOTSPOT_K: int = int(os.getenv("HOTSPOT_K", "20"))
SEED_COMPLAINT_LOOKBACK_DAYS: int = int(os.getenv("SEED_COMPLAINT_LOOKBACK_DAYS", "45"))  # routing: complaints within this window seed an ATM's origin jurisdiction
FAIRNESS_ALERT_CAP: bool = os.getenv("FAIRNESS_ALERT_CAP", "true").lower() == "true"  # Item 5: per-state proportional alert cap (active fairness constraint)
FAIRNESS_CAP_PREFERENCE: str = os.getenv("FAIRNESS_CAP_PREFERENCE", "dispatch")  # which alerts keep high tier when capped: dispatch (highest-risk/directive) keeps rank, excess demoted to monitor

# --------------------------------------------------------------------------
# Simulation control
# --------------------------------------------------------------------------
# The demo runs on a fully synthetic timeline. To make the live dashboard show
# fresh risk scores without waiting for real time to pass, the engine can
# operate "as of" a simulated reference time (defaults to the latest timestamp
# present in the data). Set SIMULATED_NOW="" to use the real system clock.
SIMULATED_NOW: str = os.getenv("SIMULATED_NOW", "")

SEED: int = int(os.getenv("SEED", "42"))
CORS_ORIGINS: list[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")]
RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "240"))
LOGIN_RATE_LIMIT_PER_MINUTE: int = int(os.getenv("LOGIN_RATE_LIMIT_PER_MINUTE", "10"))

# --------------------------------------------------------------------------
# Demo resilience (Section 10 of the SIH spec)
# --------------------------------------------------------------------------
# DEMO_MODE=true serves risk scores / alerts / evidence from a pre-computed
# "golden path" cache (data/demo_cache/*.json) so the live walkthrough survives
# inference hangs or breakage on stage. Generate the cache with:
#     python scripts/cache_demo_mode.py
DEMO_MODE: bool = os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")
DEMO_CACHE_DIR: Path = DATA_DIR / "demo_cache"

# --------------------------------------------------------------------------
# Authentication (bcrypt + JWT — production: OAuth2/OIDC, see security.py)
# --------------------------------------------------------------------------
AUTH_SECRET: str = os.getenv("AUTH_SECRET", "dev-secret-change-in-production")
JWT_SECRET: str = os.getenv("JWT_SECRET", AUTH_SECRET)
JWT_ALGORITHM: str = "HS256"
JWT_TTL_MINUTES: int = int(os.getenv("JWT_TTL_MINUTES", "30"))
JWT_REFRESH_TTL_HOURS: int = int(os.getenv("JWT_REFRESH_TTL_HOURS", "24"))

# --------------------------------------------------------------------------
# Outbound webhooks (Phase 5 — real path to a LOCAL mock inbox in the demo)
# --------------------------------------------------------------------------
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "http://127.0.0.1:8000/mock-i4c-inbox")
CFCFRMS_WEBHOOK_URL: str = os.getenv("CFCFRMS_WEBHOOK_URL", "http://127.0.0.1:8000/mock-i4c-inbox")
ALLOW_TAMPER_DEMO: bool = os.getenv("ALLOW_TAMPER_DEMO", "").lower() in ("1", "true", "yes")

# --------------------------------------------------------------------------
# Shadow mode (Phase 14): predictions recorded but no operational actions.
# SHADOW_MODE=true -> alerts are stored with status="shadow"; no SMS/email
# webhook/WS dispatch; outcomes are still evaluated. Safe real-validation path.
# --------------------------------------------------------------------------
SHADOW_MODE: bool = os.getenv("SHADOW_MODE", "").lower() in ("1", "true", "yes")
WEBHOOK_TOKEN: str = os.getenv("WEBHOOK_TOKEN", "")  # if set, mock inbox POSTs must carry it

# --------------------------------------------------------------------------
# Mock notification gateways
# --------------------------------------------------------------------------
# Real deployments would plug in:
#   SMS_GATEWAY_API_KEY  (MSG91 / Twilio / NIC SMS)
#   EMAIL_SMTP_*         (SendGrid / AWS SES / NIC email)
# Mock mode writes logs only — see backend/alerts/notifier.py.
SMS_GATEWAY_API_KEY: str = os.getenv("SMS_GATEWAY_API_KEY", "mock-sms-key")
EMAIL_SMTP_HOST: str = os.getenv("EMAIL_SMTP_HOST", "mock.smtp.local")
# Ledger anchoring integration point (Blockchain theme). When set to a real
# testnet RPC (e.g. Polygon Amoy), the consensus root is anchored on-chain.
# EMPTY by default: anchoring is demo-grade replication only, NOT exercised
# against any external network — stated honestly.
LEDGER_ANCHOR_RPC_URL: str = os.getenv("LEDGER_ANCHOR_RPC_URL", "")

# Hourly-resolution mode (sub-daily prediction). Gates scripts/hourly_eval.py;
# the production forecast convention remains the daily 24h window.
HOURLY_MODE: bool = os.getenv("HOURLY_MODE", "").lower() in ("1", "true", "yes")
