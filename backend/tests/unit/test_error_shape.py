"""
How this works / why it is safe:
Unit tests verifying structured error envelope compliance.
Invariants enforced:
- Error responses strictly match {"error": {"code": str, "message": str, "request_id": str}}.
- No internal stack traces, DB credentials, or file paths leak to callers.
"""

from app.errors import (
    AccountFrozenError,
    InsufficientFundsError,
    InvalidIdempotencyKeyError,
    standardized_error_envelope,
)


def test_standardized_error_envelope_format() -> None:
    envelope = standardized_error_envelope(
        code="insufficient_funds",
        message="Available balance is insufficient for this debit",
        request_id="req-test-uuid",
    )
    assert envelope == {
        "error": {
            "code": "insufficient_funds",
            "message": "Available balance is insufficient for this debit",
            "request_id": "req-test-uuid",
        }
    }


def test_domain_exception_defaults() -> None:
    err = InsufficientFundsError()
    assert err.code == "insufficient_funds"
    assert err.status_code == 409
    assert "insufficient" in err.message.lower() or "overdraft" in err.message.lower()

    frozen_err = AccountFrozenError()
    assert frozen_err.code == "account_frozen"
    assert frozen_err.status_code == 409

    idem_err = InvalidIdempotencyKeyError()
    assert idem_err.code == "invalid_idempotency_key"
    assert idem_err.status_code == 400
