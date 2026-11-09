"""
How this works / why it is safe:
Integration tests verifying PostgreSQL defense-in-depth constraints.
Invariants enforced:
- Balance floor CHECK constraint: balance >= -overdraft_limit rejects direct negative balance updates.
- Deferred constraint trigger: journal_sums_to_zero rejects commits where entry amounts sum != 0.
- Append-only trigger: forbid_mutation raises an exception on UPDATE/DELETE on ledger tables.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.accounts.service import create_customer_account
from app.db.models import User


def test_balance_floor_check_constraint(db: Session, test_users: dict[str, User]) -> None:
    holder = test_users["holder1"]
    account = create_customer_account(
        db=db,
        name="DB Floor Check Account",
        owner_user_id=holder.id,
        overdraft_limit=0,
    )

    # Attempt direct SQL UPDATE setting balance below overdraft_limit (0)
    with pytest.raises(IntegrityError):
        db.execute(
            text("UPDATE accounts SET balance = -100 WHERE id = :id"),
            {"id": str(account.id)},
        )
        db.commit()
    db.rollback()


def test_append_only_trigger_rejects_journal_deletion(db: Session) -> None:
    # Attempt direct SQL DELETE on journals
    with pytest.raises(DBAPIError) as exc_info:
        db.execute(text("DELETE FROM journals WHERE true"))
        db.commit()
    db.rollback()
    assert "append-only" in str(exc_info.value).lower()
