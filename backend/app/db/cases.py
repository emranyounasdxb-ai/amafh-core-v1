"""Customer, product, pipeline and case relational foundations."""

from sqlalchemy import (
    JSON,
    BigInteger,
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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from .base import created_at, metadata, pk, updated_at

case_id_counters = Table(
    "case_id_counters",
    metadata,
    pk(),
    Column("dubai_year", Integer, nullable=False, unique=True),
    Column("last_value", BigInteger, nullable=False),
    CheckConstraint("dubai_year BETWEEN 2000 AND 9999 AND last_value > 0"),
)

customers = Table(
    "customers",
    metadata,
    pk(),
    Column("customer_id", String(80), nullable=False, unique=True),
    Column("customer_type", String(20), nullable=False),
    created_at(),
    updated_at(),
    CheckConstraint("customer_type IN ('Individual','Company')"),
)
individual_customers = Table(
    "individual_customers",
    metadata,
    pk(),
    Column(
        "customer_id",
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    ),
    Column("emirates_id", String(100), nullable=False, unique=True),
    Column("passport_number", String(100), nullable=False, unique=True),
    Column("full_name", String(200), nullable=False),
    Column("nationality", String(2), nullable=True),
    Column("employer", String(200), nullable=False),
    Column("mobile", String(40), nullable=False),
    Column("email", String(254), nullable=False),
)
company_customers = Table(
    "company_customers",
    metadata,
    pk(),
    Column(
        "customer_id",
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    ),
    Column("company_name", String(200), nullable=False),
    Column("contact_person", String(200), nullable=False),
    Column("trade_license", String(100), nullable=False, unique=True),
    Column("mobile", String(40), nullable=False),
    Column("email", String(254), nullable=False),
)
banks = Table(
    "banks",
    metadata,
    pk(),
    Column("bank_code", String(80), nullable=False, unique=True),
    Column("name", String(200), nullable=False),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column("logo_file_id", UUID(as_uuid=True), ForeignKey("stored_files.id", ondelete="RESTRICT")),
    created_at(),
    updated_at(),
)
product_types = Table(
    "product_types",
    metadata,
    pk(),
    Column("name", String(150), nullable=False, unique=True),
    Column("code", String(30), nullable=False, unique=True),
    Column("image_file_id", UUID(as_uuid=True), ForeignKey("stored_files.id", ondelete="RESTRICT")),
    Column("active", Boolean, nullable=False, server_default="true"),
    created_at(),
    updated_at(),
)
product_variants = Table(
    "product_variants",
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
    Column("name", String(150), nullable=False),
    Column("image_file_id", UUID(as_uuid=True), ForeignKey("stored_files.id", ondelete="RESTRICT")),
    Column("active", Boolean, nullable=False, server_default="true"),
    created_at(),
    updated_at(),
    UniqueConstraint("bank_id", "product_type_id", "name"),
    UniqueConstraint("id", "bank_id", "product_type_id", name="uq_variant_id_context"),
)
bank_product_mappings = Table(
    "bank_product_mappings",
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
    Column("active", Boolean, nullable=False, server_default="true"),
    UniqueConstraint("bank_id", "product_type_id"),
)
pipeline_configurations = Table(
    "pipeline_configurations",
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
    Column("effective_date", Date, nullable=False),
    Column("version", Integer, nullable=False),
    Column("active", Boolean, nullable=False, server_default="true"),
    created_at(),
    UniqueConstraint("bank_id", "product_type_id", "effective_date"),
    UniqueConstraint("bank_id", "product_type_id", "version"),
    UniqueConstraint("id", "bank_id", "product_type_id", name="uq_pipeline_id_context"),
)
pipeline_stages = Table(
    "pipeline_stages",
    metadata,
    pk(),
    Column(
        "pipeline_configuration_id",
        UUID(as_uuid=True),
        ForeignKey("pipeline_configurations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("name", String(150), nullable=False),
    Column("stage_order", Integer, nullable=False),
    Column("expected_business_days", Integer, nullable=False),
    Column("is_final", Boolean, nullable=False, server_default="false"),
    Column("final_status", String(20)),
    UniqueConstraint("pipeline_configuration_id", "name"),
    UniqueConstraint("pipeline_configuration_id", "stage_order"),
    CheckConstraint("stage_order > 0 AND expected_business_days >= 0"),
    CheckConstraint(
        "final_status IS NULL OR (is_final AND final_status IN ('Completed','Rejected'))",
        name="ck_pipeline_final_status",
    ),
)
cases = Table(
    "cases",
    metadata,
    pk(),
    Column("internal_case_id", String(80), nullable=False, unique=True),
    Column(
        "customer_id",
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    ),
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
    Column(
        "pipeline_configuration_id",
        UUID(as_uuid=True),
        ForeignKey("pipeline_configurations.id", ondelete="RESTRICT"),
    ),
    Column("requested_pf_amount", Numeric(18, 0)),
    Column(
        "created_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "owner_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "coordinator_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
    ),
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
    Column("current_status", String(80), nullable=False),
    Column("current_stage", String(150)),
    Column("bank_case_number", String(120), unique=True),
    Column("finalized_at", DateTime(timezone=True)),
    Column("owner_transfer_previous_status", String(80)),
    Column("administratively_voided_at", DateTime(timezone=True)),
    Column(
        "administratively_voided_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
    ),
    Column("administrative_void_reason", Text),
    created_at(),
    updated_at(),
    Index("ix_cases_scope_status", "branch_id", "department_id", "current_status"),
    Index("ix_cases_owner", "owner_employee_id"),
    Index("ix_cases_coordinator", "coordinator_employee_id", "current_status"),
    Index("ix_cases_created", "created_at"),
    Index("ix_cases_voided_at", "administratively_voided_at"),
    CheckConstraint(
        "(administratively_voided_at IS NULL AND administratively_voided_by_employee_id IS NULL "
        "AND administrative_void_reason IS NULL) OR "
        "(administratively_voided_at IS NOT NULL AND "
        "administratively_voided_by_employee_id IS NOT NULL AND "
        "administrative_void_reason IS NOT NULL AND "
        "length(btrim(administrative_void_reason)) > 0)",
        name="ck_cases_administrative_void_complete",
    ),
    ForeignKeyConstraint(
        ["department_id", "branch_id"],
        ["departments.id", "departments.branch_id"],
        name="fk_case_department_branch",
    ),
    ForeignKeyConstraint(
        ["product_variant_id", "bank_id", "product_type_id"],
        ["product_variants.id", "product_variants.bank_id", "product_variants.product_type_id"],
        name="fk_case_variant_context",
    ),
    ForeignKeyConstraint(
        ["pipeline_configuration_id", "bank_id", "product_type_id"],
        [
            "pipeline_configurations.id",
            "pipeline_configurations.bank_id",
            "pipeline_configurations.product_type_id",
        ],
        name="fk_case_pipeline_context",
    ),
)
case_ownership_history = Table(
    "case_ownership_history",
    metadata,
    pk(),
    Column(
        "case_id", UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False
    ),
    Column(
        "owner_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("ended_at", DateTime(timezone=True)),
    Column(
        "changed_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Index("ix_case_ownership_case_dates", "case_id", "started_at"),
    Index(
        "uq_case_current_owner", "case_id", unique=True, postgresql_where=text("ended_at IS NULL")
    ),
)
case_approvals = Table(
    "case_approvals",
    metadata,
    pk(),
    Column(
        "case_id", UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False
    ),
    Column(
        "approved_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "coordinator_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("approved_at", DateTime(timezone=True), nullable=False),
    Index("ix_case_approvals_case_time", "case_id", "approved_at"),
)
case_lifecycle_history = Table(
    "case_lifecycle_history",
    metadata,
    pk(),
    Column(
        "case_id", UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False
    ),
    Column("previous_status", String(80)),
    Column("status", String(80), nullable=False),
    Column(
        "actor_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("context", JSON, nullable=False, server_default="{}"),
    Index("ix_case_lifecycle_case_time", "case_id", "occurred_at"),
)
case_stage_history = Table(
    "case_stage_history",
    metadata,
    pk(),
    Column(
        "case_id", UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False
    ),
    Column("stage", String(150), nullable=False),
    Column("remark", Text),
    Column("status", String(80), nullable=False),
    Column(
        "updated_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "csv_import_batch_id",
        UUID(as_uuid=True),
        ForeignKey("csv_import_batches.id", ondelete="RESTRICT"),
    ),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Index("ix_case_stage_history_case_time", "case_id", "occurred_at"),
)

case_notice_events = Table(
    "case_notice_events",
    metadata,
    pk(),
    Column(
        "case_id", UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False
    ),
    Column("kind", String(40), nullable=False),
    Column("cycle_started_at", DateTime(timezone=True), nullable=False),
    Column("interval_index", Integer, nullable=False),
    Column(
        "recipient_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "notification_id",
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    ),
    created_at(),
    UniqueConstraint(
        "case_id",
        "kind",
        "cycle_started_at",
        "interval_index",
        "recipient_employee_id",
        name="uq_case_notice_interval_recipient",
    ),
    CheckConstraint("kind IN ('pending_approval','stage_delayed')", name="ck_case_notice_kind"),
    CheckConstraint("interval_index >= 1", name="ck_case_notice_interval"),
)


def _canonical(column):
    return func.upper(func.regexp_replace(func.btrim(column), "[[:space:]]+", " ", "g"))


for _name, _table, _column in (
    ("uq_individual_emirates_canonical", individual_customers, "emirates_id"),
    ("uq_individual_passport_canonical", individual_customers, "passport_number"),
    ("uq_company_license_canonical", company_customers, "trade_license"),
    ("uq_bank_case_number_canonical", cases, "bank_case_number"),
    ("uq_bank_code_canonical", banks, "bank_code"),
    ("uq_bank_name_canonical", banks, "name"),
    ("uq_product_code_canonical", product_types, "code"),
):
    Index(_name, _canonical(_table.c[_column]), unique=True)

Index(
    "uq_variant_name_canonical",
    product_variants.c.bank_id,
    product_variants.c.product_type_id,
    func.lower(func.regexp_replace(func.btrim(product_variants.c.name), "[[:space:]]+", " ", "g")),
    unique=True,
)
