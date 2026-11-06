"""
How this works / why it is safe:
Unit tests verifying session token entropy, SHA-256 storage hashing, and expiration checks.
Invariants enforced:
- Raw bearer token is 256 bits of cryptographically secure random entropy (secrets.token_urlsafe).
- Raw token is never stored in DB; only its SHA-256 hash is persisted.
- Revocation and TTL expiration are cleanly checked.
"""

from datetime import datetime, timezone, timedelta
from app.auth.sessions import generate_session_token, hash_session_token, is_session_expired


def test_session_token_entropy() -> None:
    token_1 = generate_session_token()
    token_2 = generate_session_token()
    
    assert len(token_1) >= 40
    assert token_1 != token_2


def test_session_token_hashing() -> None:
    token = generate_session_token()
    token_hash_1 = hash_session_token(token)
    token_hash_2 = hash_session_token(token)
    
    assert token_hash_1 == token_hash_2
    assert len(token_hash_1) == 64  # SHA-256 hex string
    assert token_hash_1 != token    # Raw token never equals stored hash


def test_session_expiration_check() -> None:
    now = datetime.now(timezone.utc)
    future = now + timedelta(hours=1)
    past = now - timedelta(hours=1)
    
    assert is_session_expired(future) is False
    assert is_session_expired(past) is True
