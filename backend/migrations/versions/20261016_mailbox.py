"""Own-mailbox connection, signature and app-only hide references."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261016mailbox"
down_revision = "20261010loginemail"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mailbox_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("login_email", sa.String(254), nullable=False),
        sa.Column("secret", sa.LargeBinary),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("account_id", name="uq_mailbox_connection_account"),
        sa.CheckConstraint(
            "status IN ('connected', 'reconnect', 'disconnected')",
            name="ck_mailbox_connection_status",
        ),
        sa.CheckConstraint(
            "secret IS NULL OR octet_length(secret) > 13",
            name="ck_mailbox_secret_sealed",
        ),
    )
    op.create_table(
        "mailbox_signatures",
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("body_html", sa.Text, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("char_length(body_html) <= 8000", name="ck_mailbox_signature_length"),
    )
    op.create_table(
        "mailbox_hidden_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("login_email", sa.String(254), nullable=False),
        sa.Column("folder_role", sa.String(20), nullable=False),
        sa.Column("uid_validity", sa.BigInteger, nullable=False),
        sa.Column("uid", sa.BigInteger, nullable=False),
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "account_id",
            "login_email",
            "folder_role",
            "uid_validity",
            "uid",
            name="uq_mailbox_hidden_ref",
        ),
        sa.CheckConstraint(
            "folder_role IN ('inbox', 'drafts', 'sent', 'spam', 'archive')",
            name="ck_mailbox_hidden_folder",
        ),
        sa.CheckConstraint("uid_validity > 0 AND uid > 0", name="ck_mailbox_hidden_uid"),
    )
    op.create_index(
        "ix_mailbox_hidden_account",
        "mailbox_hidden_messages",
        ["account_id", "login_email"],
    )
    op.create_table(
        "mailbox_send_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("login_email", sa.String(254), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("account_id", "attempt_id", name="uq_mailbox_send_attempt"),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'failed', 'unknown', 'accepted_unrecorded')",
            name="ck_mailbox_send_status",
        ),
    )
    op.create_table(
        "mailbox_outgoing_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stored_name", sa.String(80), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("account_id", "stored_name", name="uq_mailbox_outgoing_name"),
        sa.CheckConstraint("size_bytes > 0", name="ck_mailbox_outgoing_size"),
    )
    op.create_index("ix_mailbox_outgoing_expiry", "mailbox_outgoing_files", ["expires_at"])


def downgrade() -> None:
    raise RuntimeError("Forward-only migration; mailbox ownership records must be preserved")
