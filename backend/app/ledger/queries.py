"""
How this works / why it is safe:
This module contains strictly read-only queries (SELECT) for ledger statements and history.
It interleaves confirmed postings from ledger_entries and recorded refusals from refused_attempts
into a single chronologically ordered statement based on the account's sequence (account_seq).
Counterparty account numbers are masked to ****1234 to preserve user privacy. Keyset pagination
using account_seq prevents offset performance degradation and statement pagination drift.
"""

from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.models import Account, LedgerEntry, RefusedAttempt, User, Journal
from app.ledger.schemas import InitiatorInfo, StatementItem, StatementResponse
from app.errors import NotFoundError


def mask_account_number(number: str) -> str:
    """Mask account numbers to preserve privacy (e.g. ****1234)."""
    if len(number) <= 4:
        return "****"
    return f"****{number[-4:]}"


def get_account_statement(
    db: Session,
    account_id: UUID,
    after_seq: Optional[int] = None,
    limit: int = 50,
) -> StatementResponse:
    """Fetch interleaved statement items (postings + refusals) using keyset pagination."""
    limit = min(max(1, limit), 200)

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise NotFoundError("Account not found.")

    # Query postings and refusals unioned via raw SQL for efficiency and sequence ordering
    seq_filter = "AND e.account_seq > :after_seq" if after_seq is not None else ""

    stmt_sql = text(
        f"""
        (
            SELECT 
                'posting' AS item_type,
                e.account_seq,
                e.created_at AS at,
                j.kind,
                e.amount,
                e.balance_after,
                NULL::bigint AS balance_at_attempt,
                j.id AS journal_id,
                NULL::text AS reason_code,
                j.request_id,
                u.id AS user_id,
                u.email AS user_email,
                COALESCE(dest_acc.number, src_acc.number, 'EXTERNAL') AS counterparty_number,
                encode(e.prev_hash, 'hex') AS prev_hash,
                encode(e.entry_hash, 'hex') AS entry_hash
            FROM ledger_entries e
            JOIN journals j ON e.journal_id = j.id
            JOIN users u ON j.initiated_by = u.id
            LEFT JOIN ledger_entries other_e ON other_e.journal_id = j.id AND other_e.id <> e.id
            LEFT JOIN accounts dest_acc ON other_e.account_id = dest_acc.id AND e.amount < 0
            LEFT JOIN accounts src_acc ON other_e.account_id = src_acc.id AND e.amount > 0
            WHERE e.account_id = :account_id {seq_filter}
        )
        UNION ALL
        (
            SELECT 
                'refusal' AS item_type,
                r.account_seq,
                r.created_at AS at,
                r.kind,
                r.amount,
                NULL::bigint AS balance_after,
                r.balance_at_attempt,
                NULL::uuid AS journal_id,
                r.reason_code,
                r.request_id,
                u.id AS user_id,
                u.email AS user_email,
                COALESCE(c_acc.number, 'EXTERNAL') AS counterparty_number,
                encode(r.prev_hash, 'hex') AS prev_hash,
                encode(r.entry_hash, 'hex') AS entry_hash
            FROM refused_attempts r
            JOIN users u ON r.initiated_by = u.id
            LEFT JOIN accounts c_acc ON r.counterparty_account_id = c_acc.id
            WHERE r.account_id = :account_id {seq_filter}
        )
        ORDER BY account_seq ASC
        LIMIT :limit
        """
    )

    params = {"account_id": account_id, "limit": limit + 1}
    if after_seq is not None:
        params["after_seq"] = after_seq

    rows = db.execute(stmt_sql, params).fetchall()

    has_more = len(rows) > limit
    display_rows = rows[:limit]

    items: List[StatementItem] = []
    for row in display_rows:
        items.append(
            StatementItem(
                type=row.item_type,
                account_seq=row.account_seq,
                at=row.at,
                kind=row.kind,
                amount=row.amount,
                balance_after=row.balance_after,
                balance_at_attempt=row.balance_at_attempt,
                counterparty=mask_account_number(row.counterparty_number),
                initiated_by=InitiatorInfo(id=row.user_id, email=row.user_email),
                journal_id=row.journal_id,
                reason_code=row.reason_code,
                request_id=row.request_id,
                prev_hash=row.prev_hash,
                entry_hash=row.entry_hash,
            )
        )

    next_cursor = display_rows[-1].account_seq if (has_more and display_rows) else None

    return StatementResponse(
        account_id=account.id,
        currency=account.currency,
        current_balance=account.balance,
        overdraft_limit=account.overdraft_limit,
        status=account.status,
        items=items,
        has_more=has_more,
        next_after=next_cursor,
        next_cursor=next_cursor,
    )
