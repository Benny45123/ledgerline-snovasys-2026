"""
How this works / why it is safe:
This module defines Pydantic schemas for authentication payloads.
All models configure extra="forbid" and strict=True.
Unknown fields, type coercions, or malicious mass-assignment attempts
(e.g., passing 'role' or 'is_active' in the login payload) are rejected at the edge.
"""

import re
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


def validate_email_address(v: Any) -> str:
    """Validate email address with RFC 2606 test environment support (.test, .internal)."""
    if not isinstance(v, str):
        raise ValueError("Email must be a string.")
    clean = v.strip().lower()
    if not clean or len(clean) > 254:
        raise ValueError("Invalid email length.")
    if not EMAIL_REGEX.match(clean):
        raise ValueError("value is not a valid email address.")

    try:
        from email_validator import validate_email

        valid = validate_email(clean, check_deliverability=False, test_environment=True)
        return str(valid.normalized)
    except Exception:
        # Fallback for special-use test and internal domains (.test, .internal, .local, .example)
        if clean.endswith((".test", ".internal", ".local", ".localhost", ".example")):
            return clean
        raise ValueError("value is not a valid email address.")


Email = Annotated[str, BeforeValidator(validate_email_address)]


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LoginRequest(StrictBaseModel):
    email: Email = Field(..., description="User email address")
    password: str = Field(..., min_length=1, max_length=256, description="Plaintext password")


class RegisterRequest(StrictBaseModel):
    email: Email = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=256, description="Plaintext password (min 8 chars)")
    account_name: str | None = Field(None, min_length=1, max_length=128, description="Primary account display name")


class UserResponse(StrictBaseModel):
    id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime


class AccountSummaryResponse(StrictBaseModel):
    id: UUID
    number: str
    name: str
    currency: str
    balance: int


class LoginResponse(StrictBaseModel):
    token: str
    expires_at: datetime
    user: UserResponse


class RegisterResponse(StrictBaseModel):
    token: str
    expires_at: datetime
    user: UserResponse
    account: AccountSummaryResponse | None = None
