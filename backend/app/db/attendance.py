"""Versioned branch timings and retained attendance import facts."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from .base import created_at, metadata, pk

csv_import_batches = Table(
    "csv_import_batches",
    metadata,
    pk(),
    Column("kind", String(30), nullable=False),
    Column(
        "uploaded_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("branch_id", UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT")),
    Column("attendance_date", Date),
    Column("status", String(30), nullable=False),
    Column("content_hash", String(64)),
    Column("byte_size", BigInteger),
    Column("data_row_count", Integer),
    Column("applied_count", Integer),
    Column("error_count", Integer),
    Column("file_name", String(255)),
    Column("validation_status", String(30)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index(
        "uq_csv_import_content",
        "kind",
        "uploaded_by_employee_id",
        "content_hash",
        unique=True,
        postgresql_where=text(
            "kind NOT IN ('bank_stage','attendance') AND content_hash IS NOT NULL"
        ),
    ),
    Index(
        "uq_bank_stage_import_content_global",
        "kind",
        "content_hash",
        unique=True,
        postgresql_where=text(
            "kind = 'bank_stage' AND status = 'Applied' AND content_hash IS NOT NULL"
        ),
    ),
    Index(
        "uq_attendance_applied_branch_date",
        "branch_id",
        "attendance_date",
        unique=True,
        postgresql_where=text("kind = 'attendance' AND status = 'Applied'"),
    ),
    CheckConstraint(
        "kind <> 'attendance' OR branch_id IS NULL OR (byte_size IS NOT NULL "
        "AND data_row_count IS NOT NULL AND applied_count IS NOT NULL "
        "AND error_count IS NOT NULL)",
        name="ck_attendance_batch_evidence",
    ),
)

csv_import_row_results = Table(
    "csv_import_row_results",
    metadata,
    pk(),
    Column(
        "batch_id",
        UUID(as_uuid=True),
        ForeignKey("csv_import_batches.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("row_number", Integer, nullable=False),
    Column("status", String(30), nullable=False),
    Column("error_code", String(100)),
    Column("error_detail", Text),
    Column("column_name", String(80)),
    Column("case_id", UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT")),
    Column("internal_case_id", String(80)),
    Column("bank_case_number", String(120)),
    Column("product_label", String(150)),
    Column("current_stage", String(150)),
    Column("requested_stage", String(150)),
    Column("remark", Text),
    UniqueConstraint("batch_id", "row_number"),
)

office_timings = Table(
    "office_timings",
    metadata,
    pk(),
    Column(
        "branch_id",
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("effective_date", Date, nullable=False),
    Column("start_time", Time, nullable=False),
    Column("end_time", Time, nullable=False),
    Column(
        "created_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
    ),
    created_at(),
    UniqueConstraint("branch_id", "effective_date"),
    CheckConstraint("end_time > start_time", name="ck_office_timing_order"),
)

attendance_records = Table(
    "attendance_records",
    metadata,
    pk(),
    Column(
        "employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "branch_id",
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("attendance_date", Date, nullable=False),
    Column("check_in_time", Time),
    Column("check_out_time", Time),
    Column("status", String(30), nullable=False),
    Column("is_late", Boolean, nullable=False, server_default="false"),
    Column(
        "office_timing_id", UUID(as_uuid=True), ForeignKey("office_timings.id", ondelete="RESTRICT")
    ),
    Column(
        "csv_import_batch_id",
        UUID(as_uuid=True),
        ForeignKey("csv_import_batches.id", ondelete="RESTRICT"),
    ),
    created_at(),
    UniqueConstraint("employee_id", "attendance_date"),
    CheckConstraint(
        "office_timing_id IS NULL OR (status = 'Present' AND check_in_time IS NOT NULL "
        "AND check_out_time IS NOT NULL "
        "AND check_out_time > check_in_time) OR (status = 'Absent' AND check_in_time IS NULL "
        "AND check_out_time IS NULL AND NOT is_late)",
        name="ck_attendance_record_values",
    ),
    Index("ix_attendance_branch_date", "branch_id", "attendance_date"),
)
