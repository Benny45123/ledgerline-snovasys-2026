"""Add partial unique index on journals reverses_journal_id

Revision ID: 0003_unique_reversal_journal
Revises: 0002_triggers_and_roles
Create Date: 2026-11-09

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_unique_reversal_journal"
down_revision: str | None = "0002_triggers_and_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Partial unique index ensuring each original journal can be reversed at most once
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_journals_reverses_journal_id
        ON journals (reverses_journal_id)
        WHERE reverses_journal_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_journals_reverses_journal_id;")
