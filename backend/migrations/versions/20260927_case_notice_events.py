"""Retain idempotent Case reminder and delayed-stage dispatch evidence.

Revision ID: 20260927casenotice
Revises: 20260926p6task
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260927casenotice"
down_revision = "20260926p6task"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_notice_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("cycle_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval_index", sa.Integer(), nullable=False),
        sa.Column(
            "recipient_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "notification_id",
            UUID(as_uuid=True),
            sa.ForeignKey("notifications.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "case_id",
            "kind",
            "cycle_started_at",
            "interval_index",
            "recipient_employee_id",
            name="uq_case_notice_interval_recipient",
        ),
        sa.CheckConstraint(
            "kind IN ('pending_approval','stage_delayed')", name="ck_case_notice_kind"
        ),
        sa.CheckConstraint("interval_index >= 1", name="ck_case_notice_interval"),
    )
    op.execute(
        "CREATE TRIGGER guard_case_notice_event BEFORE UPDATE OR DELETE "
        "ON case_notice_events FOR EACH ROW "
        "EXECUTE FUNCTION amafh_reject_immutable_change()"
    )


def downgrade() -> None:
    raise RuntimeError("Case notice evidence is retained and cannot be downgraded")
