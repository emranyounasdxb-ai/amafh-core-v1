"""Effective-dated monthly sales Target versions."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from .base import created_at, metadata, pk

targets = Table(
    "targets",
    metadata,
    pk(),
    Column(
        "branch_id",
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "department_id",
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "designation_id",
        UUID(as_uuid=True),
        ForeignKey("designation_user_types.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("target_points", Integer),
    Column("target_amount_aed", Numeric(18, 0)),
    Column("effective_date", Date, nullable=False),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column("inactive_from_date", Date),
    Column(
        "superseded_by_target_id",
        UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="RESTRICT"),
    ),
    created_at(),
    UniqueConstraint("branch_id", "department_id", "designation_id", "effective_date"),
    ForeignKeyConstraint(
        ["department_id", "branch_id"],
        ["departments.id", "departments.branch_id"],
        name="fk_target_department_branch",
    ),
    CheckConstraint(
        "(target_points IS NOT NULL AND target_amount_aed IS NULL AND target_points > 0) "
        "OR (target_points IS NULL AND target_amount_aed IS NOT NULL AND target_amount_aed > 0)",
        name="ck_targets_one_typed_value",
    ),
    CheckConstraint(
        "(active AND inactive_from_date IS NULL AND superseded_by_target_id IS NULL) "
        "OR (NOT active AND inactive_from_date IS NOT NULL)",
        name="ck_targets_effective_state",
    ),
    Index(
        "uq_active_target",
        "branch_id",
        "department_id",
        "designation_id",
        unique=True,
        postgresql_where=text("active"),
    ),
)
