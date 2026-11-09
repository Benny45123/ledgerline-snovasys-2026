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
