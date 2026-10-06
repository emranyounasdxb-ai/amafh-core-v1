"""Branch inventory and retained issue, maintenance, and status history."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Computed,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from .base import created_at, metadata, pk, updated_at

assets = Table(
    "assets",
    metadata,
    pk(),
    Column("asset_code", String(80), nullable=False, unique=True),
    Column(
        "branch_id",
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("category", String(80), nullable=False),
    Column("brand", String(150), nullable=False),
    Column("model", String(150), nullable=False),
    Column("serial_number", String(150), nullable=False, unique=True),
    Column("mobile_number", String(40)),
    Column("operator_provider", String(150)),
    Column("status", String(30), nullable=False),
    Column(
        "created_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
    ),
    created_at(),
    updated_at(),
    CheckConstraint(
        "created_by_employee_id IS NULL OR "
        "category IN ('Mobile Phone','SIM Card','PC','Laptop','Other')",
        name="ck_asset_category",
    ),
    CheckConstraint(
        "created_by_employee_id IS NULL OR "
        "status IN ('Available','Issued','Needs Maintenance','Maintenance','Damaged')",
        name="ck_asset_status",
    ),
    CheckConstraint(
        "created_by_employee_id IS NULL OR (length(btrim(asset_code)) > 0 "
        "AND length(btrim(brand)) > 0 AND length(btrim(model)) > 0 "
        "AND length(btrim(serial_number)) > 0)",
        name="ck_asset_required_text",
    ),
    CheckConstraint(
        "created_by_employee_id IS NULL OR ((category = 'SIM Card' AND mobile_number IS NOT NULL "
        "AND length(btrim(mobile_number)) > 0 AND operator_provider IS NOT NULL "
        "AND length(btrim(operator_provider)) > 0) OR "
        "(category <> 'SIM Card' AND mobile_number IS NULL AND operator_provider IS NULL))",
        name="ck_asset_sim_fields",
    ),
    Index(
        "uq_asset_serial_canonical",
        func.upper(func.btrim(text("serial_number"))),
        unique=True,
        postgresql_where=text("created_by_employee_id IS NOT NULL"),
    ),
    Index("ix_asset_branch_status", "branch_id", "status"),
)

asset_assignments = Table(
    "asset_assignments",
    metadata,
    pk(),
    Column(
        "asset_id", UUID(as_uuid=True), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False
    ),
    Column(
        "employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("issue_date", Date, nullable=False),
    Column(
        "issued_by_employee_id", UUID(as_uuid=True), ForeignKey("employees.id", ondelete="RESTRICT")
    ),
    Column("return_date", Date),
    Column("return_reason", Text),
    Column("condition_on_return", String(40)),
    Column(
        "returned_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
    ),
    Column("duration_days", Integer, Computed("return_date - issue_date", persisted=True)),
    created_at(),
    Index("uq_issued_asset", "asset_id", unique=True, postgresql_where=text("return_date IS NULL")),
    CheckConstraint(
        "(issued_by_employee_id IS NULL AND returned_by_employee_id IS NULL) OR "
        "(return_date IS NULL AND return_reason IS NULL AND condition_on_return IS NULL "
        "AND returned_by_employee_id IS NULL) OR (return_date IS NOT NULL "
        "AND return_date >= issue_date AND (returned_by_employee_id IS NULL OR "
        "(return_reason IS NOT NULL AND length(btrim(return_reason)) > 0 "
        "AND condition_on_return IN ('Available','Needs Maintenance','Damaged'))))",
        name="ck_asset_assignment_return",
    ),
    Index("ix_asset_assignment_employee", "employee_id", "issue_date"),
)

asset_maintenance_history = Table(
    "asset_maintenance_history",
    metadata,
    pk(),
    Column(
        "asset_id", UUID(as_uuid=True), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False
    ),
    Column("start_date", Date, nullable=False),
    Column(
        "started_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
    ),
    Column("completion_date", Date),
    Column(
        "completed_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
    ),
    Column("resulting_status", String(40)),
    Column("notes", Text),
    Column("completion_notes", Text),
    Column("duration_days", Integer, Computed("completion_date - start_date", persisted=True)),
    created_at(),
    Index(
        "uq_asset_open_maintenance",
        "asset_id",
        unique=True,
        postgresql_where=text("completion_date IS NULL"),
    ),
    CheckConstraint(
        "started_by_employee_id IS NULL OR (notes IS NOT NULL AND length(btrim(notes)) > 0)",
        name="ck_asset_maintenance_notes",
    ),
    CheckConstraint(
        "(started_by_employee_id IS NULL AND completed_by_employee_id IS NULL) OR "
        "(completion_date IS NULL AND resulting_status IS NULL "
        "AND completed_by_employee_id IS NULL) OR (completion_date IS NOT NULL "
        "AND completion_date >= start_date AND (completed_by_employee_id IS NULL OR "
        "resulting_status IN ('Available','Damaged')))",
        name="ck_asset_maintenance_completion",
    ),
)

asset_history = Table(
    "asset_history",
    metadata,
    pk(),
    Column(
        "asset_id", UUID(as_uuid=True), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False
    ),
    Column(
        "branch_id",
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("action", String(40), nullable=False),
    Column("previous_status", String(30)),
    Column("new_status", String(30), nullable=False),
    Column("effective_date", Date, nullable=False),
    Column("employee_id", UUID(as_uuid=True), ForeignKey("employees.id", ondelete="RESTRICT")),
    Column(
        "actor_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "assignment_id", UUID(as_uuid=True), ForeignKey("asset_assignments.id", ondelete="RESTRICT")
    ),
    Column(
        "maintenance_id",
        UUID(as_uuid=True),
        ForeignKey("asset_maintenance_history.id", ondelete="RESTRICT"),
    ),
    Column("reason", Text),
    created_at(),
    CheckConstraint(
        "action IN ('Created','Issued','Returned','Maintenance Started',"
        "'Maintenance Completed','Damaged')",
        name="ck_asset_history_action",
    ),
    Index("ix_asset_history_asset_date", "asset_id", "effective_date"),
)
