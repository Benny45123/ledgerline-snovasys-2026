"""
How this works / why it is safe:
Unit tests verifying strict validation on money amounts.
Invariants enforced:
- Amounts must be positive integers (paise).
- Never allow floats, decimals, booleans, negative amounts, zero, or amounts above MAX_AMOUNT_PAISE.
- Extra fields must be forbidden (extra="forbid").
"""

from uuid import UUID
import pytest
from pydantic import ValidationError
from app.ledger.schemas import AdjustmentRequest, DepositRequest, TransferRequest, WithdrawRequest
from app.config import settings


def test_positive_integer_paise_accepted() -> None:
    req = DepositRequest(amount=10000)
    assert req.amount == 10000


def test_zero_amount_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        DepositRequest(amount=0)
    assert "Input should be greater than 0" in str(exc_info.value)


def test_negative_amount_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        WithdrawRequest(amount=-500)
    assert "Input should be greater than 0" in str(exc_info.value)


def test_float_rejected_by_strict_mode() -> None:
    with pytest.raises(ValidationError):
        DepositRequest.model_validate({"amount": 100.50})


def test_string_amount_rejected_by_strict_mode() -> None:
    with pytest.raises(ValidationError):
        DepositRequest.model_validate({"amount": "1000"})


def test_boolean_rejected_by_strict_mode() -> None:
    with pytest.raises(ValidationError):
        DepositRequest.model_validate({"amount": True})


def test_amount_exceeding_max_cap_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        DepositRequest(amount=settings.MAX_AMOUNT_PAISE + 1)
    assert "Input should be less than or equal to" in str(exc_info.value)


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError) as exc_info:
        DepositRequest.model_validate({"amount": 5000, "currency": "INR", "extra_field": "exploit"})
    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_transfer_request_string_uuid_accepted() -> None:
    req = TransferRequest.model_validate({
        "from_account_id": "f2ec4856-1d48-4d0b-917b-f1beffa9c00b",
        "to_account_number": "ACC-12345",
        "amount": 5000,
        "memo": "Test transfer",
    })
    assert isinstance(req.from_account_id, UUID)
    assert str(req.from_account_id) == "f2ec4856-1d48-4d0b-917b-f1beffa9c00b"
    assert req.amount == 5000


def test_transfer_request_invalid_uuid_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        TransferRequest.model_validate({
            "from_account_id": "not-a-valid-uuid",
            "to_account_number": "ACC-12345",
            "amount": 5000,
        })
    assert "Invalid UUID format" in str(exc_info.value)


def test_transfer_request_float_amount_rejected() -> None:
    with pytest.raises(ValidationError):
        TransferRequest.model_validate({
            "from_account_id": "f2ec4856-1d48-4d0b-917b-f1beffa9c00b",
            "to_account_number": "ACC-12345",
            "amount": 50.75,
        })


def test_adjustment_request_string_uuid_accepted() -> None:
    req = AdjustmentRequest.model_validate({
        "account_id": "f2ec4856-1d48-4d0b-917b-f1beffa9c00b",
        "amount": 1000,
        "reason": "Audited balance correction",
    })
    assert isinstance(req.account_id, UUID)
    assert str(req.account_id) == "f2ec4856-1d48-4d0b-917b-f1beffa9c00b"
    assert req.amount == 1000


def test_adjustment_request_invalid_uuid_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AdjustmentRequest.model_validate({
            "account_id": "not-a-valid-uuid",
            "amount": 1000,
            "reason": "Audited balance correction",
        })
    assert "Invalid UUID format" in str(exc_info.value)
