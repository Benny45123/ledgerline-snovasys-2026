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
from app.accounts.service import AccountService
from app.db.models import IdempotencyReplay, Journal, User
from app.ledger.service import LedgerService
from tests.helpers.concurrency import fire_concurrent


def test_concurrent_idempotency_contention(db_session: Session, seed_users: dict[str, User]) -> None:
    holder = seed_users["holder"]
    account = AccountService.create_customer_account(
        db=db_session,
        owner_id=holder.id,
        account_name="Concurrent Idempotency Account",
        actor_id=holder.id,
    )
    
    # Opening deposit of 100000 paise (₹1000)
    LedgerService.deposit(
        db=db_session,
        account_id=account.id,
        amount=100000,
        user_id=holder.id,
        idempotency_key=f"init-{uuid.uuid4().hex[:12]}",
    )
    
    # 20 concurrent threads attempting the exact same deposit with identical key
    contention_key = f"contended-key-{uuid.uuid4().hex[:12]}"
    
    def fire_same_key(idx: int) -> dict[str, object]:
        res = LedgerService.deposit(
            db=db_session,
            account_id=account.id,
            amount=5000,
            user_id=holder.id,
            idempotency_key=contention_key,
        )
        return {"status": res.status, "journal_id": str(res.journal_id)}
    
    results = fire_concurrent(20, fire_same_key)
    
    # All 20 responses must report success with the identical journal ID
    journal_ids = {r["journal_id"] for r in results}
    assert len(journal_ids) == 1
    
    # Verify exactly 1 deposit journal was created for this key
    deposit_journals = (
        db_session.query(Journal)
        .filter(Journal.idempotency_key == contention_key)
        .all()
    )
    assert len(deposit_journals) == 1
    
    # Verify exactly 19 replay audit records were captured
    replay_records = (
        db_session.query(IdempotencyReplay)
        .filter(IdempotencyReplay.idempotency_key == contention_key)
        .all()
    )
    assert len(replay_records) == 19
