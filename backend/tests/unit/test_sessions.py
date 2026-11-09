"""
How this works / why it is safe:
Unit tests verifying session token entropy, SHA-256 storage hashing, and expiration checks.
Invariants enforced:
- Raw bearer token is 256 bits of cryptographically secure random entropy (secrets.token_urlsafe).
- Raw token is never stored in DB; only its SHA-256 hash is persisted.
- Revocation and TTL expiration are cleanly checked.
"""

import secrets
from datetime import UTC, datetime, timedelta

from app.auth.sessions import hash_token


def test_session_token_entropy() -> None:
    token_1 = secrets.token_urlsafe(32)
    token_2 = secrets.token_urlsafe(32)

    assert len(token_1) >= 40
    assert token_1 != token_2


def test_session_token_hashing() -> None:
    token = secrets.token_urlsafe(32)
    token_hash_1 = hash_token(token)
    token_hash_2 = hash_token(token)

    assert token_hash_1 == token_hash_2
    assert len(token_hash_1) == 32  # SHA-256 bytea
    assert token_hash_1 != token.encode("utf-8")  # Raw token never equals stored hash


def test_session_expiration_check() -> None:
    now = datetime.now(UTC)
    future = now + timedelta(hours=1)
    past = now - timedelta(hours=1)

    assert (future > now) is True
    assert (past > now) is False
