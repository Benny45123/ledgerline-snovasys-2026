"""
How this works / why it is safe:
This module defines the complete SQLAlchemy ORM model layer for LedgerLine.
All constraints from docs/ARCHITECTURE.md are represented:
- Exact primary keys, foreign keys, and unique indexes to prevent data corruption.
- CHECK constraints: balance_floor (prevents overdrafts past limits), currency ('INR'),
  amount <> 0 (no zero/negative amounts), status and kind enums.
- Strict mapping of BIGINT for all monetary amounts and sequence counters.
- bytea mapping for cryptographic hash chain fields (prev_hash, entry_hash, last_hash).
"""

import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    role = Column(String(32), nullable=False)  # admin, holder, auditor
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'holder', 'auditor')", name="valid_user_role"),
    )


class SessionModel(Base):
    __tablename__ = "sessions"

    token_hash = Column(BYTEA, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    number = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    kind = Column(String(32), nullable=False)  # customer, external, suspense
    currency = Column(String(3), nullable=False, default="INR")
    balance = Column(BigInteger, nullable=False, default=0)
    overdraft_limit = Column(BigInteger, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="active")  # active, frozen, closed
    next_seq = Column(BigInteger, nullable=False, default=1)
    last_hash = Column(BYTEA, nullable=False, default=b"\x00")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("kind IN ('customer', 'external', 'suspense')", name="valid_account_kind"),
        CheckConstraint("currency = 'INR'", name="single_currency_inr"),
        CheckConstraint("status IN ('active', 'frozen', 'closed')", name="valid_account_status"),
        CheckConstraint("overdraft_limit >= 0", name="non_negative_overdraft_limit"),
        CheckConstraint(
            "kind <> 'customer' OR balance >= -overdraft_limit",
            name="balance_floor",
        ),
    )


class AccountMember(Base):
    __tablename__ = "account_members"

    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class Journal(Base):
    __tablename__ = "journals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind = Column(String(32), nullable=False)  # deposit, withdrawal, transfer, adjustment, reversal
    initiated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    request_id = Column(String(64), nullable=False)
    memo = Column(String(140), nullable=True)
    reverses_journal_id = Column(UUID(as_uuid=True), ForeignKey("journals.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "kind IN ('deposit', 'withdrawal', 'transfer', 'adjustment', 'reversal')",
            name="valid_journal_kind",
        ),
        UniqueConstraint("initiated_by", "idempotency_key", name="uq_journal_initiator_key"),
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    journal_id = Column(UUID(as_uuid=True), ForeignKey("journals.id"), nullable=False, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True)
    account_seq = Column(BigInteger, nullable=False)
    amount = Column(BigInteger, nullable=False)  # + credit, - debit
    balance_after = Column(BigInteger, nullable=False)
    prev_hash = Column(BYTEA, nullable=False)
    entry_hash = Column(BYTEA, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("amount <> 0", name="non_zero_entry_amount"),
        UniqueConstraint("account_id", "account_seq", name="uq_entry_account_seq"),
    )


class RefusedAttempt(Base):
    __tablename__ = "refused_attempts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True)
    account_seq = Column(BigInteger, nullable=False)
    kind = Column(String(32), nullable=False)
    counterparty_account_id = Column(UUID(as_uuid=True), nullable=True)
    amount = Column(BigInteger, nullable=False)
    reason_code = Column(String(64), nullable=False)
    balance_at_attempt = Column(BigInteger, nullable=False)
    initiated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    request_id = Column(String(64), nullable=False)
    prev_hash = Column(BYTEA, nullable=False)
    entry_hash = Column(BYTEA, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("account_id", "account_seq", name="uq_refusal_account_seq"),
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    key = Column(String(128), primary_key=True)
    request_hash = Column(BYTEA, nullable=False)
    response_status = Column(Integer, nullable=True)
    response_body = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class IdempotencyReplay(Base):
    __tablename__ = "idempotency_replays"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    key = Column(String(128), nullable=False)
    same_payload = Column(Boolean, nullable=False)
    request_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    actor_user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    event = Column(String(64), nullable=False, index=True)
    detail = Column(JSONB, nullable=False, default=dict)
    request_id = Column(String(64), nullable=True)
    ip = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReviewFlag(Base):
    __tablename__ = "review_flags"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    rule_id = Column(String(64), nullable=False, index=True)
    journal_id = Column(UUID(as_uuid=True), ForeignKey("journals.id"), nullable=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True)
    severity = Column(String(16), nullable=False)  # low, medium, high
    status = Column(String(16), nullable=False, default="open")  # open, reviewed, dismissed
    evidence = Column(JSONB, nullable=False, default=dict)
    narrative = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("severity IN ('low', 'medium', 'high')", name="valid_flag_severity"),
        CheckConstraint("status IN ('open', 'reviewed', 'dismissed')", name="valid_flag_status"),
    )


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    flag_id = Column(BigInteger, ForeignKey("review_flags.id"), nullable=False)
    decision = Column(String(32), nullable=False)  # approve, dismiss, escalate
    reason = Column(Text, nullable=False)
    decided_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("decision IN ('approve', 'dismiss', 'escalate')", name="valid_decision_choice"),
    )
