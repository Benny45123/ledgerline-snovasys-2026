"""
How this works / why it is safe:
Integration test verifying Invariant I5: Every attempt is recorded (each posting AND each refusal).
Failure modes:
- Refusing a transaction must NOT simply rollback without a record.
- A refused attempt must write to refused_attempts and commit the rejection to the idempotency key.
"""

import uuid
import pytest
from sqlalchemy.orm import Session
from app.accounts.service import create_customer_account, get_system_account
from app.db.models import RefusedAttempt, User
from app.errors import InsufficientFundsError
from app.ledger.service import post_movement


def test_refused_withdrawal_is_persisted_in_db(db: Session, test_users: dict[str, User]) -> None:
    holder = test_users["holder1"]
    ext_acc = get_system_account(db, "external")
    account = create_customer_account(
        db=db,
        name="Refusal Record Test Account",
        owner_user_id=holder.id,
        overdraft_limit=0,
    )
    
    # Attempt an over-limit withdrawal of 5000 paise on an account with balance 0
    refusal_key = f"refusal-key-{uuid.uuid4().hex[:12]}"
    with pytest.raises(InsufficientFundsError):
        post_movement(
            db=db,
            user_id=holder.id,
            idempotency_key=refusal_key,
            request_id=f"req-refusal-{uuid.uuid4().hex[:8]}",
            kind="withdrawal",
            source_account_id=account.id,
            destination_account_id=ext_acc.id,
            amount=5000,
            raw_payload={"amount": 5000},
            memo="Overdraft withdrawal test",
        )
    
    # Verify a permanent refusal record was committed to refused_attempts
    refusal_records = (
        db.query(RefusedAttempt)
        .filter(RefusedAttempt.account_id == account.id)
        .all()
    )
    assert len(refusal_records) == 1
    assert refusal_records[0].amount == 5000
    assert refusal_records[0].reason_code == "insufficient_funds"
    assert refusal_records[0].initiated_by == holder.id
