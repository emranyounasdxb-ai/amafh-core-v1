"""Phase 4 holiday calendar and immutable ranking confirmation facts."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from .base import created_at, metadata, pk

uae_public_holidays = Table(
    "uae_public_holidays",
    metadata,
    pk(),
    Column("holiday_date", Date, nullable=False, unique=True),
    Column("applicable_year", Integer, nullable=False),
    Column("name", String(200), nullable=False),
    Column("source_reference", Text, nullable=False),
    Column(
        "created_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    created_at(),
    CheckConstraint("applicable_year = EXTRACT(YEAR FROM holiday_date)"),
    CheckConstraint("length(btrim(name)) > 0 AND length(btrim(source_reference)) > 0"),
)

uae_holiday_year_certifications = Table(
    "uae_holiday_year_certifications",
    metadata,
    pk(),
    Column("applicable_year", Integer, nullable=False, unique=True),
    Column("source_reference", Text, nullable=False),
    Column(
        "certified_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    created_at(),
    CheckConstraint("applicable_year BETWEEN 1900 AND 9999"),
    CheckConstraint("length(btrim(source_reference)) > 0"),
)

ranking_confirmations = Table(
    "ranking_confirmations",
    metadata,
    pk(),
    Column("context_key", String(64), nullable=False, unique=True),
    Column("period_start", Date, nullable=False),
    Column("period_end", Date, nullable=False),
    Column("branch_id", UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT")),
    Column("department_id", UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT")),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT")),
    Column(
        "designation_id",
        UUID(as_uuid=True),
        ForeignKey("designation_user_types.id", ondelete="RESTRICT"),
    ),
    Column("product_code", String(2), nullable=False),
    Column("eligible_candidate_ids", Text, nullable=False),
    Column(
        "selected_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "confirmed_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("confirmed_at", DateTime(timezone=True), nullable=False),
    created_at(),
    CheckConstraint("period_start <= period_end"),
    CheckConstraint("product_code IN ('CC','PF')"),
)
