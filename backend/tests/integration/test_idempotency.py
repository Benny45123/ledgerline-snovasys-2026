"""
How this works / why it is safe:
This module tests Invariant I3 (Exactly-Once Semantics).
It proves that:
1. Replaying the identical key sequentially returns the stored result with is_replayed=True.
2. An entry is appended to idempotency_replays documenting the duplicate.
3. Reusing an idempotency key with an altered amount/payload is rejected with 422 idempotency_key_reuse.
4. Sending 10 concurrent requests with the identical key results in exactly 1 journal and 9 replays.
"""

import uuid
from sqlalchemy.orm import Session
from app.accounts.service import create_customer_account, get_system_account
from app.db.engine import SessionLocal
from app.db.models import IdempotencyReplay, Journal
from app.errors import IdempotencyKeyReuseError
from app.ledger.service import post_movement
from tests.helpers.concurrency import fire_concurrent


def test_sequential_idempotency_replay(db: Session, test_users):
    """Prove sequential replay returns stored response and records replay entry."""
    holder = test_users["holder1"]
    ext_acc = get_system_account(db, "external")
    acc = create_customer_account(db, "Idempotency Acc", holder.id, overdraft_limit=0)

    key = f"idem-seq-{uuid.uuid4()}"
    payload = {"amount": 5000}

    # Initial execution
    res1, is_replayed1 = post_movement(
        db=db,
        user_id=holder.id,
        idempotency_key=key,
        request_id=f"req-1-{uuid.uuid4()}",
        kind="deposit",
        source_account_id=ext_acc.id,
        destination_account_id=acc.id,
        amount=5000,
        raw_payload=payload,
    )
    assert is_replayed1 is False

    # Second execution with same key and payload
    res2, is_replayed2 = post_movement(
        db=db,
        user_id=holder.id,
        idempotency_key=key,
        request_id=f"req-2-{uuid.uuid4()}",
        kind="deposit",
        source_account_id=ext_acc.id,
        destination_account_id=acc.id,
        amount=5000,
        raw_payload=payload,
    )
    assert is_replayed2 is True
    assert res1.journal_id == res2.journal_id
    assert res1.amount == res2.amount
    assert res1.entry.balance_after == res2.entry.balance_after

    # Verify duplicate is logged in idempotency_replays
    replay_count = (
        db.query(IdempotencyReplay)
        .filter(IdempotencyReplay.user_id == holder.id, IdempotencyReplay.key == key)
        .count()
    )
    assert replay_count == 1


def test_idempotency_key_reuse_payload_mismatch(db: Session, test_users):
    """Prove that reusing a key with altered amount returns 422 idempotency_key_reuse."""
    holder = test_users["holder1"]
    ext_acc = get_system_account(db, "external")
    acc = create_customer_account(db, "Idempotency Mismatch Acc", holder.id, overdraft_limit=0)

    key = f"idem-mismatch-{uuid.uuid4()}"

    # Initial request: ₹50
    post_movement(
        db=db,
        user_id=holder.id,
        idempotency_key=key,
        request_id="req-mismatch-1",
        kind="deposit",
        source_account_id=ext_acc.id,
        destination_account_id=acc.id,
        amount=5000,
        raw_payload={"amount": 5000},
    )

    # Reused key with altered payload: ₹100
    try:
        post_movement(
            db=db,
            user_id=holder.id,
            idempotency_key=key,
            request_id="req-mismatch-2",
            kind="deposit",
            source_account_id=ext_acc.id,
            destination_account_id=acc.id,
            amount=10000,
            raw_payload={"amount": 10000},
        )
        assert False, "Expected IdempotencyKeyReuseError"
    except IdempotencyKeyReuseError:
        pass


def test_concurrent_idempotency_replays(db: Session, test_users):
    """Prove that 10 simultaneous requests with the identical key create exactly 1 journal."""
    holder = test_users["holder1"]
    ext_acc = get_system_account(db, "external")
    acc = create_customer_account(db, "Concurrent Idem Acc", holder.id, overdraft_limit=0)

    key = f"idem-concurrent-{uuid.uuid4()}"
    payload = {"amount": 2500}
    num_threads = 10

    def run_concurrent_call(thread_idx: int):
        thread_db: Session = SessionLocal()
        try:
            res, is_replayed = post_movement(
                db=thread_db,
                user_id=holder.id,
                idempotency_key=key,
                request_id=f"concurrent-req-{thread_idx}",
                kind="deposit",
                source_account_id=ext_acc.id,
                destination_account_id=acc.id,
                amount=2500,
                raw_payload=payload,
            )
            return is_replayed
        finally:
            thread_db.close()

    results = fire_concurrent(num_threads, run_concurrent_call, start_barrier=True)
    exceptions = [exc for _, _, exc in results if exc]
    assert len(exceptions) == 0, f"Exceptions in concurrent replay: {exceptions}"

    # Exactly one initial post (is_replayed == False) and 9 replays (is_replayed == True)
    initial_count = sum(1 for _, is_rep, _ in results if is_rep is False)
    replay_count = sum(1 for _, is_rep, _ in results if is_rep is True)

    assert initial_count == 1
    assert replay_count == 9

    # Only 1 journal created in database
    journals = db.query(Journal).filter(Journal.idempotency_key == key).count()
    assert journals == 1
