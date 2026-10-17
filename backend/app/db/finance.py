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
    Column("pf_commission_per_1000", Numeric(18, 0)),
    Column("pf_amount_basis", String(32)),
    Column("rule_effective_date", Date, nullable=False),
    created_at(),
    CheckConstraint("product_code IN ('CC','PF')"),
    CheckConstraint("cc_points IS NULL OR cc_points > 0"),
    CheckConstraint(
        "(pf_amount_basis IS NULL AND pf_commission_per_1000 IS NULL) OR "
        "(pf_amount_basis IS NOT NULL AND pf_amount_basis = 'final_approved_disbursed' "
        "AND product_code = 'PF' "
        "AND cc_points IS NULL AND pf_amount_aed IS NOT NULL AND pf_amount_aed > 0 "
        "AND pf_commission_per_1000 IS NOT NULL AND pf_commission_per_1000 >= 0 "
        "AND commission_aed IS NOT NULL "
        "AND commission_aed = round(pf_amount_aed * pf_commission_per_1000 / 1000))",
        name="ck_financial_result_pf_rate",
    ),
    Index("ix_case_financial_results_owner_time", "credited_owner_employee_id", "completed_at"),
)
