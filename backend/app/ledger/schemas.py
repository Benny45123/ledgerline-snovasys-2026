"""
How this works / why it is safe:
This module defines strict Pydantic models for all money movement endpoints.
Monetary values are strictly validated as integers (paise) with positive boundaries (gt=0)
capped at MAX_AMOUNT_PAISE (₹10 crore). All models configure strict=True and extra="forbid",
preventing type coercions (like floats or booleans converted to ints) and rejecting
unauthorized parameter injection attacks. Response models never leak counterparty balances.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.config import settings


class StrictLedgerBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DepositRequest(StrictLedgerBaseModel):
    amount: int = Field(
        ...,
        gt=0,
        le=settings.MAX_AMOUNT_PAISE,
        description="Deposit amount in integer paise (e.g. ₹100.00 = 10000 paise)",
    )
    memo: Optional[str] = Field(None, max_length=140, description="Optional transaction memo")


class WithdrawRequest(StrictLedgerBaseModel):
    amount: int = Field(
        ...,
        gt=0,
        le=settings.MAX_AMOUNT_PAISE,
        description="Withdrawal amount in integer paise",
    )
    memo: Optional[str] = Field(None, max_length=140, description="Optional transaction memo")


class TransferRequest(StrictLedgerBaseModel):
    from_account_id: UUID = Field(..., description="Source account UUID")
    to_account_number: str = Field(..., min_length=1, max_length=64, description="Destination account number")
    amount: int = Field(
        ...,
        gt=0,
        le=settings.MAX_AMOUNT_PAISE,
        description="Transfer amount in integer paise",
    )
    memo: Optional[str] = Field(None, max_length=140, description="Optional transaction memo")

    @field_validator("from_account_id", mode="before")
    @classmethod
    def parse_from_account_id(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return UUID(v)
            except ValueError:
                raise ValueError("Invalid UUID format")
        return v


class AdjustmentRequest(StrictLedgerBaseModel):
    account_id: UUID = Field(..., description="Account UUID to adjust against SUSPENSE")
    amount: int = Field(
        ...,
        ne=0,
        ge=-settings.MAX_AMOUNT_PAISE,
        le=settings.MAX_AMOUNT_PAISE,
        description="Signed adjustment amount in paise (+ credit, - debit)",
    )
    reason: str = Field(..., min_length=5, max_length=255, description="Mandatory audit reason for adjustment")

    @field_validator("account_id", mode="before")
    @classmethod
    def parse_account_id(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return UUID(v)
            except ValueError:
                raise ValueError("Invalid UUID format")
        return v


class PostingEntryResponse(StrictLedgerBaseModel):
    account_id: UUID
    account_seq: int
    amount: int
    balance_after: int


class MovementResponse(StrictLedgerBaseModel):
    journal_id: UUID
    kind: str
    amount: int
    status: Literal["posted"] = "posted"
    entry: PostingEntryResponse
    created_at: datetime


class InitiatorInfo(StrictLedgerBaseModel):
    id: UUID
    email: str


class StatementItem(StrictLedgerBaseModel):
    type: Literal["posting", "refusal"]
    account_seq: int
    at: datetime
    kind: str
    amount: int
    balance_after: Optional[int] = None
    balance_at_attempt: Optional[int] = None
    counterparty: str
    initiated_by: InitiatorInfo
    journal_id: Optional[UUID] = None
    reason_code: Optional[str] = None
    request_id: str
    prev_hash: Optional[str] = None
    entry_hash: Optional[str] = None


class StatementResponse(StrictLedgerBaseModel):
    account_id: UUID
    currency: str
    current_balance: int
    overdraft_limit: int
    status: str
    items: List[StatementItem]
    has_more: bool = False
    next_after: Optional[int] = None
    next_cursor: Optional[int] = None
