"""
How this works / why it is safe:
Integration tests verifying PostgreSQL defense-in-depth constraints.
Invariants enforced:
- Balance floor CHECK constraint: balance >= -overdraft_limit rejects direct negative balance updates.
- Deferred constraint trigger: journal_sums_to_zero rejects commits where entry amounts sum != 0.
- Append-only trigger: forbid_mutation raises an exception on UPDATE/DELETE on ledger tables.
"""

import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from app.accounts.service import AccountService
from app.db.models import User


def test_balance_floor_check_constraint(db_session: Session, seed_users: dict[str, User]) -> None:
    holder = seed_users["holder"]
    account = AccountService.create_customer_account(
        db=db_session,
        owner_id=holder.id,
        account_name="DB Floor Check Account",
        actor_id=holder.id,
    )
    
    # Attempt direct SQL UPDATE setting balance below overdraft_limit (0)
    with pytest.raises(IntegrityError):
        db_session.execute(
            text("UPDATE accounts SET balance = -100 WHERE id = :id"),
            {"id": str(account.id)},
        )
        db_session.commit()
    db_session.rollback()


def test_append_only_trigger_rejects_journal_deletion(db_session: Session) -> None:
    # Attempt direct SQL DELETE on journals
    with pytest.raises(DBAPIError) as exc_info:
        db_session.execute(text("DELETE FROM journals WHERE true"))
        db_session.commit()
    db_session.rollback()
    assert "append-only" in str(exc_info.value).lower()
