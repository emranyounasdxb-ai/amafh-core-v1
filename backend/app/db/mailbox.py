"""Mailbox connection, signature and app-only message state.

Original messages stay on the mail server. These tables store encrypted
credentials, the personal signature, send-attempt identity and the references
needed to hide or restore a message inside AMAFH Core.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from .base import created_at, metadata, pk, updated_at

mailbox_connections = Table(
    "mailbox_connections",
    metadata,
    pk(),
    Column(
        "account_id",
        UUID(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("login_email", String(254), nullable=False),
    Column("secret", LargeBinary),
    Column("status", String(20), nullable=False),
    Column("generation", Integer, nullable=False, server_default="1"),
    created_at(),
    updated_at(),
    UniqueConstraint("account_id", name="uq_mailbox_connection_account"),
    CheckConstraint(
        "status IN ('connected', 'reconnect', 'disconnected')",
        name="ck_mailbox_connection_status",
    ),
    CheckConstraint("secret IS NULL OR octet_length(secret) > 13", name="ck_mailbox_secret_sealed"),
    CheckConstraint("generation > 0", name="ck_mailbox_connection_generation"),
)

mailbox_signatures = Table(
    "mailbox_signatures",
    metadata,
    Column(
        "account_id",
        UUID(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("body_html", Text, nullable=False),
    updated_at(),
    CheckConstraint("char_length(body_html) <= 8000", name="ck_mailbox_signature_length"),
)

mailbox_hidden_messages = Table(
    "mailbox_hidden_messages",
    metadata,
    pk(),
    Column(
        "account_id",
        UUID(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("login_email", String(254), nullable=False),
    Column("folder_role", String(20), nullable=False),
    Column("uid_validity", BigInteger, nullable=False),
    Column("uid", BigInteger, nullable=False),
    Column("hidden_at", DateTime(timezone=True), nullable=False),
    Column("subject", String(998), nullable=False, server_default=""),
    Column("sender", String(998), nullable=False, server_default=""),
    Column("recipients", String(998), nullable=False, server_default=""),
    Column("preview", String(180), nullable=False, server_default=""),
    Column("message_date", DateTime(timezone=True)),
    Column("has_attachment", Boolean, nullable=False, server_default="false"),
    UniqueConstraint(
        "account_id",
        "login_email",
        "folder_role",
        "uid_validity",
        "uid",
        name="uq_mailbox_hidden_ref",
    ),
    CheckConstraint(
        "folder_role IN ('inbox', 'drafts', 'sent', 'spam', 'archive')",
        name="ck_mailbox_hidden_folder",
    ),
    CheckConstraint("uid_validity > 0 AND uid > 0", name="ck_mailbox_hidden_uid"),
    Index("ix_mailbox_hidden_account", "account_id", "login_email"),
)

mailbox_send_attempts = Table(
    "mailbox_send_attempts",
    metadata,
    pk(),
    Column(
        "account_id",
        UUID(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("attempt_id", UUID(as_uuid=True), nullable=False),
    Column("login_email", String(254), nullable=False),
    Column("status", String(32), nullable=False),
    created_at(),
    updated_at(),
    UniqueConstraint("account_id", "attempt_id", name="uq_mailbox_send_attempt"),
    CheckConstraint(
        "status IN ('pending', 'accepted', 'failed', 'unknown', 'accepted_unrecorded', 'partial')",
        name="ck_mailbox_send_status",
    ),
)

mailbox_outgoing_files = Table(
    "mailbox_outgoing_files",
    metadata,
    pk(),
    Column(
        "account_id",
        UUID(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("stored_name", String(80), nullable=False),
    Column("filename", String(200), nullable=False),
    Column("content_type", String(120), nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    created_at(),
    UniqueConstraint("account_id", "stored_name", name="uq_mailbox_outgoing_name"),
    CheckConstraint("size_bytes > 0", name="ck_mailbox_outgoing_size"),
    Index("ix_mailbox_outgoing_expiry", "expires_at"),
)
