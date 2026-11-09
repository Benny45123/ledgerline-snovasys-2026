"""
How this works / why it is safe:
This module tests Invariant I1 (Conservation) and Invariant I3 (Exactly Once)
for journal reversals under hostile concurrency.
Multiple worker threads are released at the exact same instant via a threading.Barrier,
each attempting to reverse the exact same journal using distinct idempotency keys.
Under row locking and the partial unique index on reverses_journal_id:
- Exactly 1 reversal succeeds.
- All other attempts are cleanly rejected.
- Balances reflect exactly one reversal, and exactly one reversal journal is written.
"""

import uuid

from sqlalchemy.orm import Session

from app.accounts.service import create_customer_account, get_system_account
from app.db.engine import SessionLocal
from app.db.models import Journal
from app.errors import LockTimeoutError, ValidationError
from app.ledger.service import post_movement
from tests.helpers.concurrency import fire_concurrent


def test_concurrent_reversals_cannot_duplicate(db: Session, test_users):
    """Prove that concurrent reversal attempts against the same journal serialize and only one succeeds."""
    admin = test_users["admin"]
    holder = test_users["holder1"]
    ext_acc = get_system_account(db, "external")

    # 1. Setup accounts
    acc_a = create_customer_account(db, "Reversal Acc A", holder.id, overdraft_limit=0)
    acc_b = create_customer_account(db, "Reversal Acc B", holder.id, overdraft_limit=0)

    # 2. Deposit into Acc A
    post_movement(
        db=db,
        user_id=holder.id,
        idempotency_key=f"init-rev-dep-{uuid.uuid4()}",
        request_id=f"req-init-dep-{uuid.uuid4().hex[:8]}",
        kind="deposit",
        source_account_id=ext_acc.id,
        destination_account_id=acc_a.id,
        amount=10000,
        raw_payload={"amount": 10000},
    )

    # 3. Transfer ₹40 (4,000 paise) from Acc A to Acc B
    transfer_movement, _ = post_movement(
        db=db,
        user_id=holder.id,
        idempotency_key=f"init-rev-transfer-{uuid.uuid4()}",
        request_id=f"req-init-xfer-{uuid.uuid4().hex[:8]}",
        kind="transfer",
        source_account_id=acc_a.id,
        destination_account_id=acc_b.id,
        amount=4000,
        raw_payload={"amount": 4000},
    )
    orig_journal_id = transfer_movement.journal_id

    # 4. 10 concurrent threads attempt to reverse orig_journal_id
    num_threads = 10

    def run_reversal(thread_idx: int):
        idem_key = f"race-rev-{thread_idx}-{uuid.uuid4()}"
        req_id = f"race-rev-req-{thread_idx}"
        for _ in range(8):
            thread_db: Session = SessionLocal()
            try:
                # Invert legs: Acc B -> Acc A
                res, is_replayed = post_movement(
                    db=thread_db,
                    user_id=admin.id,
                    idempotency_key=idem_key,
                    request_id=req_id,
                    kind="reversal",
                    source_account_id=acc_b.id,
                    destination_account_id=acc_a.id,
                    amount=4000,
                    raw_payload={"reason": f"Concurrent reversal test {thread_idx}"},
                    memo=f"Reversal of {orig_journal_id}",
                    reverses_journal_id=orig_journal_id,
                )
                return "posted"
            except (ValidationError, Exception) as e:
                if isinstance(e, LockTimeoutError):
                    continue
                # Expected rejection when already reversed
                return "rejected"
            finally:
                thread_db.close()
        return "timeout"

    results = fire_concurrent(num_threads, run_reversal)

    posted_count = sum(1 for _, res, _ in results if res == "posted")
    rejected_count = sum(1 for _, res, _ in results if res == "rejected")

    assert posted_count == 1, f"Expected exactly 1 reversal to succeed, got {posted_count}"
    assert rejected_count == num_threads - 1

    # 5. Verify database records
    reversal_journals = db.query(Journal).filter(Journal.reverses_journal_id == orig_journal_id).all()
    assert len(reversal_journals) == 1

    db.refresh(acc_a)
    db.refresh(acc_b)
    # Acc A balance should be 10000 (10000 - 4000 + 4000)
    assert acc_a.balance == 10000
    # Acc B balance should be 0 (0 + 4000 - 4000)
    assert acc_b.balance == 0
