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

from app.db.models import Journal, LedgerEntry


def test_append_only_triggers_reject_mutations(db: Session):
    """Prove that triggers block UPDATE, DELETE, and TRUNCATE on ledger tables."""
    entry = db.query(LedgerEntry).first()
    assert entry is not None, "Ledger entry must exist to test row-level trigger"
    orig_amount = entry.amount
    try:
        with pytest.raises(Exception) as exc_update:
            db.execute(text("UPDATE ledger_entries SET amount = 99999 WHERE id = :eid;"), {"eid": entry.id})
            db.commit()
        db.rollback()
        assert "append-only" in str(exc_update.value).lower() or "forbid_mutation" in str(exc_update.value).lower()
    finally:
        db.rollback()
        current = db.query(LedgerEntry).filter(LedgerEntry.id == entry.id).first()
        if current and current.amount != orig_amount:
            db.execute(text("UPDATE ledger_entries SET amount = :amt WHERE id = :eid;"), {"amt": orig_amount, "eid": entry.id})
            db.commit()

    # Attempt to DELETE from journals
    journal = db.query(Journal).first()
    assert journal is not None, "Journal must exist to test row-level trigger"
    with pytest.raises(Exception) as exc_delete:
        db.execute(text("DELETE FROM journals WHERE id = :jid;"), {"jid": journal.id})
        db.commit()
    db.rollback()
    assert "append-only" in str(exc_delete.value).lower() or "forbid_mutation" in str(exc_delete.value).lower()

    # Attempt to TRUNCATE refused_attempts
    with pytest.raises(Exception) as exc_truncate:
        db.execute(text("TRUNCATE TABLE refused_attempts;"))
        db.commit()
    db.rollback()
    assert "append-only" in str(exc_truncate.value).lower() or "forbid_mutation" in str(exc_truncate.value).lower()
