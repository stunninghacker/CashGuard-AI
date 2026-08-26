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

from ..config import EMAIL_SMTP_HOST, SMS_GATEWAY_API_KEY

_GATEWAY_MODE = "MOCK"


def send_sms(recipient: str, message: str) -> str:
    """
    Simulate an SMS. Returns the log line stored on the alert.
    Real impl: requests.post(SMS_ENDPOINT, json={to, text, api_key=SMS_GATEWAY_API_KEY})
    """
    if _GATEWAY_MODE == "MOCK":
        return (
            f"[{datetime.utcnow():%Y-%m-%d %H:%M:%S}] [SMS:{SMS_GATEWAY_API_KEY[:8]}...] "
            f"SMS sent to {recipient}: {message}"
        )
    return message  # pragma: no cover


def send_email(recipient: str, subject: str, body: str | None = None) -> str:
    """
    Simulate an email. Returns the log line stored on the alert.
    Real impl: smtplib / SendGrid API using EMAIL_SMTP_HOST credentials.
    """
    body = body or subject
    if _GATEWAY_MODE == "MOCK":
        return (
            f"[{datetime.utcnow():%Y-%m-%d %H:%M:%S}] [EMAIL:{EMAIL_SMTP_HOST}] "
            f"Email sent to {recipient} | Subject: {subject} | {body}"
        )
    return body  # pragma: no cover


def push_to_i4c_webhook(payload: dict) -> str:
    """
    Reserved stub: pushes an alert JSON to the I4C state-LEA API for
    cross-jurisdiction dispatch in production.
    """
    return f"[WEBHOOK:{datetime.utcnow():%Y-%m-%d %H:%M:%S}] Payload queued for I4C: {payload}"