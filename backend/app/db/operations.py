"""Attendance, assets, finance, notifications and audit foundations."""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from .assets import asset_assignments, asset_maintenance_history, assets  # noqa: F401
from .attendance import (
    attendance_records,
    csv_import_batches,
    csv_import_row_results,
    office_timings,
)
from .base import created_at, metadata, pk
from .targets import targets  # noqa: F401

__all__ = (
    "attendance_records",
    "csv_import_batches",
    "csv_import_row_results",
    "office_timings",
    "asset_assignments",
    "asset_maintenance_history",
    "assets",
)

financial_rules = Table(
    "financial_rules",
    metadata,
    pk(),
    Column(
        "bank_id", UUID(as_uuid=True), ForeignKey("banks.id", ondelete="RESTRICT"), nullable=False
    ),
    Column(
        "product_type_id",
        UUID(as_uuid=True),
        ForeignKey("product_types.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "product_variant_id",
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
    ),
    Column("pf_amount_min", Numeric(18, 0)),
    Column("pf_amount_max", Numeric(18, 0)),
    Column("cc_points", Integer),
    Column("commission_aed", Numeric(18, 0)),
    Column("effective_date", Date, nullable=False),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column(
        "superseded_by_rule_id",
        UUID(as_uuid=True),
        ForeignKey("financial_rules.id", ondelete="RESTRICT"),
    ),
    created_at(),
    Index("ix_financial_rule_context", "bank_id", "product_type_id", "effective_date"),
    Index(
        "uq_cc_rule_effective_version",
        "bank_id",
        "product_variant_id",
        "effective_date",
        unique=True,
        postgresql_where=text("product_variant_id IS NOT NULL"),
    ),
    Index(
        "uq_pf_rule_effective_version",
        "bank_id",
        "product_type_id",
        "pf_amount_min",
        "pf_amount_max",
        "effective_date",
        unique=True,
        postgresql_where=text("product_variant_id IS NULL"),
    ),
    ForeignKeyConstraint(
        ["product_variant_id", "bank_id", "product_type_id"],
        ["product_variants.id", "product_variants.bank_id", "product_variants.product_type_id"],
        name="fk_financial_rule_variant_context",
    ),
    Index(
        "uq_active_cc_financial_rule",
        "bank_id",
        "product_variant_id",
        unique=True,
        postgresql_where=text("active AND product_variant_id IS NOT NULL"),
    ),
    Index(
        "uq_active_pf_financial_rule_slab",
        "bank_id",
        "product_type_id",
        "pf_amount_min",
        "pf_amount_max",
        unique=True,
        postgresql_where=text(
            "active AND product_variant_id IS NULL AND pf_amount_min IS NOT NULL "
            "AND pf_amount_max IS NOT NULL"
        ),
    ),
    CheckConstraint(
        "(product_variant_id IS NOT NULL AND pf_amount_min IS NULL AND pf_amount_max IS NULL) "
        "OR (product_variant_id IS NULL AND pf_amount_min IS NOT NULL "
        "AND pf_amount_max IS NOT NULL AND pf_amount_min <= pf_amount_max)",
        name="ck_financial_rule_context",
    ),
    CheckConstraint(
        "(cc_points IS NULL OR cc_points > 0) AND "
        "(commission_aed IS NULL OR commission_aed >= 0) AND "
        "((product_variant_id IS NOT NULL AND "
        "(cc_points IS NOT NULL OR commission_aed IS NOT NULL)) OR "
        "(product_variant_id IS NULL AND pf_amount_min > 0 AND commission_aed IS NOT NULL))",
        name="ck_financial_rule_values",
    ),
)
points_wallets = Table(
    "points_wallets",
    metadata,
    pk(),
    Column(
        "employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    ),
    created_at(),
)
points_wallet_transactions = Table(
    "points_wallet_transactions",
    metadata,
    pk(),
    Column(
        "wallet_id",
        UUID(as_uuid=True),
        ForeignKey("points_wallets.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "case_id",
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    ),
    Column("points_credited", Integer, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("points_credited > 0"),
)
clawbacks = Table(
    "clawbacks",
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
        "case_owner_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("amount_aed", Numeric(18, 0), nullable=False),
    Column("clawback_date", Date, nullable=False),
    Column("reason", Text, nullable=False),
    Column(
        "created_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    created_at(),
    CheckConstraint("amount_aed > 0", name="ck_clawback_positive"),
    CheckConstraint("length(btrim(reason)) > 0", name="ck_clawback_reason"),
)
payment_records = Table(
    "payment_records",
    metadata,
    pk(),
    Column(
        "employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("payment_type", String(20), nullable=False),
    Column("amount_aed", Numeric(18, 0), nullable=False),
    Column("payment_month", Date, nullable=False),
    Column("payment_date", Date, nullable=False),
    Column(
        "created_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    created_at(),
    UniqueConstraint("employee_id", "payment_month", "payment_type"),
    CheckConstraint("payment_type IN ('Salary','Commission')"),
    CheckConstraint("amount_aed > 0", name="ck_payment_positive"),
    CheckConstraint("EXTRACT(DAY FROM payment_month) = 1", name="ck_payment_month_start"),
)
notifications = Table(
    "notifications",
    metadata,
    pk(),
    Column(
        "recipient_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("kind", String(80), nullable=False),
    Column("target_id", UUID(as_uuid=True), ForeignKey("targets.id", ondelete="RESTRICT")),
    Column("case_id", UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT")),
    Column("task_id", UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="RESTRICT")),
    Column(
        "csv_import_batch_id",
        UUID(as_uuid=True),
        ForeignKey("csv_import_batches.id", ondelete="RESTRICT"),
    ),
    Column("employee_id", UUID(as_uuid=True), ForeignKey("employees.id", ondelete="RESTRICT")),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT")),
    Column("message", Text, nullable=False),
    Column(
        "available_on",
        Date,
        nullable=False,
        server_default=text("(now() AT TIME ZONE 'Asia/Dubai')::date"),
    ),
    Column("read_at", DateTime(timezone=True)),
    Column("suppressed_at", DateTime(timezone=True)),
    created_at(),
    Index("ix_notification_recipient_read", "recipient_employee_id", "read_at"),
    Index(
        "ix_notification_recipient_created",
        "recipient_employee_id",
        "created_at",
        "id",
    ),
    Index("ix_notification_case", "case_id"),
    Index("ix_notification_task", "task_id"),
    Index("ix_notification_csv_import_batch", "csv_import_batch_id"),
    Index("ix_notification_employee", "employee_id"),
    Index("ix_notification_team", "team_id"),
    CheckConstraint(
        "(target_id IS NOT NULL)::int + (case_id IS NOT NULL)::int + "
        "(task_id IS NOT NULL)::int + (csv_import_batch_id IS NOT NULL)::int + "
        "(employee_id IS NOT NULL)::int + (team_id IS NOT NULL)::int <= 1",
        name="ck_notification_one_source",
    ),
    Index(
        "uq_target_notification_recipient",
        "target_id",
        "recipient_employee_id",
        unique=True,
        postgresql_where=text("target_id IS NOT NULL"),
    ),
)
stored_files = Table(
    "stored_files",
    metadata,
    pk(),
    Column("kind", String(40), nullable=False),
    Column("storage_key", String(255), nullable=False, unique=True),
    Column("content_type", String(80), nullable=False),
    Column("byte_size", Integer, nullable=False),
    Column(
        "uploaded_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    created_at(),
    CheckConstraint(
        "kind IN ('employee_avatar','employee_cover','bank_logo',"
        "'product_image','product_variant_image','global_profile_banner',"
        "'employee_document','hr_issued_document')"
    ),
)
global_profile_banner = Table(
    "global_profile_banner",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("file_id", UUID(as_uuid=True), ForeignKey("stored_files.id", ondelete="RESTRICT")),
    Column(
        "updated_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
    ),
    Column("updated_at", DateTime(timezone=True)),
    CheckConstraint("id = 1", name="ck_global_profile_banner_singleton"),
)
export_requests = Table(
    "export_requests",
    metadata,
    pk(),
    Column(
        "requested_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("report_type", String(80), nullable=False),
    Column("format", String(10), nullable=False),
    Column("filters", JSON, nullable=False),
    Column("status", String(30), nullable=False),
    created_at(),
    CheckConstraint("format IN ('CSV','PDF')"),
)
idempotency_records = Table(
    "idempotency_records",
    metadata,
    pk(),
    Column(
        "actor_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("operation", String(100), nullable=False),
    Column("idempotency_key", String(150), nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("response_status", Integer),
    Column("response_json", JSON),
    created_at(),
    UniqueConstraint("actor_employee_id", "operation", "idempotency_key"),
)
audit_events = Table(
    "audit_events",
    metadata,
    pk(),
    Column("actor_employee_id", UUID(as_uuid=True)),
    Column("action", String(120), nullable=False),
    Column("module", String(80), nullable=False),
    Column("entity_type", String(80)),
    Column("entity_id", String(120)),
    Column("context", JSON, nullable=False, server_default="{}"),
    Column("before_values", JSON),
    Column("after_values", JSON),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Index("ix_audit_actor_time", "actor_employee_id", "occurred_at"),
    Index("ix_audit_entity", "entity_type", "entity_id"),
)
