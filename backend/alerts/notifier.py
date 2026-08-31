"""
Mock notification gateway — SMS + email.

Hackathon: writes human-readable logs (stored on the Alert record and shown
in the dashboard's alert feed). No external calls.

PRODUCTION INTEGRATION POINT:
    * SMS  -> NIC SMS Gateway / MSG91 / Twilio  (send_sms)
    * Email-> NIC email / SendGrid / AWS SES    (send_email)
    * API  -> I4C Alert API webhook pushed to state-LEA command centres
              (push_to_i4c_webhook — reserved stub)
Only these functions change when real gateways are wired in; the alert
engine and dashboard stay untouched.
"""
from __future__ import annotations

from datetime import datetime

import os
from pathlib import Path
from ..config import EMAIL_SMTP_HOST
from ..config import SMS_GATEWAY_API_KEY  # retained for backward compatibility

# Twilio optional imports
try:
    from twilio.rest import Client
except ImportError:  # pragma: no cover
    Client = None

# Determine mode based on env vars at import time
_TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
_TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
_TWILIO_FROM = os.getenv("TWILIO_FROM_NUMBER")
_DEMO_TARGET = os.getenv("DEMO_TARGET_PHONE")

if all([_TWILIO_SID, _TWILIO_TOKEN, _TWILIO_FROM, _DEMO_TARGET]):
    _GATEWAY_MODE = "LIVE"
    _twilio_client = Client(_TWILIO_SID, _TWILIO_TOKEN)
else:
    _GATEWAY_MODE = "MOCK"
    _twilio_client = None


def send_sms(recipient: str, message: str) -> str:
    """Send an SMS via Twilio if credentials are available, otherwise mock.

    Returns a log line string describing the action.
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    if _GATEWAY_MODE == "LIVE" and _twilio_client:
        try:
            sms = _twilio_client.messages.create(
                body=message,
                from_=_TWILIO_FROM,
                to=recipient,
            )
            log_line = f"[{timestamp}] [SMS:LIVE] Sent to {recipient}: SID={sms.sid}"
        except Exception as e:  # pragma: no cover
            log_line = f"[{timestamp}] [SMS:ERROR] Failed to send to {recipient}: {e}"
    else:
        # Mock mode: write to log file and return formatted line
        log_line = (
            f"[{timestamp}] [SMS:MOCK] SMS sent to {recipient}: {message}"
        )
        # Ensure logs directory exists (project-root logs/, same as run.py)
        log_path = Path(__file__).resolve().parents[2] / "logs" / "sms_dispatches.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
        # TODO: push to WebSocket feed for demo UI (placeholder)
    return log_line


def send_email(recipient: str, subject: str, body: str | None = None) -> str:
    """Send an email (mock implementation). Real integration can be added later."""
    body = body or subject
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    log_line = (
        f"[{timestamp}] [EMAIL:MOCK] Email sent to {recipient} | Subject: {subject} | {body}"
    )
    # Write to same logs directory for consistency
    log_path = Path(__file__).resolve().parents[2] / "logs" / "email_dispatches.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")
    return log_line


def push_to_i4c_webhook(payload: dict) -> str:
    """
    Reserved stub: pushes an alert JSON to the I4C state-LEA API for
    cross-jurisdiction dispatch in production.
    """
    return f"[WEBHOOK:{datetime.utcnow():%Y-%m-%d %H:%M:%S}] Payload queued for I4C: {payload}"