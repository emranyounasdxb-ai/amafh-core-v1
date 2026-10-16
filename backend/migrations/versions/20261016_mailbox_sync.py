"""Account-scoped mailbox synchronization cache.

The cache is reconstructible. Dropping these tables removes only synchronized
copies. Original provider mail, app-only hidden references, signatures and
send attempts stay. A mailbox generation change, disconnect, or account
disable cancels jobs and deletes that account's cache rows. Cached bodies are
sealed with AMAFH_MAILBOX_KEY_FILE and are useless without it. Restoring a
database backup restores the cache ciphertext; it does not restore a missing
key and it does not change the remote mailbox.

Rollback of this revision is forward-only. Leave the tables in place. They
hold no credentials and no original mail.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261016mailsync"
down_revision = "20261016mailreview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mailbox_sync_folders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("login_email", sa.String(254), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("folder_role", sa.String(20), nullable=False),
        sa.Column("folder_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("uid_validity", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("remote_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(40)),
        sa.Column("synced_at", sa.DateTime(timezone=True)),
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
        sa.UniqueConstraint(
            "account_id", "generation", "folder_role", name="uq_mailbox_sync_folder"
        ),
        sa.CheckConstraint(
            "folder_role IN ('inbox', 'drafts', 'sent', 'spam', 'archive')",
            name="ck_mailbox_sync_folder_role",
        ),
        sa.CheckConstraint(
            "status IN ('ready', 'failed', 'missing')",
            name="ck_mailbox_sync_folder_status",
        ),
        sa.CheckConstraint("generation > 0", name="ck_mailbox_sync_folder_generation"),
    )
    op.create_index(
        "ix_mailbox_sync_folder_account",
        "mailbox_sync_folders",
        ["account_id", "generation"],
    )
    op.create_table(
        "mailbox_sync_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("login_email", sa.String(254), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("folder_role", sa.String(20), nullable=False),
        sa.Column("uid_validity", sa.BigInteger(), nullable=False),
        sa.Column("uid", sa.BigInteger(), nullable=False),
        sa.Column("subject", sa.String(998), nullable=False, server_default=""),
        sa.Column("sender", sa.String(998), nullable=False, server_default=""),
        sa.Column("recipients", sa.String(998), nullable=False, server_default=""),
        sa.Column("preview", sa.String(180), nullable=False, server_default=""),
        sa.Column("message_date", sa.DateTime(timezone=True)),
        sa.Column("unread", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("has_attachment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("message_id", sa.String(998), nullable=False, server_default=""),
        sa.Column("cc", sa.String(998), nullable=False, server_default=""),
        sa.Column("bcc", sa.String(998), nullable=False, server_default=""),
        sa.Column("reply_to", sa.String(998), nullable=False, server_default=""),
        sa.Column("references_header", sa.String(998), nullable=False, server_default=""),
        sa.Column("body_sealed", sa.LargeBinary()),
        sa.Column("attachments_json", sa.Text()),
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
        sa.UniqueConstraint(
            "account_id",
            "generation",
            "folder_role",
            "uid_validity",
            "uid",
            name="uq_mailbox_sync_message",
        ),
        sa.CheckConstraint(
            "folder_role IN ('inbox', 'drafts', 'sent', 'spam', 'archive')",
            name="ck_mailbox_sync_message_role",
        ),
        sa.CheckConstraint(
            "generation > 0 AND uid_validity > 0 AND uid > 0",
            name="ck_mailbox_sync_message_uid",
        ),
        sa.CheckConstraint(
            "body_sealed IS NULL OR "
            "(octet_length(body_sealed) > 13 AND get_byte(body_sealed, 0) = 1)",
            name="ck_mailbox_sync_body_sealed",
        ),
        sa.CheckConstraint(
            "attachments_json IS NULL OR char_length(attachments_json) <= 8000",
            name="ck_mailbox_sync_attachments_json",
        ),
    )
    op.create_index(
        "ix_mailbox_sync_message_page",
        "mailbox_sync_messages",
        ["account_id", "generation", "folder_role", "uid_validity", "message_date", "uid"],
    )
    op.create_table(
        "mailbox_sync_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("login_email", sa.String(254), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("folder_role", sa.String(20), nullable=False, server_default=""),
        sa.Column("uid", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("uid_validity", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("priority_role", sa.String(20), nullable=False, server_default="inbox"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint("kind IN ('sync', 'seen')", name="ck_mailbox_sync_job_kind"),
        sa.CheckConstraint(
            "status IN ('pending', 'leased', 'done', 'failed', 'cancelled')",
            name="ck_mailbox_sync_job_status",
        ),
        sa.CheckConstraint(
            "generation > 0 AND attempts >= 0 AND uid >= 0",
            name="ck_mailbox_sync_job_bounds",
        ),
    )
    op.create_index("ix_mailbox_sync_job_due", "mailbox_sync_jobs", ["status", "next_run_at"])
    op.create_index(
        "uq_mailbox_sync_job_active",
        "mailbox_sync_jobs",
        ["account_id", "generation", "kind", "folder_role", "uid"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'leased')"),
    )


def downgrade() -> None:
    raise RuntimeError(
        "Forward-only migration; synchronized copies can be dropped later without mail loss"
    )
