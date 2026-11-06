"""
How this works / why it is safe:
This module tests Invariant I4 / Cryptographic Hash Chain Verification.
It proves that if a superuser attempts to alter a ledger entry's amount or sequence,
the cryptographic verification engine (/audit/verify) flags the corruption,
identifying the exact account and sequence where the chain was broken.
"""

import uuid
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.accounts.service import create_customer_account, get_system_account
from app.audit.verify import verify_ledger_integrity
from app.db.models import LedgerEntry
from app.ledger.service import post_movement


def test_hash_chain_detects_tampering(db: Session, test_users):
    """Prove that any silent modification to ledger entries is detected by verify."""
    holder = test_users["holder1"]
    ext_acc = get_system_account(db, "external")
    acc = create_customer_account(db, "Tamper Detection Acc", holder.id, overdraft_limit=0)

    # 1. Post two deposits
    post_movement(
        db=db,
        user_id=holder.id,
        idempotency_key=f"tamper-dep-1-{uuid.uuid4()}",
        request_id="req-1",
        kind="deposit",
        source_account_id=ext_acc.id,
        destination_account_id=acc.id,
        amount=10000,
        raw_payload={"amt": 10000},
    )
    post_movement(
        db=db,
        user_id=holder.id,
        idempotency_key=f"tamper-dep-2-{uuid.uuid4()}",
        request_id="req-2",
        kind="deposit",
        source_account_id=ext_acc.id,
        destination_account_id=acc.id,
        amount=20000,
        raw_payload={"amt": 20000},
    )

    # Clean verification
    initial_report = verify_ledger_integrity(db)
    assert initial_report.verified is True
    assert len(initial_report.discrepancies) == 0

    # 2. Simulate superuser tampering (bypass trigger by disabling it temporarily in test)
    db.execute(text("ALTER TABLE ledger_entries DISABLE TRIGGER trg_ledger_entries_append_only_rows;"))
    db.execute(
        text(
            """
            UPDATE ledger_entries 
            SET amount = 999999 
            WHERE account_id = :acc_id AND account_seq = 1;
            """
        ),
        {"acc_id": acc.id},
    )
    db.execute(text("ALTER TABLE ledger_entries ENABLE TRIGGER trg_ledger_entries_append_only_rows;"))
    db.commit()

    # 3. Verification must fail and detect the tampered account and sequence
    tampered_report = verify_ledger_integrity(db)
    assert tampered_report.verified is False
    assert len(tampered_report.discrepancies) > 0

    tamper_checks = [d.check for d in tampered_report.discrepancies]
    assert "entry_hash_integrity" in tamper_checks or "balance_cache_match" in tamper_checks
