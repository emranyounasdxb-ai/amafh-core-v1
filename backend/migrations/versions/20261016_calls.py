"""Add the call-recording catalog.

Rollback is forward-only. These rows are reconstructible metadata. Original
recordings are not stored here and are not affected by this migration.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261016calls"
down_revision = "20261016mailclaim"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "call_recording_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_key", sa.String(40), nullable=False, unique=True),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("catalog_generation", sa.Integer(), nullable=False, server_default=sa.text("0")),
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
        sa.CheckConstraint("catalog_generation >= 0", name="ck_call_sources_generation"),
    )
    op.create_table(
        "call_recordings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("call_recording_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("catalog_generation", sa.Integer(), nullable=False),
        sa.Column("connector_id", sa.String(36), nullable=False),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("customer_number", sa.String(10), nullable=False),
        sa.Column("extension", sa.String(32), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("file_version", sa.Text(), nullable=False),
        sa.Column("availability", sa.String(20), nullable=False),
        sa.Column("source_sequence", sa.BigInteger(), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True)),
        sa.Column("synchronized_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("catalog_generation >= 0", name="ck_call_recordings_generation"),
        sa.CheckConstraint("month ~ '^[0-9]{4}-[0-9]{2}$'", name="ck_call_recordings_month"),
        sa.CheckConstraint(
            "customer_number ~ '^[0-9]{10}$'",
            name="ck_call_recordings_customer_number",
        ),
        sa.CheckConstraint(
            "availability IN ('ready', 'missing')",
            name="ck_call_recordings_availability",
        ),
        sa.UniqueConstraint(
            "source_id",
            "catalog_generation",
            "connector_id",
            name="uq_call_recordings_identity",
        ),
    )
    op.create_index(
        "ix_call_recordings_search",
        "call_recordings",
        ["source_id", "catalog_generation", "month", "customer_number", "filename", "id"],
        postgresql_where=sa.text("availability = 'ready'"),
    )
    op.create_table(
        "call_recording_sync_state",
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("call_recording_sources.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'idle'")),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("applied_sequence", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("published_epoch", sa.Text()),
        sa.Column("snapshot_epoch", sa.Text()),
        sa.Column("snapshot_generation", sa.Integer()),
        sa.Column("snapshot_cursor", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("snapshot_journal_max", sa.BigInteger()),
        sa.Column("phase", sa.String(20), nullable=False, server_default=sa.text("'indexing'")),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True)),
        sa.Column("last_synchronized_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(40)),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("status IN ('idle', 'leased')", name="ck_call_sync_status"),
        sa.CheckConstraint(
            "phase IN ('indexing', 'ready', 'offline', 'updating')",
            name="ck_call_sync_phase",
        ),
    )


def downgrade() -> None:
    raise RuntimeError("Call recording catalog metadata is forward-only.")
