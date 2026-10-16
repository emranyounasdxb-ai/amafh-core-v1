"""Fence each mailbox sync claim and remember which bodies were opened.

Rollback is forward-only. The new columns are cache metadata. Dropping them
is unnecessary: a missing claim token cannot match a worker, and a missing
access time only changes which cached body is kept.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261016mailclaim"
down_revision = "20261016mailsync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mailbox_sync_jobs",
        sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "mailbox_sync_messages",
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    raise RuntimeError("Mailbox sync claim metadata is forward-only.")
