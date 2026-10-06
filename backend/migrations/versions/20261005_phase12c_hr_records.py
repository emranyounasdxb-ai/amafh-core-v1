"""Phase 12C HR records.

Versioned employee packages, versioned employee documents with configurable
onboarding requirements, visa records with workflow history, Draft-first HR
letter and certificate templates, numbered issuances and an explicit last
working date for offboarding. Existing Offboarded employees keep a NULL last
working date; no date is inferred. Permission rows are added for existing
User Types inside the approved boundary.

Revision ID: 20261005p12c
Revises: 20261004p12b
"""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20261005p12c"
down_revision = "20261004p12b"
branch_labels = None
depends_on = None

NEW_GRANTS = {
    "Owner": (
        "package.read",
        "package.write",
        "employee_document.read",
        "employee_document.write",
        "employee_document.withdraw",
        "visa.read",
        "visa.write",
        "hr_letter.read",
        "hr_letter.write",
        "hr_letter.approve",
        "hr_letter.void",
        "hr_settings.write",
    ),
    "Managing Director": ("package.read", "employee_document.read", "visa.read"),
    "HR": (
        "package.read",
        "package.write",
        "employee_document.read",
        "employee_document.write",
        "visa.read",
        "visa.write",
        "hr_letter.read",
        "hr_letter.write",
    ),
    "Finance": ("package.read",),
}

DOCUMENT_TYPES = (
    # code, name, required, number, issue, expiry, country, order
    ("passport", "Passport", True, "required", "optional", "required", "required", 10),
    ("emirates_id", "Emirates ID", True, "required", "optional", "required", "none", 20),
    ("residence_visa", "Residence visa", False, "required", "optional", "required", "none", 30),
    (
        "work_permit",
        "Work permit / labour card",
        False,
        "required",
        "optional",
        "required",
        "none",
        40,
    ),
    (
        "employment_contract",
        "Employment contract (signed)",
        True,
        "none",
        "optional",
        "optional",
        "none",
        50,
    ),
    (
        "educational_certificate",
        "Educational certificate",
        False,
        "none",
        "optional",
        "none",
        "optional",
        60,
    ),
    ("other", "Other", False, "optional", "optional", "optional", "optional", 70),
)

EMPLOYMENT = (
    "{{employee_name}} (Employee Code {{company_employee_code}}) has been employed with "
    "{{company_legal_name}} since {{date_of_joining}} and currently holds the position of "
    "{{designation}} in the {{department}} Department, {{branch}} Branch."
)
DRAFT_TEMPLATES = (
    (
        "salary_letter",
        "Salary Certificate",
        f"This is to certify that {EMPLOYMENT}\n\n"
        "{{salary_breakdown}}\n\n"
        "This letter is issued at the request of the employee for the purpose of {{purpose}}.",
    ),
    (
        "employment_verification",
        "Employment Verification Letter",
        f"This is to confirm that {EMPLOYMENT}\n\n"
        "This letter is issued at the request of the employee for the purpose of {{purpose}}.",
    ),
    (
        "noc",
        "No Objection Certificate",
        f"This is to confirm that {EMPLOYMENT}\n\n"
        "{{company_legal_name}} has no objection to the employee's {{noc_purpose}} request "
        "for the purpose of {{purpose}}.",
    ),
    (
        "salary_transfer_letter",
        "Salary Transfer Letter",
        f"This is to confirm that {EMPLOYMENT}\n\n"
        "{{salary_breakdown}}\n\n"
        "At the employee's request, this letter confirms the request to transfer the "
        "employee's salary to the account held with {{addressee}} for the purpose of "
        "{{purpose}}.",
    ),
    (
        "experience_certificate",
        "Experience Certificate",
        "This is to certify that {{employee_name}} (Employee Code {{company_employee_code}}) "
        "was employed with {{company_legal_name}} from {{date_of_joining}} to "
        "{{last_working_date}}.\n\n"
        "Positions held:\n{{designation_history}}\n\n"
        "This certificate is issued at the request of the former employee.",
    ),
)


def _employee_fk(name: str, *, nullable: bool = True) -> sa.Column:
    return sa.Column(
        name,
        UUID(as_uuid=True),
        sa.ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=nullable,
    )


def _id() -> sa.Column:
    return sa.Column("id", UUID(as_uuid=True), primary_key=True)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def _now(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )


FIELD_MODES = "('required','optional','none')"
HR_DOCUMENT_TYPES = (
    "'salary_letter','employment_verification','noc','salary_transfer_letter',"
    "'experience_certificate'"
)
VISA_STATUSES = (
    "'Draft','In Progress','Active','Renewal In Progress','Cancellation In Progress','Cancelled'"
)


def upgrade() -> None:
    op.drop_constraint("stored_files_kind_check", "stored_files", type_="check")
    op.create_check_constraint(
        "stored_files_kind_check",
        "stored_files",
        "kind IN ('employee_avatar','employee_cover','bank_logo',"
        "'product_image','product_variant_image','global_profile_banner',"
        "'employee_document','hr_issued_document')",
    )
    op.add_column("employees", sa.Column("last_working_date", sa.Date()))
    op.create_check_constraint(
        "ck_employee_last_working_date",
        "employees",
        "last_working_date IS NULL OR (status = 'Offboarded' "
        "AND last_working_date >= date_of_joining)",
    )

    op.create_table(
        "employee_packages",
        _id(),
        _employee_fk("employee_id", nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("basic_salary_aed", sa.Numeric(18, 0), nullable=False),
        sa.Column("housing_allowance_aed", sa.Numeric(18, 0)),
        sa.Column("transport_allowance_aed", sa.Numeric(18, 0)),
        sa.Column("other_allowance_label", sa.String(80)),
        sa.Column("other_allowance_aed", sa.Numeric(18, 0)),
        sa.Column("total_monthly_aed", sa.Numeric(18, 0), nullable=False),
        sa.Column("change_reason", sa.String(500), nullable=False),
        _employee_fk("created_by_employee_id", nullable=False),
        _created_at(),
        sa.UniqueConstraint("employee_id", "effective_date"),
        sa.CheckConstraint("basic_salary_aed > 0", name="ck_package_basic_positive"),
        sa.CheckConstraint(
            "coalesce(housing_allowance_aed, 0) >= 0 AND coalesce(transport_allowance_aed, 0) >= 0 "
            "AND coalesce(other_allowance_aed, 0) >= 0",
            name="ck_package_allowances",
        ),
        sa.CheckConstraint(
            "(other_allowance_label IS NULL) = (other_allowance_aed IS NULL)",
            name="ck_package_other_allowance",
        ),
        sa.CheckConstraint(
            "total_monthly_aed = basic_salary_aed + coalesce(housing_allowance_aed, 0) "
            "+ coalesce(transport_allowance_aed, 0) + coalesce(other_allowance_aed, 0)",
            name="ck_package_total",
        ),
        sa.CheckConstraint("length(btrim(change_reason)) > 0", name="ck_package_reason"),
    )

    document_types = op.create_table(
        "employee_document_types",
        _id(),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column(
            "required_at_onboarding", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("number_mode", sa.String(10), nullable=False),
        sa.Column("issue_date_mode", sa.String(10), nullable=False),
        sa.Column("expiry_date_mode", sa.String(10), nullable=False),
        sa.Column("country_mode", sa.String(10), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        _employee_fk("updated_by_employee_id"),
        sa.CheckConstraint(
            f"number_mode IN {FIELD_MODES} AND issue_date_mode IN {FIELD_MODES} "
            f"AND expiry_date_mode IN {FIELD_MODES} AND country_mode IN {FIELD_MODES}",
            name="ck_document_type_modes",
        ),
    )

    op.create_table(
        "employee_documents",
        _id(),
        _employee_fk("employee_id", nullable=False),
        sa.Column(
            "document_type_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employee_document_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("series_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("document_number", sa.String(100)),
        sa.Column("issue_date", sa.Date()),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("issuing_country", sa.String(2)),
        sa.Column("notes", sa.String(1000)),
        sa.Column(
            "file_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stored_files.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(255), nullable=False),
        _employee_fk("uploaded_by_employee_id", nullable=False),
        _now("uploaded_at"),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        _employee_fk("withdrawn_by_employee_id"),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.Column("withdrawal_reason", sa.String(1000)),
        sa.UniqueConstraint("series_id", "version"),
        sa.CheckConstraint(
            "status IN ('Current','Superseded','Withdrawn')", name="ck_employee_document_status"
        ),
        sa.CheckConstraint("version >= 1", name="ck_employee_document_version"),
        sa.CheckConstraint(
            "(status = 'Superseded') = (superseded_at IS NOT NULL)",
            name="ck_employee_document_superseded",
        ),
        sa.CheckConstraint(
            "(status = 'Withdrawn') = (withdrawn_at IS NOT NULL "
            "AND withdrawn_by_employee_id IS NOT NULL AND withdrawal_reason IS NOT NULL "
            "AND length(btrim(withdrawal_reason)) > 0)",
            name="ck_employee_document_withdrawn",
        ),
        sa.CheckConstraint(
            "issue_date IS NULL OR expiry_date IS NULL OR expiry_date >= issue_date",
            name="ck_employee_document_dates",
        ),
    )
    op.create_index(
        "uq_employee_document_current",
        "employee_documents",
        ["series_id"],
        unique=True,
        postgresql_where=sa.text("status = 'Current'"),
    )
    op.create_index("ix_employee_documents_employee", "employee_documents", ["employee_id"])

    op.create_table(
        "visa_records",
        _id(),
        _employee_fk("employee_id", nullable=False),
        sa.Column("visa_type", sa.String(20), nullable=False),
        sa.Column("sponsor", sa.String(160), nullable=False),
        sa.Column("visa_number", sa.String(80)),
        sa.Column("file_number", sa.String(80)),
        sa.Column("issue_date", sa.Date()),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("work_permit_number", sa.String(80)),
        sa.Column("work_permit_expiry_date", sa.Date()),
        sa.Column("medical_fitness_date", sa.Date()),
        sa.Column("insurance_expiry_date", sa.Date()),
        sa.Column("notes", sa.String(1000)),
        sa.Column("status", sa.String(30), nullable=False),
        _employee_fk("created_by_employee_id", nullable=False),
        _created_at(),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        _employee_fk("updated_by_employee_id"),
        sa.CheckConstraint(
            "visa_type IN ('Employment','Investor/Partner','Family-sponsored','Other')",
            name="ck_visa_type",
        ),
        sa.CheckConstraint(f"status IN ({VISA_STATUSES})", name="ck_visa_status"),
        sa.CheckConstraint("length(btrim(sponsor)) > 0", name="ck_visa_sponsor"),
        sa.CheckConstraint(
            "issue_date IS NULL OR expiry_date IS NULL OR expiry_date >= issue_date",
            name="ck_visa_dates",
        ),
        sa.CheckConstraint(
            "status IN ('Draft','In Progress') OR (visa_number IS NOT NULL "
            "AND issue_date IS NOT NULL AND expiry_date IS NOT NULL)",
            name="ck_visa_active_details",
        ),
    )
    op.create_index(
        "uq_visa_current_per_employee",
        "visa_records",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'Cancelled'"),
    )

    op.create_table(
        "visa_record_events",
        _id(),
        sa.Column(
            "visa_record_id",
            UUID(as_uuid=True),
            sa.ForeignKey("visa_records.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("from_status", sa.String(30)),
        sa.Column("to_status", sa.String(30)),
        sa.Column("changes", sa.JSON()),
        sa.Column("note", sa.String(1000)),
        _employee_fk("actor_employee_id", nullable=False),
        _now("occurred_at"),
        sa.CheckConstraint(
            "event_type IN ('created','updated','status_changed','document_attached',"
            "'document_detached')",
            name="ck_visa_event_type",
        ),
    )
    op.create_index("ix_visa_record_events_record", "visa_record_events", ["visa_record_id"])

    op.create_table(
        "visa_record_documents",
        _id(),
        sa.Column(
            "visa_record_id",
            UUID(as_uuid=True),
            sa.ForeignKey("visa_records.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employee_documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        _employee_fk("attached_by_employee_id", nullable=False),
        _now("attached_at"),
        _employee_fk("detached_by_employee_id"),
        sa.Column("detached_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "(detached_at IS NULL) = (detached_by_employee_id IS NULL)",
            name="ck_visa_document_detached",
        ),
    )
    op.create_index(
        "uq_visa_document_attached",
        "visa_record_documents",
        ["visa_record_id", "document_id"],
        unique=True,
        postgresql_where=sa.text("detached_at IS NULL"),
    )

    op.create_table(
        "hr_company_profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_legal_name", sa.String(200)),
        sa.Column("company_address", sa.String(500)),
        sa.Column("trade_license_number", sa.String(80)),
        sa.Column("signatory_name", sa.String(200)),
        sa.Column("signatory_designation", sa.String(120)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        _employee_fk("updated_by_employee_id"),
        sa.CheckConstraint("id = 1", name="ck_hr_company_profile_singleton"),
    )

    templates = op.create_table(
        "hr_document_templates",
        _id(),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        _employee_fk("created_by_employee_id"),
        _created_at(),
        _employee_fk("approved_by_employee_id"),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("document_type", "version"),
        sa.CheckConstraint(f"document_type IN ({HR_DOCUMENT_TYPES})", name="ck_hr_template_type"),
        sa.CheckConstraint(
            "status IN ('Draft','Approved','Retired')", name="ck_hr_template_status"
        ),
        sa.CheckConstraint(
            "(status = 'Draft') = (approved_at IS NULL AND approved_by_employee_id IS NULL)",
            name="ck_hr_template_approval",
        ),
        sa.CheckConstraint(
            "(status = 'Retired') = (retired_at IS NOT NULL)", name="ck_hr_template_retired"
        ),
    )
    op.create_index(
        "uq_hr_template_approved",
        "hr_document_templates",
        ["document_type"],
        unique=True,
        postgresql_where=sa.text("status = 'Approved'"),
    )

    op.create_table(
        "hr_document_sequences",
        _id(),
        sa.Column("prefix", sa.String(10), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.UniqueConstraint("prefix", "year"),
        sa.CheckConstraint("prefix IN ('HR-LTR','HR-CRT')", name="ck_hr_sequence_prefix"),
        sa.CheckConstraint("last_value BETWEEN 1 AND 999999", name="ck_hr_sequence_range"),
    )

    op.create_table(
        "hr_document_issuances",
        _id(),
        sa.Column("document_type", sa.String(40), nullable=False),
        _employee_fk("employee_id", nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("addressee", sa.String(200)),
        sa.Column("purpose", sa.String(500)),
        sa.Column("noc_purpose", sa.String(10)),
        sa.Column(
            "reissue_of_id",
            UUID(as_uuid=True),
            sa.ForeignKey("hr_document_issuances.id", ondelete="RESTRICT"),
        ),
        _employee_fk("prepared_by_employee_id", nullable=False),
        _now("prepared_at"),
        _employee_fk("approved_by_employee_id"),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("document_number", sa.String(20), unique=True),
        sa.Column(
            "template_id",
            UUID(as_uuid=True),
            sa.ForeignKey("hr_document_templates.id", ondelete="RESTRICT"),
        ),
        sa.Column("snapshot", sa.JSON()),
        sa.Column(
            "file_id", UUID(as_uuid=True), sa.ForeignKey("stored_files.id", ondelete="RESTRICT")
        ),
        _employee_fk("issued_by_employee_id"),
        sa.Column("issued_at", sa.DateTime(timezone=True)),
        _employee_fk("voided_by_employee_id"),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("void_reason", sa.String(1000)),
        _employee_fk("cancelled_by_employee_id"),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(1000)),
        sa.CheckConstraint(f"document_type IN ({HR_DOCUMENT_TYPES})", name="ck_hr_issuance_type"),
        sa.CheckConstraint(
            "status IN ('Prepared','Pending Approval','Issued','Voided','Cancelled')",
            name="ck_hr_issuance_status",
        ),
        sa.CheckConstraint(
            "(document_type = 'noc') = (noc_purpose IS NOT NULL)", name="ck_hr_issuance_noc"
        ),
        sa.CheckConstraint(
            "noc_purpose IS NULL OR noc_purpose IN ('Travel','Bank','Visa')",
            name="ck_hr_issuance_noc_purpose",
        ),
        sa.CheckConstraint(
            "(status IN ('Issued','Voided')) = (document_number IS NOT NULL "
            "AND file_id IS NOT NULL AND template_id IS NOT NULL AND snapshot IS NOT NULL "
            "AND issued_at IS NOT NULL AND issued_by_employee_id IS NOT NULL)",
            name="ck_hr_issuance_issued",
        ),
        sa.CheckConstraint(
            "NOT requires_approval OR status NOT IN ('Issued','Voided') "
            "OR (approved_at IS NOT NULL AND approved_by_employee_id IS NOT NULL)",
            name="ck_hr_issuance_approved",
        ),
        sa.CheckConstraint(
            "(status = 'Voided') = (voided_at IS NOT NULL AND voided_by_employee_id IS NOT NULL "
            "AND void_reason IS NOT NULL AND length(btrim(void_reason)) > 0)",
            name="ck_hr_issuance_voided",
        ),
        sa.CheckConstraint(
            "(status = 'Cancelled') = (cancelled_at IS NOT NULL "
            "AND cancelled_by_employee_id IS NOT NULL AND cancel_reason IS NOT NULL "
            "AND length(btrim(cancel_reason)) > 0)",
            name="ck_hr_issuance_cancelled",
        ),
    )
    op.create_index("ix_hr_document_issuances_employee", "hr_document_issuances", ["employee_id"])

    op.bulk_insert(
        document_types,
        [
            {
                "id": uuid4(),
                "code": code,
                "name": name,
                "required_at_onboarding": required,
                "number_mode": number,
                "issue_date_mode": issue,
                "expiry_date_mode": expiry,
                "country_mode": country,
                "sort_order": order,
            }
            for code, name, required, number, issue, expiry, country, order in DOCUMENT_TYPES
        ],
    )
    op.bulk_insert(
        templates,
        [
            {
                "id": uuid4(),
                "document_type": kind,
                "version": 1,
                "title": title,
                "body": body,
                "status": "Draft",
            }
            for kind, title, body in DRAFT_TEMPLATES
        ],
    )
    # The legal name is the approved company name already used on report exports.
    op.execute(
        "INSERT INTO hr_company_profile (id, company_legal_name) "
        "VALUES (1, 'AMAFH Commercial Brokers L.L.C.')"
    )

    for role, keys in NEW_GRANTS.items():
        for key in keys:
            op.execute(
                sa.text(
                    "INSERT INTO permissions (id, key, description) "
                    "VALUES (gen_random_uuid(), :key, :key) ON CONFLICT (key) DO NOTHING"
                ).bindparams(key=key)
            )
            op.execute(
                sa.text(
                    "INSERT INTO role_permissions (id, designation_id, permission_id) "
                    "SELECT gen_random_uuid(), d.id, p.id "
                    "FROM designation_user_types d CROSS JOIN permissions p "
                    "WHERE d.name = :role AND p.key = :key "
                    "ON CONFLICT (designation_id, permission_id) DO NOTHING"
                ).bindparams(role=role, key=key)
            )

    op.execute(
        """
    CREATE TRIGGER protect_employee_packages BEFORE UPDATE OR DELETE ON employee_packages
      FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change();
    CREATE TRIGGER protect_visa_record_events BEFORE UPDATE OR DELETE ON visa_record_events
      FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change();
    CREATE TRIGGER protect_visa_records_delete BEFORE DELETE ON visa_records
      FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change();
    CREATE TRIGGER protect_hr_company_profile_delete BEFORE DELETE ON hr_company_profile
      FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change();

    CREATE FUNCTION amafh_guard_document_type() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' OR (to_jsonb(NEW) - 'required_at_onboarding' - 'updated_at'
           - 'updated_by_employee_id')
         IS DISTINCT FROM (to_jsonb(OLD) - 'required_at_onboarding' - 'updated_at'
           - 'updated_by_employee_id')
      THEN RAISE EXCEPTION 'Employee document types are fixed'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_employee_document_types
      BEFORE UPDATE OR DELETE ON employee_document_types
      FOR EACH ROW EXECUTE FUNCTION amafh_guard_document_type();

    CREATE FUNCTION amafh_guard_employee_document() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Employee document history is retained'; END IF;
      IF OLD.status <> 'Current' OR NEW.status NOT IN ('Superseded','Withdrawn')
         OR (to_jsonb(NEW) - 'status' - 'superseded_at' - 'withdrawn_by_employee_id'
             - 'withdrawn_at' - 'withdrawal_reason')
            IS DISTINCT FROM
            (to_jsonb(OLD) - 'status' - 'superseded_at' - 'withdrawn_by_employee_id'
             - 'withdrawn_at' - 'withdrawal_reason')
      THEN RAISE EXCEPTION 'Employee document versions are read-only'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_employee_documents BEFORE UPDATE OR DELETE ON employee_documents
      FOR EACH ROW EXECUTE FUNCTION amafh_guard_employee_document();

    CREATE FUNCTION amafh_guard_visa_document_link() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' OR OLD.detached_at IS NOT NULL OR NEW.detached_at IS NULL
         OR (to_jsonb(NEW) - 'detached_at' - 'detached_by_employee_id')
            IS DISTINCT FROM (to_jsonb(OLD) - 'detached_at' - 'detached_by_employee_id')
      THEN RAISE EXCEPTION 'Visa document links are retained'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_visa_record_documents BEFORE UPDATE OR DELETE ON visa_record_documents
      FOR EACH ROW EXECUTE FUNCTION amafh_guard_visa_document_link();

    CREATE FUNCTION amafh_guard_hr_template() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'HR document templates are retained'; END IF;
      IF (to_jsonb(NEW) - 'status' - 'approved_by_employee_id' - 'approved_at' - 'retired_at')
         IS DISTINCT FROM
         (to_jsonb(OLD) - 'status' - 'approved_by_employee_id' - 'approved_at' - 'retired_at')
         OR NOT ((OLD.status = 'Draft' AND NEW.status = 'Approved')
                 OR (OLD.status = 'Approved' AND NEW.status = 'Retired'
                     AND NEW.approved_at IS NOT DISTINCT FROM OLD.approved_at
                     AND NEW.approved_by_employee_id
                         IS NOT DISTINCT FROM OLD.approved_by_employee_id))
      THEN RAISE EXCEPTION 'HR document template wording is immutable'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_hr_document_templates BEFORE UPDATE OR DELETE ON hr_document_templates
      FOR EACH ROW EXECUTE FUNCTION amafh_guard_hr_template();

    CREATE FUNCTION amafh_guard_hr_sequence() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' OR NEW.prefix IS DISTINCT FROM OLD.prefix
         OR NEW.year IS DISTINCT FROM OLD.year OR NEW.last_value <> OLD.last_value + 1
      THEN RAISE EXCEPTION 'HR document numbers are never reused'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_hr_document_sequences BEFORE UPDATE OR DELETE ON hr_document_sequences
      FOR EACH ROW EXECUTE FUNCTION amafh_guard_hr_sequence();

    CREATE FUNCTION amafh_guard_hr_issuance() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE fixed_columns text[] := ARRAY['id','document_type','employee_id',
      'requires_approval','addressee','purpose','noc_purpose','reissue_of_id',
      'prepared_by_employee_id','prepared_at'];
    DECLARE issued_columns text[] := ARRAY['approved_by_employee_id','approved_at',
      'document_number','template_id','snapshot','file_id','issued_by_employee_id','issued_at'];
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'HR document history is retained'; END IF;
      IF EXISTS (SELECT 1 FROM unnest(fixed_columns) c
                 WHERE to_jsonb(NEW) -> c IS DISTINCT FROM to_jsonb(OLD) -> c)
      THEN RAISE EXCEPTION 'HR document preparation is immutable'; END IF;
      IF OLD.status IN ('Prepared','Pending Approval')
         AND NEW.status IN ('Issued','Cancelled') THEN RETURN NEW; END IF;
      IF OLD.status = 'Issued' AND NEW.status = 'Voided'
         AND NOT EXISTS (SELECT 1 FROM unnest(issued_columns) c
                         WHERE to_jsonb(NEW) -> c IS DISTINCT FROM to_jsonb(OLD) -> c)
      THEN RETURN NEW; END IF;
      RAISE EXCEPTION 'Issued HR documents are immutable';
    END $$;
    CREATE TRIGGER guard_hr_document_issuances BEFORE UPDATE OR DELETE ON hr_document_issuances
      FOR EACH ROW EXECUTE FUNCTION amafh_guard_hr_issuance();
        """
    )


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
