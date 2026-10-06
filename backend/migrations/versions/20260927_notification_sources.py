"""Retain source records for navigable in-app notifications.

Revision ID: 20260927noticesrc
Revises: 20260927casenotice
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260927noticesrc"
down_revision = "20260927casenotice"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("csv_import_batch_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column("notifications", sa.Column("employee_id", UUID(as_uuid=True), nullable=True))
    op.add_column("notifications", sa.Column("team_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_notification_csv_import_batch",
        "notifications",
        "csv_import_batches",
        ["csv_import_batch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_notification_employee",
        "notifications",
        "employees",
        ["employee_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_notification_team",
        "notifications",
        "teams",
        ["team_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_notification_csv_import_batch", "notifications", ["csv_import_batch_id"])
    op.create_index("ix_notification_employee", "notifications", ["employee_id"])
    op.create_index("ix_notification_team", "notifications", ["team_id"])
    op.drop_constraint("ck_notification_one_source", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_one_source",
        "notifications",
        "(target_id IS NOT NULL)::int + (case_id IS NOT NULL)::int + "
        "(task_id IS NOT NULL)::int + (csv_import_batch_id IS NOT NULL)::int + "
        "(employee_id IS NOT NULL)::int + (team_id IS NOT NULL)::int <= 1",
    )


def downgrade() -> None:
    raise RuntimeError("Notification source evidence is retained and cannot be downgraded")
