"""
How this works / why it is safe:
This module tests Invariant I2 (Balance Floor) under hostile concurrency.
Twenty worker threads are released at the exact same instant through a threading.Barrier,
each attempting to withdraw ₹30 from an account holding ₹100.
Under row locking and check-after-lock semantics:
- Exactly 3 withdrawals succeed (90 deducted).
- Exactly 17 withdrawals are refused (409 Conflict).
- Final balance is exactly ₹10.
- Exactly 3 journals and 17 refused_attempts rows are recorded in the ledger.
"""

import time
import uuid

from sqlalchemy.orm import Session

from app.accounts.service import create_customer_account, get_system_account
from app.db.engine import SessionLocal
from app.db.models import Journal, RefusedAttempt
from app.errors import InsufficientFundsError, LockTimeoutError
from app.ledger.service import post_movement
from tests.helpers.concurrency import fire_concurrent


def test_no_overdraft_race(db: Session, test_users):
    """Prove that 20 concurrent withdrawals against a ₹100 balance yield exactly 3 successes and 17 refusals."""
    holder = test_users["holder1"]
    ext_acc = get_system_account(db, "external")

    # 1. Create account with overdraft_limit = 0
    acc = create_customer_account(db, "Race Test Account", holder.id, overdraft_limit=0)

    # 2. Deposit ₹100 (10,000 paise)
    post_movement(
        db=db,
        user_id=holder.id,
        idempotency_key=f"init-dep-{uuid.uuid4()}",
        request_id=f"req-{uuid.uuid4()}",
        kind="deposit",
        source_account_id=ext_acc.id,
        destination_account_id=acc.id,
        amount=10000,
        raw_payload={"amount": 10000},
        memo="Initial ₹100",
    )

    db.refresh(acc)
    assert acc.balance == 10000

    # 3. Prepare 20 concurrent withdrawal attempts of ₹30 (3,000 paise)
    num_threads = 20
    withdraw_amount = 3000

    def run_withdrawal(thread_idx: int):
        idem_key = f"race-withdraw-{thread_idx}-{uuid.uuid4()}"
        for attempt in range(8):
            thread_db: Session = SessionLocal()
            try:
                res, is_replayed = post_movement(
                    db=thread_db,
                    user_id=holder.id,
                    idempotency_key=idem_key,
                    request_id=f"race-req-{thread_idx}",
                    kind="withdrawal",
                    source_account_id=acc.id,
                    destination_account_id=ext_acc.id,
                    amount=withdraw_amount,
                    raw_payload={"thread": thread_idx, "amount": withdraw_amount},
                    memo=f"Race withdrawal {thread_idx}",
                )
                return "SUCCESS"
            except InsufficientFundsError:
                return "REFUSED"
            except LockTimeoutError:
                time.sleep(0.15 * (attempt + 1))
            finally:
                thread_db.close()
        raise LockTimeoutError("Exhausted retries on race withdrawal.")

    results = fire_concurrent(num_threads, run_withdrawal, start_barrier=True)

    # 4. Analyze results
    success_count = sum(1 for _, res, exc in results if res == "SUCCESS")
    refusal_count = sum(1 for _, res, exc in results if res == "REFUSED")
    error_count = sum(1 for _, res, exc in results if exc is not None)

    assert error_count == 0, f"Unexpected exceptions encountered: {[exc for _, _, exc in results if exc]}"
    assert success_count == 3, f"Expected exactly 3 successes, got {success_count}"
    assert refusal_count == 17, f"Expected exactly 17 refusals, got {refusal_count}"

    # 5. Verify final database state
    db.refresh(acc)
    assert acc.balance == 1000, f"Expected final balance 1000 paise (₹10), got {acc.balance}"

    # Verify journal and refusal counts for this account
    withdrawal_journals = (
        db.query(Journal)
        .filter(Journal.kind == "withdrawal", Journal.idempotency_key.like("race-withdraw-%"))
        .count()
    )
    assert withdrawal_journals == 3

    recorded_refusals = (
        db.query(RefusedAttempt)
        .filter(RefusedAttempt.account_id == acc.id, RefusedAttempt.reason_code == "insufficient_funds")
        .count()
    )
    assert recorded_refusals == 17
