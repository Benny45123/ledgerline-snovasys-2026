"""
How this works / why it is safe:
This module mitigates brute-force and credential-stuffing attacks.
Recent failed login attempts are queried from the security_events table across
a 15-minute sliding window per IP address and per email.
Instead of permanently locking accounts (which would allow an adversary to DoS
shared judge/seed accounts), progressive sleep delays are enforced and an HTTP 429
is returned when rate limits are exceeded. Every failure is audited.
"""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import SecurityEvent
from app.errors import RateLimitedError

MAX_ATTEMPTS_BEFORE_DELAY = 5
MAX_ATTEMPTS_BEFORE_429 = 15
WINDOW_MINUTES = 15


def check_login_throttle(db: Session, email: str, ip: str | None) -> None:
    """Enforce progressive delay or 429 based on recent failed login events."""
    cutoff = datetime.now(UTC) - timedelta(minutes=WINDOW_MINUTES)

    # Count failed attempts for this email
    email_fails = (
        db.query(func.count(SecurityEvent.id))
        .filter(
            SecurityEvent.event == "login_failed",
            SecurityEvent.created_at >= cutoff,
            SecurityEvent.detail["email"].astext == email,
        )
        .scalar()
        or 0
    )

    # Count failed attempts for this IP if provided
    ip_fails = 0
    if ip:
        ip_fails = (
            db.query(func.count(SecurityEvent.id))
            .filter(
                SecurityEvent.event == "login_failed",
                SecurityEvent.created_at >= cutoff,
                SecurityEvent.ip == ip,
            )
            .scalar()
            or 0
        )

    # IP-level rate limiting blocks aggressive brute-force originators without locking out shared seed accounts
    if ip and ip_fails >= MAX_ATTEMPTS_BEFORE_429:
        raise RateLimitedError(message="Too many failed login attempts from this IP address. Please wait 15 minutes before retrying.")

    # Email & IP-level progressive delay slows down credential guessing without locking out evaluators
    fails = max(email_fails, ip_fails)
    if fails >= MAX_ATTEMPTS_BEFORE_DELAY:
        delay = min(2.0, (fails - MAX_ATTEMPTS_BEFORE_DELAY + 1) * 0.25)
        time.sleep(delay)


def record_login_attempt(
    db: Session,
    success: bool,
    email: str,
    ip: str | None,
    request_id: str | None,
    user_id: Any | None = None,
) -> None:
    """Record an immutable security event for every login attempt."""
    event_type = "login_success" if success else "login_failed"
    event = SecurityEvent(
        actor_user_id=user_id,
        event=event_type,
        detail={"email": email},
        request_id=request_id,
        ip=ip,
    )
    db.add(event)
    db.commit()
