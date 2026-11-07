"""
How this works / why it is safe:
This module mitigates brute-force and credential-stuffing attacks.
Recent failed login attempts are queried from the security_events table across
a 15-minute sliding window per IP address and per email.
Instead of permanently locking accounts (which would allow an adversary to DoS
shared judge/seed accounts), progressive sleep delays are enforced and an HTTP 429
is returned when rate limits are exceeded. Every failure is audited.
"""
from typing import Any, Optional
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import SecurityEvent
from app.errors import RateLimitedError

MAX_ATTEMPTS_BEFORE_DELAY = 5
MAX_ATTEMPTS_BEFORE_429 = 15
WINDOW_MINUTES = 15


def check_login_throttle(db: Session, email: str, ip: Optional[str]) -> None:
    """Enforce progressive delay or 429 based on recent failed login events."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MINUTES)

    # Count failed attempts for this email
    email_fails = (
        db.query(func.count(SecurityEvent.id))
        .filter(
            SecurityEvent.event == "login_failed",
            SecurityEvent.created_at >= cutoff,
            SecurityEvent.detail["email"].as_string() == email,
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

    fails = max(email_fails, ip_fails)

    if fails >= MAX_ATTEMPTS_BEFORE_429:
        raise RateLimitedError(
            message="Too many failed login attempts. Please wait 15 minutes before retrying."
        )

    if fails >= MAX_ATTEMPTS_BEFORE_DELAY:
        delay = min(2.0, (fails - MAX_ATTEMPTS_BEFORE_DELAY + 1) * 0.25)
        time.sleep(delay)


def record_login_attempt(
    db: Session,
    success: bool,
    email: str,
    ip: Optional[str],
    request_id: Optional[str],
    user_id: Optional[Any] = None,
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
