"""
How this works / why it is safe:
This module is the SOLE WRITER of financial money movements in LedgerLine.
All deposits, withdrawals, transfers, adjustments, and reversals flow through
post_movement() inside a single database transaction under READ COMMITTED isolation.
It strictly executes the 6-phase algorithm from docs/ARCHITECTURE.md:
1. Claims the idempotency key (concurrent duplicates block on unique index, then replay).
2. Locks accounts deterministically (SELECT ... FOR UPDATE ORDER BY id) preventing deadlocks.
3. Authorizes caller against account_members post-lock (preventing race conditions).
4. Validates active status and balance floor (balance >= -overdraft_limit).
5. Refusals permanently record a refused_attempts row and commit 409 (refusals are records).
6. Success inserts a zero-sum journal and signed entries, updates balance cache, and commits 200.
Unexpected exceptions cleanly rollback the entire transaction including the key claim.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from psycopg.errors import LockNotAvailable, QueryCanceled
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    Account,
    AccountMember,
    IdempotencyKey,
    IdempotencyReplay,
    Journal,
    LedgerEntry,
    RefusedAttempt,
    SecurityEvent,
    User,
)
from app.errors import (
    AccountClosedError,
    AccountFrozenError,
    ForbiddenError,
    IdempotencyKeyReuseError,
    InsufficientFundsError,
    InvalidDestinationError,
    LockTimeoutError,
    NotFoundError,
    RefusalError,
    ValidationError,
)
from app.ledger.hashing import (
    compute_entry_hash,
    compute_refusal_hash,
    compute_request_hash,
)
from app.ledger.schemas import MovementResponse, PostingEntryResponse


def post_movement(
    db: Session,
    user_id: UUID,
    idempotency_key: str,
    request_id: str,
    kind: Literal["deposit", "withdrawal", "transfer", "adjustment", "reversal"],
    source_account_id: UUID,
    destination_account_id: UUID,
    amount: int,
    raw_payload: dict[str, Any],
    memo: str | None = None,
    reverses_journal_id: UUID | None = None,
) -> tuple[MovementResponse, bool]:
    """Execute atomic money movement or return an idempotent replay.

    Returns:
        (MovementResponse, is_replayed: bool)
    """
    if amount <= 0 or amount > settings.MAX_AMOUNT_PAISE:
        raise ValidationError(f"Amount must be between 1 and {settings.MAX_AMOUNT_PAISE} paise.")

    if source_account_id == destination_account_id:
        raise ValidationError("Source and destination accounts must be distinct.")

    req_hash = compute_request_hash(raw_payload)

    try:
        # Set strict per-transaction timeouts
        db.execute(text(f"SET LOCAL lock_timeout = '{settings.LOCK_TIMEOUT_MS}ms'"))
        db.execute(text(f"SET LOCAL statement_timeout = '{settings.STATEMENT_TIMEOUT_MS}ms'"))

        # Phase 1: Claim Idempotency Key
        claim_stmt = text(
            """
            INSERT INTO idempotency_keys (user_id, key, request_hash, created_at)
            VALUES (:user_id, :key, :request_hash, now())
            ON CONFLICT (user_id, key) DO NOTHING
            """
        )
        res = db.execute(
            claim_stmt,
            {"user_id": user_id, "key": idempotency_key, "request_hash": req_hash},
        )

        if res.rowcount == 0:
            # Key already exists: lock and inspect the existing key row
            existing_key = (
                db.query(IdempotencyKey)
                .filter(IdempotencyKey.user_id == user_id, IdempotencyKey.key == idempotency_key)
                .first()
            )

            if not existing_key:
                raise LockTimeoutError("Idempotency conflict under high concurrency.")

            same_payload = bytes(existing_key.request_hash) == req_hash

            # Record duplicate attempt
            replay_entry = IdempotencyReplay(
                user_id=user_id,
                key=idempotency_key,
                same_payload=same_payload,
                request_id=request_id,
            )
            db.add(replay_entry)
            db.commit()

            if not same_payload:
                raise IdempotencyKeyReuseError()

            if existing_key.response_status is None:
                raise LockTimeoutError("Original request still in progress. Please retry.")

            # If the original was a refusal, re-raise the recorded refusal
            if existing_key.response_status == 409:
                err_msg = existing_key.response_body.get("message", "Transaction refused.")
                raise RefusalError(message=err_msg, code=existing_key.response_body.get("code", "refused"))

            if existing_key.response_status != 200:
                raise ValidationError(message="Original request failed.")

            # Replay stored response
            stored = existing_key.response_body
            replayed_resp = MovementResponse(
                journal_id=UUID(stored["journal_id"]),
                kind=stored["kind"],
                amount=stored["amount"],
                status="posted",
                entry=PostingEntryResponse(
                    account_id=UUID(stored["entry"]["account_id"]),
                    account_seq=stored["entry"]["account_seq"],
                    amount=stored["entry"]["amount"],
                    balance_after=stored["entry"]["balance_after"],
                ),
                created_at=datetime.fromisoformat(stored["created_at"]),
            )
            return replayed_resp, True

        # Phase 2: Lock accounts deterministically (ORDER BY id)
        account_ids = sorted([source_account_id, destination_account_id])
        accounts = (
            db.query(Account)
            .filter(Account.id.in_(account_ids))
            .order_by(Account.id.asc())
            .with_for_update()
            .all()
        )

        acc_map = {acc.id: acc for acc in accounts}
        if source_account_id not in acc_map or destination_account_id not in acc_map:
            db.rollback()
            raise NotFoundError("One or more specified accounts were not found.")

        src_acc = acc_map[source_account_id]
        dest_acc = acc_map[destination_account_id]

        # Phase 3: Authorize caller inside transaction post-lock (Invariant I6)
        caller = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
        if not caller:
            db.rollback()
            raise NotFoundError("User not found.")

        if kind in ("adjustment", "reversal"):
            if caller.role != "admin":
                sec_event = SecurityEvent(
                    actor_user_id=user_id,
                    event="unauthorized_admin_action",
                    detail={"action": kind, "caller_role": caller.role},
                    request_id=request_id,
                )
                db.add(sec_event)
                db.commit()
                raise ForbiddenError("Only administrators may execute balance adjustments or reversals.")
        else:
            # Customer-initiated money movements
            if src_acc.kind == "customer":
                membership = (
                    db.query(AccountMember)
                    .filter(AccountMember.account_id == src_acc.id, AccountMember.user_id == user_id)
                    .first()
                )
                if not membership:
                    # Log security event and return 404 (never 403) to prevent enumeration
                    sec_event = SecurityEvent(
                        actor_user_id=user_id,
                        event="unauthorized_account_access",
                        detail={"account_id": str(src_acc.id), "action": kind},
                        request_id=request_id,
                    )
                    db.add(sec_event)
                    db.commit()
                    raise NotFoundError("Account not found.")

            if kind == "deposit" and dest_acc.kind == "customer":
                membership = (
                    db.query(AccountMember)
                    .filter(AccountMember.account_id == dest_acc.id, AccountMember.user_id == user_id)
                    .first()
                )
                if not membership:
                    raise NotFoundError("Account not found.")

        # Phase 4: Validate Account Status
        now = datetime.now(UTC)

        if src_acc.status == "frozen":
            _record_refusal_and_commit(
                db, user_id, idempotency_key, request_id, src_acc, dest_acc, amount, "account_frozen", now
            )
            raise AccountFrozenError()

        if src_acc.status == "closed":
            _record_refusal_and_commit(
                db, user_id, idempotency_key, request_id, src_acc, dest_acc, amount, "account_closed", now
            )
            raise AccountClosedError()

        if dest_acc.status in ("frozen", "closed"):
            # Uniform error so external callers cannot probe destination account status
            db.rollback()
            if kind == "deposit" and dest_acc.status == "frozen":
                raise InvalidDestinationError("The account is frozen by an administrator. Deposits are not permitted.")
            raise InvalidDestinationError()

        if src_acc.currency != "INR" or dest_acc.currency != "INR":
            db.rollback()
            raise ValidationError("All accounts must be denominated in INR.")

        # Phase 5: Balance Floor Check (balance >= -overdraft_limit)
        new_src_balance = src_acc.balance - amount
        if src_acc.kind == "customer" and new_src_balance < -src_acc.overdraft_limit:
            _record_refusal_and_commit(
                db, user_id, idempotency_key, request_id, src_acc, dest_acc, amount, "insufficient_funds", now
            )
            raise InsufficientFundsError()

        # Phase 6: Post Journal and Double-Entry Postings
        journal = Journal(
            id=uuid.uuid4(),
            kind=kind,
            initiated_by=user_id,
            idempotency_key=idempotency_key,
            request_id=request_id,
            memo=memo,
            reverses_journal_id=reverses_journal_id,
            created_at=now,
        )
        db.add(journal)
        db.flush()

        # Source entry (Debit)
        src_seq = src_acc.next_seq
        src_prev_hash = bytes(src_acc.last_hash)
        src_entry_hash = compute_entry_hash(
            src_prev_hash, src_acc.id, src_seq, journal.id, -amount, new_src_balance, now
        )

        src_entry = LedgerEntry(
            journal_id=journal.id,
            account_id=src_acc.id,
            account_seq=src_seq,
            amount=-amount,
            balance_after=new_src_balance,
            prev_hash=src_prev_hash,
            entry_hash=src_entry_hash,
            created_at=now,
        )
        db.add(src_entry)

        # Update source account cache & sequence
        src_acc.balance = new_src_balance
        src_acc.next_seq = src_seq + 1
        src_acc.last_hash = src_entry_hash

        # Destination entry (Credit)
        new_dest_balance = dest_acc.balance + amount
        dest_seq = dest_acc.next_seq
        dest_prev_hash = bytes(dest_acc.last_hash)
        dest_entry_hash = compute_entry_hash(
            dest_prev_hash, dest_acc.id, dest_seq, journal.id, amount, new_dest_balance, now
        )

        dest_entry = LedgerEntry(
            journal_id=journal.id,
            account_id=dest_acc.id,
            account_seq=dest_seq,
            amount=amount,
            balance_after=new_dest_balance,
            prev_hash=dest_prev_hash,
            entry_hash=dest_entry_hash,
            created_at=now,
        )
        db.add(dest_entry)

        # Update destination account cache & sequence
        dest_acc.balance = new_dest_balance
        dest_acc.next_seq = dest_seq + 1
        dest_acc.last_hash = dest_entry_hash

        # Caller sees only their own account's entry
        caller_entry = src_entry if src_acc.kind == "customer" else dest_entry
        response_data = MovementResponse(
            journal_id=journal.id,
            kind=kind,
            amount=amount,
            status="posted",
            entry=PostingEntryResponse(
                account_id=caller_entry.account_id,
                account_seq=caller_entry.account_seq,
                amount=caller_entry.amount,
                balance_after=caller_entry.balance_after,
            ),
            created_at=now,
        )

        # Store response in idempotency_keys
        idempotency_record = (
            db.query(IdempotencyKey)
            .filter(IdempotencyKey.user_id == user_id, IdempotencyKey.key == idempotency_key)
            .first()
        )
        if idempotency_record:
            idempotency_record.response_status = 200
            idempotency_record.response_body = {
                "journal_id": str(response_data.journal_id),
                "kind": response_data.kind,
                "amount": response_data.amount,
                "created_at": response_data.created_at.isoformat(),
                "entry": {
                    "account_id": str(response_data.entry.account_id),
                    "account_seq": response_data.entry.account_seq,
                    "amount": response_data.entry.amount,
                    "balance_after": response_data.entry.balance_after,
                },
            }

        db.commit()
        return response_data, False

    except (LockNotAvailable, QueryCanceled) as e:
        db.rollback()
        raise LockTimeoutError() from e
    except (DBAPIError, OperationalError) as e:
        db.rollback()
        # Detect PostgreSQL lock timeout (55P03) or statement timeout (57014)
        orig_err = getattr(e, "orig", None)
        sqlstate = getattr(orig_err, "sqlstate", None)
        if sqlstate in ("55P03", "57014") or isinstance(orig_err, (LockNotAvailable, QueryCanceled)):
            raise LockTimeoutError() from e
        raise
    except Exception:
        db.rollback()
        raise


def _record_refusal_and_commit(
    db: Session,
    user_id: UUID,
    idempotency_key: str,
    request_id: str,
    src_acc: Account,
    dest_acc: Account,
    amount: int,
    reason_code: str,
    now: datetime,
) -> None:
    """Commit an immutable refusal record into refused_attempts."""
    seq = src_acc.next_seq
    prev_hash = bytes(src_acc.last_hash)
    entry_hash = compute_refusal_hash(
        prev_hash, src_acc.id, seq, amount, src_acc.balance, reason_code, now
    )

    refusal = RefusedAttempt(
        account_id=src_acc.id,
        account_seq=seq,
        kind="refusal",
        counterparty_account_id=dest_acc.id,
        amount=amount,
        reason_code=reason_code,
        balance_at_attempt=src_acc.balance,
        initiated_by=user_id,
        idempotency_key=idempotency_key,
        request_id=request_id,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
        created_at=now,
    )
    db.add(refusal)

    # Sequence and hash chain must advance so refused attempts cannot be expunged
    src_acc.next_seq = seq + 1
    src_acc.last_hash = entry_hash

    # Save refusal response in idempotency_keys
    idempotency_record = (
        db.query(IdempotencyKey)
        .filter(IdempotencyKey.user_id == user_id, IdempotencyKey.key == idempotency_key)
        .first()
    )
    if idempotency_record:
        idempotency_record.response_status = 409
        idempotency_record.response_body = {
            "code": reason_code,
            "message": f"Transaction refused: {reason_code}.",
            "request_id": request_id,
        }

    db.commit()
