"""Initial Schema for LedgerLine

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-06

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext;")

    # 1. Users
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("role IN ('admin', 'holder', 'auditor')", name="valid_user_role"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # 2. Sessions
    op.create_table(
        "sessions",
        sa.Column("token_hash", BYTEA, primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    # 3. Accounts
    op.create_table(
        "accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("number", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("overdraft_limit", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("next_seq", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("last_hash", BYTEA, nullable=False, server_default=sa.text(r"'\x00'::bytea")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("kind IN ('customer', 'external', 'suspense')", name="valid_account_kind"),
        sa.CheckConstraint("currency = 'INR'", name="single_currency_inr"),
        sa.CheckConstraint("status IN ('active', 'frozen', 'closed')", name="valid_account_status"),
        sa.CheckConstraint("overdraft_limit >= 0", name="non_negative_overdraft_limit"),
        sa.CheckConstraint("kind <> 'customer' OR balance >= -overdraft_limit", name="balance_floor"),
    )
    op.create_index("ix_accounts_number", "accounts", ["number"])

    # 4. Account Members
    op.create_table(
        "account_members",
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    )

    # 5. Journals
    op.create_table(
        "journals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("initiated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("memo", sa.String(140), nullable=True),
        sa.Column("reverses_journal_id", UUID(as_uuid=True), sa.ForeignKey("journals.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "kind IN ('deposit', 'withdrawal', 'transfer', 'adjustment', 'reversal')",
            name="valid_journal_kind",
        ),
        sa.UniqueConstraint("initiated_by", "idempotency_key", name="uq_journal_initiator_key"),
    )

    # 6. Ledger Entries
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("journal_id", UUID(as_uuid=True), sa.ForeignKey("journals.id"), nullable=False),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("account_seq", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column("prev_hash", BYTEA, nullable=False),
        sa.Column("entry_hash", BYTEA, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("amount <> 0", name="non_zero_entry_amount"),
        sa.UniqueConstraint("account_id", "account_seq", name="uq_entry_account_seq"),
    )
    op.create_index("ix_ledger_entries_journal_id", "ledger_entries", ["journal_id"])
    op.create_index("ix_ledger_entries_account_id", "ledger_entries", ["account_id"])

    # 7. Refused Attempts
    op.create_table(
        "refused_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("account_seq", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("counterparty_account_id", UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("balance_at_attempt", sa.BigInteger(), nullable=False),
        sa.Column("initiated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("prev_hash", BYTEA, nullable=False),
        sa.Column("entry_hash", BYTEA, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("account_id", "account_seq", name="uq_refusal_account_seq"),
    )
    op.create_index("ix_refused_attempts_account_id", "refused_attempts", ["account_id"])

    # 8. Idempotency Keys
    op.create_table(
        "idempotency_keys",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("request_hash", BYTEA, nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 9. Idempotency Replays
    op.create_table(
        "idempotency_replays",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("same_payload", sa.Boolean(), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_idempotency_replays_user_id", "idempotency_replays", ["user_id"])

    # 10. Security Events
    op.create_table(
        "security_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("detail", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_security_events_actor", "security_events", ["actor_user_id"])
    op.create_index("ix_security_events_event", "security_events", ["event"])

    # 11. Review Flags
    op.create_table(
        "review_flags",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("journal_id", UUID(as_uuid=True), sa.ForeignKey("journals.id"), nullable=True),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("evidence", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("severity IN ('low', 'medium', 'high')", name="valid_flag_severity"),
        sa.CheckConstraint("status IN ('open', 'reviewed', 'dismissed')", name="valid_flag_status"),
    )
    op.create_index("ix_review_flags_rule", "review_flags", ["rule_id"])

    # 12. Review Decisions
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("flag_id", sa.BigInteger(), sa.ForeignKey("review_flags.id"), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decided_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("decision IN ('approve', 'dismiss', 'escalate')", name="valid_decision_choice"),
    )


def downgrade() -> None:
    op.drop_table("review_decisions")
    op.drop_table("review_flags")
    op.drop_table("security_events")
    op.drop_table("idempotency_replays")
    op.drop_table("idempotency_keys")
    op.drop_table("refused_attempts")
    op.drop_table("ledger_entries")
    op.drop_table("journals")
    op.drop_table("account_members")
    op.drop_table("accounts")
    op.drop_table("sessions")
    op.drop_table("users")
