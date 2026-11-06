"""
How this works / why it is safe:
This module defines domain errors specific to ledger operations.
It encapsulates business refusals (insufficient funds, frozen accounts, self-transfers)
and concurrency conditions (lock timeouts, idempotency collisions).
Mapping errors explicitly prevents generic 500s on expected business refusal paths.
"""

from app.errors import (
    AccountClosedError,
    AccountFrozenError,
    IdempotencyKeyReuseError,
    InsufficientFundsError,
    InvalidDestinationError,
    LockTimeoutError,
    RefusalError,
    ValidationError,
)

__all__ = [
    "RefusalError",
    "InsufficientFundsError",
    "AccountFrozenError",
    "AccountClosedError",
    "ValidationError",
    "IdempotencyKeyReuseError",
    "InvalidDestinationError",
    "LockTimeoutError",
]
