"""Database Triggers and Security Roles for LedgerLine

Revision ID: 0002_triggers_and_roles
Revises: 0001_initial_schema
Create Date: 2026-11-06

"""
from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_triggers_and_roles"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Append-Only Trigger Function
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Table % is append-only. UPDATE, DELETE, and TRUNCATE are prohibited.', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # Attach append-only triggers to immutable tables
    append_only_tables = [
        "journals",
        "ledger_entries",
        "refused_attempts",
        "idempotency_replays",
        "security_events",
        "review_flags",
        "review_decisions",
    ]

    for table in append_only_tables:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_append_only_rows
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

            CREATE TRIGGER trg_{table}_append_only_truncate
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION forbid_mutation();
            """
        )

    # 2. Zero-Sum Constraint Trigger (Checked at COMMIT)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_journal_zero_sum() RETURNS trigger AS $$
        DECLARE
            net_sum bigint;
        BEGIN
            SELECT COALESCE(SUM(amount), 0) INTO net_sum
            FROM ledger_entries
            WHERE journal_id = NEW.journal_id;

            IF net_sum <> 0 THEN
                RAISE EXCEPTION 'Double-entry violation: Journal % does not sum to zero (net sum: %).', NEW.journal_id, net_sum;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE CONSTRAINT TRIGGER journal_sums_to_zero
        AFTER INSERT ON ledger_entries
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION check_journal_zero_sum();
        """
    )

    # 3. Balance Cache Integrity Trigger at COMMIT
    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_account_balance_cache() RETURNS trigger AS $$
        DECLARE
            actual_balance bigint;
            cached_balance bigint;
        BEGIN
            SELECT balance_after INTO actual_balance
            FROM ledger_entries
            WHERE account_id = NEW.account_id
            ORDER BY account_seq DESC
            LIMIT 1;

            SELECT balance INTO cached_balance
            FROM accounts
            WHERE id = NEW.account_id;

            IF actual_balance IS NOT NULL AND actual_balance <> cached_balance THEN
                RAISE EXCEPTION 'Cache integrity violation: Account % cached balance (%) != latest ledger balance_after (%).',
                    NEW.account_id, cached_balance, actual_balance;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE CONSTRAINT TRIGGER account_balance_matches_ledger
        AFTER INSERT ON ledger_entries
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION check_account_balance_cache();
        """
    )

    # 4. Optional Role & Privilege Grants (conditioned for cloud Postgres compatibility)
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ledgerline_app') THEN
                REVOKE ALL ON ALL TABLES IN SCHEMA public FROM ledgerline_app;
                GRANT SELECT, INSERT ON journals, ledger_entries, refused_attempts, idempotency_replays,
                      security_events, review_flags, review_decisions TO ledgerline_app;
                GRANT SELECT, INSERT, UPDATE ON accounts, idempotency_keys, sessions TO ledgerline_app;
                GRANT SELECT, INSERT, UPDATE ON users TO ledgerline_app;
                GRANT SELECT, INSERT ON account_members TO ledgerline_app;
                GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO ledgerline_app;
            END IF;
        END;
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS account_balance_matches_ledger ON ledger_entries;")
    op.execute("DROP FUNCTION IF EXISTS check_account_balance_cache();")
    op.execute("DROP TRIGGER IF EXISTS journal_sums_to_zero ON ledger_entries;")
    op.execute("DROP FUNCTION IF EXISTS check_journal_zero_sum();")

    append_only_tables = [
        "journals",
        "ledger_entries",
        "refused_attempts",
        "idempotency_replays",
        "security_events",
        "review_flags",
        "review_decisions",
    ]

    for table in append_only_tables:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only_rows ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only_truncate ON {table};")

    op.execute("DROP FUNCTION IF EXISTS forbid_mutation();")
