"""Add account_requests table for user onboarding and admin approval

Revision ID: 0004_account_requests
Revises: 0003_unique_reversal_journal
Create Date: 2026-11-10

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_account_requests"
down_revision: str | None = "0003_unique_reversal_journal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS account_requests (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            account_name VARCHAR(128) NOT NULL,
            purpose TEXT,
            currency VARCHAR(3) NOT NULL DEFAULT 'INR',
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
            reviewed_at TIMESTAMPTZ,
            rejection_reason TEXT,
            account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT valid_account_request_status CHECK (status IN ('pending', 'approved', 'rejected')),
            CONSTRAINT single_currency_account_request CHECK (currency = 'INR')
        );

        CREATE INDEX IF NOT EXISTS ix_account_requests_user_id ON account_requests(user_id);
        CREATE INDEX IF NOT EXISTS ix_account_requests_status ON account_requests(status);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS account_requests CASCADE;")
