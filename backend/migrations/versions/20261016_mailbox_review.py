"""Mailbox generation, hide metadata and partial send status."""

import sqlalchemy as sa
from alembic import op

revision = "20261016mailreview"
down_revision = "20261016mailbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mailbox_connections",
        sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint(
        "ck_mailbox_connection_generation",
        "mailbox_connections",
        "generation > 0",
    )
    op.add_column(
        "mailbox_hidden_messages",
        sa.Column("subject", sa.String(998), nullable=False, server_default=""),
    )
    op.add_column(
        "mailbox_hidden_messages",
        sa.Column("sender", sa.String(998), nullable=False, server_default=""),
    )
    op.add_column(
        "mailbox_hidden_messages",
        sa.Column("recipients", sa.String(998), nullable=False, server_default=""),
    )
    op.add_column(
        "mailbox_hidden_messages",
        sa.Column("preview", sa.String(180), nullable=False, server_default=""),
    )
    op.add_column(
        "mailbox_hidden_messages",
        sa.Column("message_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "mailbox_hidden_messages",
        sa.Column("has_attachment", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.drop_constraint("ck_mailbox_send_status", "mailbox_send_attempts", type_="check")
    op.create_check_constraint(
        "ck_mailbox_send_status",
        "mailbox_send_attempts",
        "status IN ('pending', 'accepted', 'failed', 'unknown', 'accepted_unrecorded', 'partial')",
    )


def downgrade() -> None:
    raise RuntimeError("Forward-only migration; mailbox ownership records must be preserved")
