"""
How this works / why it is safe:
Integration test verifying Invariant I5: Every attempt is recorded (each posting AND each refusal).
Failure modes:
- Refusing a transaction must NOT simply rollback without a record.
- A refused attempt must write to refused_attempts and commit the rejection to the idempotency key.
"""

import uuid
from sqlalchemy.orm import Session
from app.accounts.service import AccountService
from app.db.models import RefusedAttempt, User
from app.ledger.service import LedgerService


def test_refused_withdrawal_is_persisted_in_db(db_session: Session, seed_users: dict[str, User]) -> None:
    holder = seed_users["holder"]
    account = AccountService.create_customer_account(
        db=db_session,
        owner_id=holder.id,
        account_name="Refusal Record Test Account",
        actor_id=holder.id,
    )
    
    # Attempt an over-limit withdrawal of 5000 paise on an account with balance 0
    refusal_key = f"refusal-key-{uuid.uuid4().hex[:12]}"
    result = LedgerService.withdraw(
        db=db_session,
        account_id=account.id,
        amount=5000,
        user_id=holder.id,
        idempotency_key=refusal_key,
    )
    
    # Verify result structure
    assert result.status == "refused"
    assert result.reason_code == "insufficient_funds"
    assert result.journal_id is None
    
    # Verify a permanent refusal record was committed to refused_attempts
    refusal_records = (
        db_session.query(RefusedAttempt)
        .filter(RefusedAttempt.account_id == account.id)
        .all()
    )
    assert len(refusal_records) == 1
    assert refusal_records[0].attempted_amount == 5000
    assert refusal_records[0].reason_code == "insufficient_funds"
    assert refusal_records[0].initiated_by == holder.id
