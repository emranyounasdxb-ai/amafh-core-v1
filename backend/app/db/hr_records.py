"""Employee packages, documents, visa records, and HR letters and certificates."""

from sqlalchemy import (
    JSON,
    Boolean,
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
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from .base import created_at, metadata, pk


def _employee_fk(name: str, *, nullable: bool = True) -> Column:
    return Column(
        name,
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=nullable,
    )


employee_packages = Table(
    "employee_packages",
    metadata,
    pk(),
    _employee_fk("employee_id", nullable=False),
    Column("effective_date", Date, nullable=False),
    Column("basic_salary_aed", Numeric(18, 0), nullable=False),
    Column("housing_allowance_aed", Numeric(18, 0)),
    Column("transport_allowance_aed", Numeric(18, 0)),
    Column("other_allowance_label", String(80)),
    Column("other_allowance_aed", Numeric(18, 0)),
    Column("total_monthly_aed", Numeric(18, 0), nullable=False),
    Column("change_reason", String(500), nullable=False),
    _employee_fk("created_by_employee_id", nullable=False),
    created_at(),
    UniqueConstraint("employee_id", "effective_date"),
    CheckConstraint("basic_salary_aed > 0", name="ck_package_basic_positive"),
    CheckConstraint(
        "coalesce(housing_allowance_aed, 0) >= 0 AND coalesce(transport_allowance_aed, 0) >= 0 "
        "AND coalesce(other_allowance_aed, 0) >= 0",
        name="ck_package_allowances",
    ),
    CheckConstraint(
        "(other_allowance_label IS NULL) = (other_allowance_aed IS NULL)",
        name="ck_package_other_allowance",
    ),
    CheckConstraint(
        "total_monthly_aed = basic_salary_aed + coalesce(housing_allowance_aed, 0) "
        "+ coalesce(transport_allowance_aed, 0) + coalesce(other_allowance_aed, 0)",
        name="ck_package_total",
    ),
    CheckConstraint("length(btrim(change_reason)) > 0", name="ck_package_reason"),
)

FIELD_MODES = "('required','optional','none')"
employee_document_types = Table(
    "employee_document_types",
    metadata,
    pk(),
    Column("code", String(40), nullable=False, unique=True),
    Column("name", String(80), nullable=False, unique=True),
    Column("required_at_onboarding", Boolean, nullable=False, server_default=text("false")),
    Column("number_mode", String(10), nullable=False),
    Column("issue_date_mode", String(10), nullable=False),
    Column("expiry_date_mode", String(10), nullable=False),
    Column("country_mode", String(10), nullable=False),
    Column("sort_order", Integer, nullable=False),
    Column("updated_at", DateTime(timezone=True)),
    _employee_fk("updated_by_employee_id"),
    CheckConstraint(
        f"number_mode IN {FIELD_MODES} AND issue_date_mode IN {FIELD_MODES} "
        f"AND expiry_date_mode IN {FIELD_MODES} AND country_mode IN {FIELD_MODES}",
        name="ck_document_type_modes",
    ),
)

employee_documents = Table(
    "employee_documents",
    metadata,
    pk(),
    _employee_fk("employee_id", nullable=False),
    Column(
        "document_type_id",
        UUID(as_uuid=True),
        ForeignKey("employee_document_types.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("series_id", UUID(as_uuid=True), nullable=False),
    Column("version", Integer, nullable=False),
    Column("status", String(12), nullable=False),
    Column("document_number", String(100)),
    Column("issue_date", Date),
    Column("expiry_date", Date),
    Column("issuing_country", String(2)),
    Column("notes", String(1000)),
    Column(
        "file_id",
        UUID(as_uuid=True),
        ForeignKey("stored_files.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("original_filename", String(255), nullable=False),
    _employee_fk("uploaded_by_employee_id", nullable=False),
    Column("uploaded_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Column("superseded_at", DateTime(timezone=True)),
    _employee_fk("withdrawn_by_employee_id"),
    Column("withdrawn_at", DateTime(timezone=True)),
    Column("withdrawal_reason", String(1000)),
    UniqueConstraint("series_id", "version"),
    CheckConstraint(
        "status IN ('Current','Superseded','Withdrawn')", name="ck_employee_document_status"
    ),
    CheckConstraint("version >= 1", name="ck_employee_document_version"),
    CheckConstraint(
        "(status = 'Superseded') = (superseded_at IS NOT NULL)",
        name="ck_employee_document_superseded",
    ),
    CheckConstraint(
        "(status = 'Withdrawn') = (withdrawn_at IS NOT NULL "
        "AND withdrawn_by_employee_id IS NOT NULL AND withdrawal_reason IS NOT NULL "
        "AND length(btrim(withdrawal_reason)) > 0)",
        name="ck_employee_document_withdrawn",
    ),
    CheckConstraint(
        "issue_date IS NULL OR expiry_date IS NULL OR expiry_date >= issue_date",
        name="ck_employee_document_dates",
    ),
    Index(
        "uq_employee_document_current",
        "series_id",
        unique=True,
        postgresql_where=text("status = 'Current'"),
    ),
    Index("ix_employee_documents_employee", "employee_id"),
)

VISA_STATUSES = (
    "'Draft','In Progress','Active','Renewal In Progress','Cancellation In Progress','Cancelled'"
)
visa_records = Table(
    "visa_records",
    metadata,
    pk(),
    _employee_fk("employee_id", nullable=False),
    Column("visa_type", String(20), nullable=False),
    Column("sponsor", String(160), nullable=False),
    Column("visa_number", String(80)),
    Column("file_number", String(80)),
    Column("issue_date", Date),
    Column("expiry_date", Date),
    Column("work_permit_number", String(80)),
    Column("work_permit_expiry_date", Date),
    Column("medical_fitness_date", Date),
    Column("insurance_expiry_date", Date),
    Column("notes", String(1000)),
    Column("status", String(30), nullable=False),
    _employee_fk("created_by_employee_id", nullable=False),
    created_at(),
    Column("updated_at", DateTime(timezone=True)),
    _employee_fk("updated_by_employee_id"),
    CheckConstraint(
        "visa_type IN ('Employment','Investor/Partner','Family-sponsored','Other')",
        name="ck_visa_type",
    ),
    CheckConstraint(f"status IN ({VISA_STATUSES})", name="ck_visa_status"),
    CheckConstraint("length(btrim(sponsor)) > 0", name="ck_visa_sponsor"),
    CheckConstraint(
        "issue_date IS NULL OR expiry_date IS NULL OR expiry_date >= issue_date",
        name="ck_visa_dates",
    ),
    CheckConstraint(
        "status IN ('Draft','In Progress') OR (visa_number IS NOT NULL "
        "AND issue_date IS NOT NULL AND expiry_date IS NOT NULL)",
        name="ck_visa_active_details",
    ),
    Index(
        "uq_visa_current_per_employee",
        "employee_id",
        unique=True,
        postgresql_where=text("status <> 'Cancelled'"),
    ),
)

visa_record_events = Table(
    "visa_record_events",
    metadata,
    pk(),
    Column(
        "visa_record_id",
        UUID(as_uuid=True),
        ForeignKey("visa_records.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("event_type", String(30), nullable=False),
    Column("from_status", String(30)),
    Column("to_status", String(30)),
    Column("changes", JSON),
    Column("note", String(1000)),
    _employee_fk("actor_employee_id", nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    CheckConstraint(
        "event_type IN ('created','updated','status_changed','document_attached',"
        "'document_detached')",
        name="ck_visa_event_type",
    ),
    Index("ix_visa_record_events_record", "visa_record_id"),
)

visa_record_documents = Table(
    "visa_record_documents",
    metadata,
    pk(),
    Column(
        "visa_record_id",
        UUID(as_uuid=True),
        ForeignKey("visa_records.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "document_id",
        UUID(as_uuid=True),
        ForeignKey("employee_documents.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    _employee_fk("attached_by_employee_id", nullable=False),
    Column("attached_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    _employee_fk("detached_by_employee_id"),
    Column("detached_at", DateTime(timezone=True)),
    CheckConstraint(
        "(detached_at IS NULL) = (detached_by_employee_id IS NULL)",
        name="ck_visa_document_detached",
    ),
    Index(
        "uq_visa_document_attached",
        "visa_record_id",
        "document_id",
        unique=True,
        postgresql_where=text("detached_at IS NULL"),
    ),
)

hr_company_profile = Table(
    "hr_company_profile",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_legal_name", String(200)),
    Column("company_address", String(500)),
    Column("trade_license_number", String(80)),
    Column("signatory_name", String(200)),
    Column("signatory_designation", String(120)),
    Column("updated_at", DateTime(timezone=True)),
    _employee_fk("updated_by_employee_id"),
    CheckConstraint("id = 1", name="ck_hr_company_profile_singleton"),
)

HR_DOCUMENT_TYPES = (
    "'salary_letter','employment_verification','noc','salary_transfer_letter',"
    "'experience_certificate'"
)
hr_document_templates = Table(
    "hr_document_templates",
    metadata,
    pk(),
    Column("document_type", String(40), nullable=False),
    Column("version", Integer, nullable=False),
    Column("title", String(200), nullable=False),
    Column("body", Text, nullable=False),
    Column("status", String(10), nullable=False),
    _employee_fk("created_by_employee_id"),
    created_at(),
    _employee_fk("approved_by_employee_id"),
    Column("approved_at", DateTime(timezone=True)),
    Column("retired_at", DateTime(timezone=True)),
    UniqueConstraint("document_type", "version"),
    CheckConstraint(f"document_type IN ({HR_DOCUMENT_TYPES})", name="ck_hr_template_type"),
    CheckConstraint("status IN ('Draft','Approved','Retired')", name="ck_hr_template_status"),
    CheckConstraint(
        "(status = 'Draft') = (approved_at IS NULL AND approved_by_employee_id IS NULL)",
        name="ck_hr_template_approval",
    ),
    CheckConstraint(
        "(status = 'Retired') = (retired_at IS NOT NULL)", name="ck_hr_template_retired"
    ),
    Index(
        "uq_hr_template_approved",
        "document_type",
        unique=True,
        postgresql_where=text("status = 'Approved'"),
    ),
)

hr_document_sequences = Table(
    "hr_document_sequences",
    metadata,
    pk(),
    Column("prefix", String(10), nullable=False),
    Column("year", Integer, nullable=False),
    Column("last_value", Integer, nullable=False),
    UniqueConstraint("prefix", "year"),
    CheckConstraint("prefix IN ('HR-LTR','HR-CRT')", name="ck_hr_sequence_prefix"),
    CheckConstraint("last_value BETWEEN 1 AND 999999", name="ck_hr_sequence_range"),
)

hr_document_issuances = Table(
    "hr_document_issuances",
    metadata,
    pk(),
    Column("document_type", String(40), nullable=False),
    _employee_fk("employee_id", nullable=False),
    Column("status", String(20), nullable=False),
    Column("requires_approval", Boolean, nullable=False),
    Column("addressee", String(200)),
    Column("purpose", String(500)),
    Column("noc_purpose", String(10)),
    Column(
        "reissue_of_id",
        UUID(as_uuid=True),
        ForeignKey("hr_document_issuances.id", ondelete="RESTRICT"),
    ),
    _employee_fk("prepared_by_employee_id", nullable=False),
    Column("prepared_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    _employee_fk("approved_by_employee_id"),
    Column("approved_at", DateTime(timezone=True)),
    Column("document_number", String(20), unique=True),
    Column(
        "template_id",
        UUID(as_uuid=True),
        ForeignKey("hr_document_templates.id", ondelete="RESTRICT"),
    ),
    Column("snapshot", JSON),
    Column("file_id", UUID(as_uuid=True), ForeignKey("stored_files.id", ondelete="RESTRICT")),
    _employee_fk("issued_by_employee_id"),
    Column("issued_at", DateTime(timezone=True)),
    _employee_fk("voided_by_employee_id"),
    Column("voided_at", DateTime(timezone=True)),
    Column("void_reason", String(1000)),
    _employee_fk("cancelled_by_employee_id"),
    Column("cancelled_at", DateTime(timezone=True)),
    Column("cancel_reason", String(1000)),
    CheckConstraint(f"document_type IN ({HR_DOCUMENT_TYPES})", name="ck_hr_issuance_type"),
    CheckConstraint(
        "status IN ('Prepared','Pending Approval','Issued','Voided','Cancelled')",
        name="ck_hr_issuance_status",
    ),
    CheckConstraint(
        "(document_type = 'noc') = (noc_purpose IS NOT NULL)", name="ck_hr_issuance_noc"
    ),
    CheckConstraint(
        "noc_purpose IS NULL OR noc_purpose IN ('Travel','Bank','Visa')",
        name="ck_hr_issuance_noc_purpose",
    ),
    CheckConstraint(
        "(status IN ('Issued','Voided')) = (document_number IS NOT NULL AND file_id IS NOT NULL "
        "AND template_id IS NOT NULL AND snapshot IS NOT NULL AND issued_at IS NOT NULL "
        "AND issued_by_employee_id IS NOT NULL)",
        name="ck_hr_issuance_issued",
    ),
    CheckConstraint(
        "NOT requires_approval OR status NOT IN ('Issued','Voided') "
        "OR (approved_at IS NOT NULL AND approved_by_employee_id IS NOT NULL)",
        name="ck_hr_issuance_approved",
    ),
    CheckConstraint(
        "(status = 'Voided') = (voided_at IS NOT NULL AND voided_by_employee_id IS NOT NULL "
        "AND void_reason IS NOT NULL AND length(btrim(void_reason)) > 0)",
        name="ck_hr_issuance_voided",
    ),
    CheckConstraint(
        "(status = 'Cancelled') = (cancelled_at IS NOT NULL "
        "AND cancelled_by_employee_id IS NOT NULL AND cancel_reason IS NOT NULL "
        "AND length(btrim(cancel_reason)) > 0)",
        name="ck_hr_issuance_cancelled",
    ),
    Index("ix_hr_document_issuances_employee", "employee_id"),
)
