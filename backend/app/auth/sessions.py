"""
How this works / why it is safe:
This module manages session tokens and database state.
Tokens are 256-bit high-entropy random strings generated via secrets.token_urlsafe.
The raw token is returned to the client once upon login and never retained in plaintext.
Only the SHA-256 hash (bytea) is persisted in the database. If the database is dumped,
no active sessions can be hijacked. Expiry and explicit revocation (logout) are strictly
checked on every authenticated request.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import SessionModel, User


def hash_token(token: str) -> bytes:
    """Compute the SHA-256 digest of an opaque bearer token."""
    return hashlib.sha256(token.encode("utf-8")).digest()


def create_session(db: Session, user: User) -> tuple[str, datetime]:
    """Generate a new 256-bit session token and store its SHA-256 hash."""
    raw_token = secrets.token_urlsafe(32)
    token_digest = hash_token(raw_token)
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.SESSION_TTL_MINUTES)

    session_record = SessionModel(
        token_hash=token_digest,
        user_id=user.id,
        expires_at=expires_at,
        revoked_at=None,
    )
    db.add(session_record)
    db.commit()
    return raw_token, expires_at


def get_user_from_token(db: Session, raw_token: str) -> User | None:
    """Look up an active user by validating the token's hash, expiry, and revocation."""
    token_digest = hash_token(raw_token)
    now = datetime.now(UTC)

    session_record = (
        db.query(SessionModel)
        .filter(
            SessionModel.token_hash == token_digest,
            SessionModel.revoked_at.is_(None),
            SessionModel.expires_at > now,
        )
        .first()
    )

    if not session_record:
        return None

    user = db.query(User).filter(User.id == session_record.user_id, User.is_active.is_(True)).first()
    return user


def revoke_session(db: Session, raw_token: str) -> bool:
    """Revoke a session immediately upon user logout."""
    token_digest = hash_token(raw_token)
    session_record = db.query(SessionModel).filter(SessionModel.token_hash == token_digest).first()
    if session_record and session_record.revoked_at is None:
        session_record.revoked_at = datetime.now(UTC)
        db.commit()
        return True
    return False
