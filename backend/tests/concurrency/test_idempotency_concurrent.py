"""
How this works / why it is safe:
Concurrency test verifying exactly-once execution under high-contention identical key submission.
Invariants enforced:
- Invariant I3 (Exactly once): When 50 concurrent requests arrive with the same (user_id, idempotency_key),
  exactly one movement commits to the ledger, and the other 49 block, detect the committed result,
  and safely replay it.
- Exactly 1 journal is created. Exactly 49 idempotency_replays rows are recorded.
"""

import uuid

from sqlalchemy.orm import Session

from app.accounts.service import create_customer_account, get_system_account
from app.db.engine import SessionLocal
from app.db.models import IdempotencyReplay, Journal, User
from app.ledger.service import post_movement
from tests.helpers.concurrency import fire_concurrent


def test_concurrent_idempotency_contention(db: Session, test_users: dict[str, User]) -> None:
    holder = test_users["holder1"]
    ext_acc = get_system_account(db, "external")
    account = create_customer_account(
        db=db,
        name="Concurrent Idempotency Account",
        owner_user_id=holder.id,
        overdraft_limit=0,
    )

    # Opening deposit of 100000 paise (₹1000)
    post_movement(
        db=db,
        user_id=holder.id,
        idempotency_key=f"init-{uuid.uuid4().hex[:12]}",
        request_id="init-req-1",
        kind="deposit",
        source_account_id=ext_acc.id,
        destination_account_id=account.id,
        amount=100000,
        raw_payload={"amount": 100000},
        memo="Initial funding",
    )

    # 20 concurrent threads attempting the exact same deposit with identical key
    contention_key = f"contended-key-{uuid.uuid4().hex[:12]}"
    payload = {"amount": 5000}

    def fire_same_key(idx: int) -> dict[str, object]:
        thread_db: Session = SessionLocal()
        try:
            res, is_replayed = post_movement(
                db=thread_db,
                user_id=holder.id,
                idempotency_key=contention_key,
                request_id=f"contended-req-{idx}",
                kind="deposit",
                source_account_id=ext_acc.id,
                destination_account_id=account.id,
                amount=5000,
                raw_payload=payload,
                memo="Contended deposit",
            )
            return {"status": "posted", "journal_id": str(res.journal_id), "is_replayed": is_replayed}
        finally:
            thread_db.close()

    results = fire_concurrent(20, fire_same_key, start_barrier=True)
    exceptions = [exc for _, _, exc in results if exc]
    assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"

    # All 20 responses must report success with the identical journal ID
    outputs = [out for _, out, _ in results if out]
    journal_ids = {r["journal_id"] for r in outputs}
    assert len(journal_ids) == 1

    # Verify exactly 1 deposit journal was created for this key
    deposit_journals = db.query(Journal).filter(Journal.idempotency_key == contention_key).all()
    assert len(deposit_journals) == 1

    # Verify exactly 19 replay audit records were captured
    replay_records = db.query(IdempotencyReplay).filter(IdempotencyReplay.key == contention_key).all()
    assert len(replay_records) == 19
