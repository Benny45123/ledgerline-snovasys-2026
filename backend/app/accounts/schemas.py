"""
How this works / why it is safe:
This module defines Pydantic schemas for account management.
Accounts are created with zero balance. Status is constrained to active, frozen, or closed.
All input schemas prohibit extra attributes (extra="forbid") and enforce strict typing.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.schemas import Email


class StrictAccountBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CreateAccountRequest(StrictAccountBaseModel):
    name: str = Field(..., min_length=2, max_length=128, description="Account holder display name")
    owner_user_id: UUID = Field(..., description="User UUID to assign as initial owner")
    overdraft_limit: int = Field(default=0, ge=0, description="Authorized overdraft limit in paise")

    @field_validator("owner_user_id", mode="before")
    @classmethod
    def parse_owner_user_id(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return UUID(v)
            except ValueError as e:
                raise ValueError("Invalid UUID format") from e
        return v


class AccountResponse(StrictAccountBaseModel):
    id: UUID
    number: str
    name: str
    kind: str
    currency: str
    balance: int
    overdraft_limit: int
    status: str
    created_at: datetime


class AccountListResponse(StrictAccountBaseModel):
    accounts: list[AccountResponse]


class AdminUserAccountItem(StrictAccountBaseModel):
    id: UUID
    number: str
    name: str
    balance: int
    status: str


class AdminUserItem(StrictAccountBaseModel):
    id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime
    accounts: list[AdminUserAccountItem] = Field(default_factory=list)


class AdminUserListResponse(StrictAccountBaseModel):
    users: list[AdminUserItem]


class AdminCreateUserRequest(StrictAccountBaseModel):
    email: Email = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=256, description="Initial plaintext password (min 8 chars)")
    role: str = Field(default="holder", description="User role ('admin', 'holder', or 'auditor')")
    account_name: str | None = Field(default=None, max_length=128, description="Initial account display name")


class AdminToggleUserStatusRequest(StrictAccountBaseModel):
    is_active: bool = Field(..., description="Target active status for user")


class AccountRequestCreate(StrictAccountBaseModel):
    account_name: str = Field(..., min_length=2, max_length=128, description="Requested vault name")
    purpose: str | None = Field(default=None, max_length=512, description="Reason or business purpose")


class AccountRequestItem(StrictAccountBaseModel):
    id: UUID
    user_id: UUID
    account_name: str
    purpose: str | None = None
    currency: str = "INR"
    status: str
    created_at: datetime
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    account_id: UUID | None = None
    account_number: str | None = None


class AccountRequestListResponse(StrictAccountBaseModel):
    requests: list[AccountRequestItem]
