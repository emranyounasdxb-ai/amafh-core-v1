"""Immutable completed-Case financial result schema."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import UUID

from .base import created_at, metadata, pk

case_financial_results = Table(
    "case_financial_results",
    metadata,
    pk(),
    Column(
        "case_id",
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    ),
    Column(
        "financial_rule_id",
        UUID(as_uuid=True),
        ForeignKey("financial_rules.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "credited_owner_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("product_code", String(2), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=False),
    Column("cc_points", Integer),
    Column("commission_aed", Numeric(18, 0)),
    Column("pf_amount_aed", Numeric(18, 0)),
    Column("rule_effective_date", Date, nullable=False),
    created_at(),
    CheckConstraint("product_code IN ('CC','PF')"),
    CheckConstraint("cc_points IS NULL OR cc_points > 0"),
    Index("ix_case_financial_results_owner_time", "credited_owner_employee_id", "completed_at"),
)
