"""
How this works / why it is safe:
This module proves Invariant I1 (Conservation of Money).
It executes a mixed sequence of deposits, transfers, and withdrawals.
It asserts that every single journal's entries sum to exactly 0,
the database-wide sum of ALL accounts (customer + system) is exactly 0,
and the cryptographic verify engine confirms zero discrepancies.
"""

import uuid
from sqlalchemy.orm import Session
from app.accounts.service import create_customer_account, get_system_account
from app.audit.verify import verify_ledger_integrity
from app.ledger.service import post_movement


def test_conservation_invariant(db: Session, test_users):
    """Prove that every journal sums to 0 and global sum(balance) == 0."""
    holder1 = test_users["holder1"]
    holder2 = test_users["holder2"]
    ext_acc = get_system_account(db, "external")

    initial_ext_balance = ext_acc.balance
    from app.db.models import Account
    from sqlalchemy import func
    initial_customer_sum = int(
        db.query(func.coalesce(func.sum(Account.balance), 0))
        .filter(Account.kind == "customer")
        .scalar()
        or 0
    )

    # 1. Create two customer accounts
    acc1 = create_customer_account(db, "Conservation Acc 1", holder1.id, overdraft_limit=0)
    acc2 = create_customer_account(db, "Conservation Acc 2", holder2.id, overdraft_limit=0)

    # 2. Deposit ₹1,000 (100,000 paise) into Acc 1
    post_movement(
        db=db,
        user_id=holder1.id,
        idempotency_key=f"idem-dep-{uuid.uuid4()}",
        request_id=f"req-{uuid.uuid4()}",
        kind="deposit",
        source_account_id=ext_acc.id,
        destination_account_id=acc1.id,
        amount=100000,
        raw_payload={"amt": 100000},
        memo="Deposit ₹1,000",
    )

    # 3. Transfer ₹400 (40,000 paise) from Acc 1 to Acc 2
    post_movement(
        db=db,
        user_id=holder1.id,
        idempotency_key=f"idem-tx-{uuid.uuid4()}",
        request_id=f"req-{uuid.uuid4()}",
        kind="transfer",
        source_account_id=acc1.id,
        destination_account_id=acc2.id,
        amount=40000,
        raw_payload={"amt": 40000},
        memo="Transfer ₹400",
    )

    # 4. Withdraw ₹150 (15,000 paise) from Acc 2
    post_movement(
        db=db,
        user_id=holder2.id,
        idempotency_key=f"idem-wd-{uuid.uuid4()}",
        request_id=f"req-{uuid.uuid4()}",
        kind="withdrawal",
        source_account_id=acc2.id,
        destination_account_id=ext_acc.id,
        amount=15000,
        raw_payload={"amt": 15000},
        memo="Withdrawal ₹150",
    )

    # Refresh accounts
    db.refresh(acc1)
    db.refresh(acc2)
    db.refresh(ext_acc)

    # Balance expectations
    # Acc 1: +100,000 - 40,000 = 60,000 paise
    # Acc 2: +40,000 - 15,000 = 25,000 paise
    # Ext Acc: delta is -100,000 + 15,000 = -85,000 paise
    assert acc1.balance == 60000
    assert acc2.balance == 25000
    assert ext_acc.balance == initial_ext_balance - 85000

    # System sum: 60,000 + 25,000 + (-85,000) = 0
    total_delta = acc1.balance + acc2.balance + (ext_acc.balance - initial_ext_balance)
    assert total_delta == 0

    # Run cryptographic verification
    report = verify_ledger_integrity(db)
    assert report.verified is True
    assert len(report.discrepancies) == 0
    assert report.global_balance_sum == 0
    assert report.customer_balance_sum == initial_customer_sum + 85000
