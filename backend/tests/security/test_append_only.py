"""
How this works / why it is safe:
This module tests Invariant I4 (Append-Only Audit Trail).
It proves that direct UPDATE, DELETE, or TRUNCATE operations against
ledger and audit tables are rejected by database triggers (forbid_mutation).
A statement or journal cannot be quietly edited, deleted, or erased.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.accounts.service import get_system_account


def test_append_only_triggers_reject_mutations(db: Session):
    """Prove that triggers block UPDATE, DELETE, and TRUNCATE on ledger tables."""
    # Attempt to UPDATE ledger_entries
    with pytest.raises(Exception) as exc_update:
        db.execute(text("UPDATE ledger_entries SET amount = 99999 WHERE id = 1;"))
        db.commit()
    db.rollback()
    assert "append-only" in str(exc_update.value).lower() or "forbid_mutation" in str(exc_update.value).lower()

    # Attempt to DELETE from journals
    with pytest.raises(Exception) as exc_delete:
        db.execute(text("DELETE FROM journals WHERE id = '00000000-0000-0000-0000-000000000000';"))
        db.commit()
    db.rollback()
    assert "append-only" in str(exc_delete.value).lower() or "forbid_mutation" in str(exc_delete.value).lower()

    # Attempt to TRUNCATE refused_attempts
    with pytest.raises(Exception) as exc_truncate:
        db.execute(text("TRUNCATE TABLE refused_attempts;"))
        db.commit()
    db.rollback()
    assert "append-only" in str(exc_truncate.value).lower() or "forbid_mutation" in str(exc_truncate.value).lower()
