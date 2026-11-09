"""
How this works / why it is safe:
This module provides cryptographic password management using Argon2id.
Argon2id provides state-of-the-art resistance against GPU/ASIC cracking.
To prevent user enumeration via timing analysis, unknown email lookups execute
a constant-time dummy verification against a static hash so response latency
remains indistinguishable from an authentic email lookup.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Precomputed static hash for constant-time dummy verification
DUMMY_HASH = ph.hash("constant-time-dummy-password-for-timing-defense")


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def dummy_verify() -> None:
    """Execute a simulated verification to neutralize timing discrepancies."""
    try:
        ph.verify(DUMMY_HASH, "wrong-password")
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        pass
