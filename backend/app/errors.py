"""
How this works / why it is safe:
This module defines the unified domain error hierarchy for LedgerLine.
Every application error inherits from AppError, declaring an explicit HTTP
status code and machine-readable error code. Custom FastAPI handlers format
all failures into an immutable, structured envelope: {"error": {"code", "message", "request_id"}}.
Raw SQL messages, database connection strings, and stack traces are suppressed
from the client to prevent information disclosure.
"""

from typing import Any


def standardized_error_envelope(code: str, message: str, request_id: str) -> dict[str, Any]:
    """Create the contractual error envelope: {"error": {"code", "message", "request_id"}}."""
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }


class AppError(Exception):
    """Base application exception for all domain failures."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message or self.message)
        if message:
            self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}


# 400 Bad Request
class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"
    message = "Invalid request syntax or headers."


class MissingIdempotencyKeyError(BadRequestError):
    code = "missing_idempotency_key"
    message = "The 'Idempotency-Key' header is required for this operation."


class InvalidIdempotencyKeyError(BadRequestError):
    code = "invalid_idempotency_key"
    message = "The 'Idempotency-Key' must be 16-128 chars of [A-Za-z0-9_-]."


# 401 Unauthorized
class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Authentication required."


class InvalidCredentialsError(UnauthorizedError):
    code = "invalid_credentials"
    message = "Invalid email or password."


class SessionExpiredError(UnauthorizedError):
    code = "session_expired"
    message = "Session has expired or was revoked. Please log in again."


# 403 Forbidden
class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "You do not have permission to perform this action."


# 404 Not Found (Uniform for foreign accounts to stop enumeration)
class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "The requested resource was not found."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "Resource conflict detected."


class UserAlreadyExistsError(ConflictError):
    code = "user_already_exists"
    message = "A user with this email address already exists."


# 409 Conflict (Refusals recorded in ledger)
class RefusalError(AppError):
    status_code = 409
    code = "refused"
    message = "The money movement was refused by account rules."


class InsufficientFundsError(RefusalError):
    code = "insufficient_funds"
    message = "Transaction declined: balance would fall below overdraft limit."


class AccountFrozenError(RefusalError):
    code = "account_frozen"
    message = "Transaction declined: account is frozen."


class AccountClosedError(RefusalError):
    code = "account_closed"
    message = "Transaction declined: account is closed."


# 422 Unprocessable Entity
class ValidationError(AppError):
    status_code = 422
    code = "validation_error"
    message = "The request payload failed domain validation."


class IdempotencyKeyReuseError(AppError):
    status_code = 422
    code = "idempotency_key_reuse"
    message = "Idempotency key was previously submitted with a different request payload."


class InvalidDestinationError(AppError):
    status_code = 422
    code = "invalid_destination"
    message = "The destination account is invalid, closed, or frozen by an administrator."


# 429 Too Many Requests
class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"
    message = "Too many requests. Please slow down."


# 503 Service Unavailable (e.g. Lock timeout)
class LockTimeoutError(AppError):
    status_code = 503
    code = "lock_timeout"
    message = "The system is busy under high concurrent load. Please retry."
