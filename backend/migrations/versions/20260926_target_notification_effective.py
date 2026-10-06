"""Dispatch Target notices from effective-date facts, retaining legacy rows.

Revision ID: 20260926targetnotice
Revises: 20260926phase4
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260926targetnotice"
down_revision = "20260926phase4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("target_id", UUID(as_uuid=True)))
    op.add_column("notifications", sa.Column("suppressed_at", sa.DateTime(timezone=True)))
    op.create_foreign_key(
        "fk_notification_target",
        "notifications",
        "targets",
        ["target_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_target_notification_recipient",
        "notifications",
        ["target_id", "recipient_employee_id"],
        unique=True,
        postgresql_where=sa.text("target_id IS NOT NULL"),
    )
    op.execute(
        "UPDATE notifications SET suppressed_at = now() "
        "WHERE kind = 'target.effective' AND target_id IS NULL"
    )


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
