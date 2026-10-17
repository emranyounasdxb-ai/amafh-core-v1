"""Call-recording catalog. Audio bytes stay on the Windows source."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from .base import created_at, metadata, pk, updated_at

call_recording_sources = Table(
    "call_recording_sources",
    metadata,
    pk(),
    Column("source_key", String(40), nullable=False, unique=True),
    Column("display_name", String(80), nullable=False),
    Column("enabled", Boolean, nullable=False, server_default=text("false")),
    Column("catalog_generation", Integer, nullable=False, server_default=text("0")),
    created_at(),
    updated_at(),
    CheckConstraint("catalog_generation >= 0", name="ck_call_sources_generation"),
)

call_recordings = Table(
    "call_recordings",
    metadata,
    pk(),
    Column(
        "source_id",
        UUID(as_uuid=True),
        ForeignKey("call_recording_sources.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("catalog_generation", Integer, nullable=False),
    Column("connector_id", String(36), nullable=False),
    Column("month", String(7), nullable=False),
    Column("customer_number", String(32), nullable=False),
    Column("extension", String(32), nullable=False),
    Column("filename", String(255), nullable=False),
    Column("byte_size", BigInteger, nullable=False),
    Column("file_version", Text, nullable=False),
    Column("availability", String(20), nullable=False),
    Column("source_sequence", BigInteger, nullable=False),
    Column("indexed_at", DateTime(timezone=True)),
    Column("synchronized_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "source_id",
        "catalog_generation",
        "connector_id",
        name="uq_call_recordings_identity",
    ),
    CheckConstraint("catalog_generation >= 0", name="ck_call_recordings_generation"),
    CheckConstraint("month ~ '^[0-9]{4}-[0-9]{2}$'", name="ck_call_recordings_month"),
    CheckConstraint(
        "customer_number ~ '^[0-9]{1,32}$'",
        name="ck_call_recordings_customer_number",
    ),
    CheckConstraint(
        "availability IN ('ready', 'missing')",
        name="ck_call_recordings_availability",
    ),
    Index(
        "ix_call_recordings_first_number_search",
        "source_id",
        "catalog_generation",
        "month",
        "extension",
        "filename",
        "id",
        postgresql_where=text("availability = 'ready'"),
    ),
    Index(
        "ix_call_recordings_search",
        "source_id",
        "catalog_generation",
        "month",
        "customer_number",
        "filename",
        "id",
        postgresql_where=text("availability = 'ready'"),
    ),
)

call_recording_sync_state = Table(
    "call_recording_sync_state",
    metadata,
    Column(
        "source_id",
        UUID(as_uuid=True),
        ForeignKey("call_recording_sources.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("status", String(20), nullable=False, server_default=text("'idle'")),
    Column("claim_token", UUID(as_uuid=True)),
    Column("lease_until", DateTime(timezone=True)),
    Column("applied_sequence", BigInteger, nullable=False, server_default=text("0")),
    Column("published_epoch", Text),
    Column("snapshot_epoch", Text),
    Column("snapshot_generation", Integer),
    Column("snapshot_cursor", Text, nullable=False, server_default=text("''")),
    Column("snapshot_journal_max", BigInteger),
    Column("phase", String(20), nullable=False, server_default=text("'indexing'")),
    Column("last_indexed_at", DateTime(timezone=True)),
    Column("last_synchronized_at", DateTime(timezone=True)),
    Column("heartbeat_at", DateTime(timezone=True)),
    Column("error_code", String(40)),
    Column("error_count", Integer, nullable=False, server_default=text("0")),
    updated_at(),
    CheckConstraint(
        "status IN ('idle', 'leased')",
        name="ck_call_sync_status",
    ),
    CheckConstraint(
        "phase IN ('indexing', 'ready', 'offline', 'updating')",
        name="ck_call_sync_phase",
    ),
)
