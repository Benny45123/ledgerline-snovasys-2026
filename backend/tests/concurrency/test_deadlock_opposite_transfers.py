"""
How this works / why it is safe:
This module tests Invariant I1/I2 against concurrency deadlocks.
Two accounts A and B concurrently execute transfers in opposite directions:
Thread A transfers A -> B while Thread B transfers B -> A.
Because post_movement() acquires locks sorted strictly by account UUID (ORDER BY id),
cyclic lock dependency is eliminated and zero deadlock exceptions (40P01) occur.
"""

import time
import uuid

from sqlalchemy.orm import Session

from app.accounts.service import create_customer_account, get_system_account
from app.db.engine import SessionLocal
from app.errors import LockTimeoutError
from app.ledger.service import post_movement
from tests.helpers.concurrency import fire_concurrent


def test_deadlock_opposite_transfers(db: Session, test_users):
    """Prove that concurrent opposite transfers (A->B and B->A) do not deadlock."""
    holder1 = test_users["holder1"]
    holder2 = test_users["holder2"]
    ext_acc = get_system_account(db, "external")

    # Create Account A and Account B
    acc_a = create_customer_account(db, "Deadlock Acc A", holder1.id, overdraft_limit=0)
    acc_b = create_customer_account(db, "Deadlock Acc B", holder2.id, overdraft_limit=0)

    # Fund both accounts with ₹10,000 (1,000,000 paise)
    post_movement(
        db=db,
        user_id=holder1.id,
        idempotency_key=f"fund-a-{uuid.uuid4()}",
        request_id="req-fund-a",
        kind="deposit",
        source_account_id=ext_acc.id,
        destination_account_id=acc_a.id,
        amount=1000000,
        raw_payload={"amount": 1000000},
    )
    post_movement(
        db=db,
        user_id=holder2.id,
        idempotency_key=f"fund-b-{uuid.uuid4()}",
        request_id="req-fund-b",
        kind="deposit",
        source_account_id=ext_acc.id,
        destination_account_id=acc_b.id,
        amount=1000000,
        raw_payload={"amount": 1000000},
    )

    db.refresh(acc_a)
    db.refresh(acc_b)
    initial_combined_balance = acc_a.balance + acc_b.balance

    num_threads = 20

    def run_opposite_transfer(thread_idx: int):
        for attempt in range(8):
            thread_db: Session = SessionLocal()
            try:
                # Alternating direction based on thread parity
                if thread_idx % 2 == 0:
                    src, dest, user = acc_a.id, acc_b.id, holder1.id
                else:
                    src, dest, user = acc_b.id, acc_a.id, holder2.id

                post_movement(
                    db=thread_db,
                    user_id=user,
                    idempotency_key=f"deadlock-tx-{thread_idx}-{attempt}-{uuid.uuid4()}",
                    request_id=f"deadlock-req-{thread_idx}",
                    kind="transfer",
                    source_account_id=src,
                    destination_account_id=dest,
                    amount=1000,
                    raw_payload={"thread": thread_idx},
                )
                return "SUCCESS"
            except LockTimeoutError:
                time.sleep(0.15 * (attempt + 1))
            finally:
                thread_db.close()
        raise LockTimeoutError("Exhausted retries on high concurrency.")

    results = fire_concurrent(num_threads, run_opposite_transfer, start_barrier=True)
    exceptions = [exc for _, _, exc in results if exc]

    assert len(exceptions) == 0, f"Deadlock or operational failure occurred: {exceptions}"

    # Verify combined balance of A and B is completely preserved
    db.refresh(acc_a)
    db.refresh(acc_b)
    assert acc_a.balance + acc_b.balance == initial_combined_balance
