"""Add Phase 2 identifiers, pipeline outcomes, import replay guards and history.

Revision ID: 20260926cases
Revises: 20260926ownerlock
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260926cases"
down_revision = "20260926ownerlock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE amafh_employee_code_seq AS bigint START WITH 1 NO CYCLE")
    op.execute("""
    SELECT setval('amafh_employee_code_seq', GREATEST(1, COALESCE((
      SELECT max(substring(system_employee_code from 5)::bigint) + 1
      FROM employees WHERE system_employee_code ~ '^EMP-[0-9]+$'
    ), 1)), false)
    """)
    op.create_table(
        "case_id_counters",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("dubai_year", sa.Integer(), nullable=False, unique=True),
        sa.Column("last_value", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("dubai_year BETWEEN 2000 AND 9999 AND last_value > 0"),
    )
    op.execute("""
    CREATE FUNCTION amafh_protect_business_reference() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      IF (TG_TABLE_NAME = 'employees' AND
          NEW.system_employee_code IS DISTINCT FROM OLD.system_employee_code)
         OR (TG_TABLE_NAME = 'cases' AND
          NEW.internal_case_id IS DISTINCT FROM OLD.internal_case_id)
         OR (TG_TABLE_NAME = 'customers' AND
          NEW.customer_id IS DISTINCT FROM OLD.customer_id) THEN
        RAISE EXCEPTION 'Immutable business reference';
      END IF;
      RETURN NEW;
    END $$
    """)
    for table, column in (
        ("employees", "system_employee_code"),
        ("cases", "internal_case_id"),
        ("customers", "customer_id"),
    ):
        op.execute(
            f"CREATE TRIGGER protect_{table}_business_reference BEFORE UPDATE OF {column} "
            f"ON {table} FOR EACH ROW EXECUTE FUNCTION amafh_protect_business_reference()"
        )
    for table, column, index in (
        ("individual_customers", "emirates_id", "uq_individual_emirates_canonical"),
        ("individual_customers", "passport_number", "uq_individual_passport_canonical"),
        ("company_customers", "trade_license", "uq_company_license_canonical"),
        ("cases", "bank_case_number", "uq_bank_case_number_canonical"),
        ("banks", "bank_code", "uq_bank_code_canonical"),
        ("banks", "name", "uq_bank_name_canonical"),
        ("product_types", "code", "uq_product_code_canonical"),
    ):
        op.execute(
            f"CREATE UNIQUE INDEX {index} ON {table} "
            f"(upper(regexp_replace(btrim({column}), '[[:space:]]+', ' ', 'g')))"
        )
    op.execute("""
    CREATE UNIQUE INDEX uq_variant_name_canonical ON product_variants
    (bank_id, product_type_id, lower(regexp_replace(btrim(name), '[[:space:]]+', ' ', 'g')))
    """)
    op.create_unique_constraint("uq_case_approval_once", "case_approvals", ["case_id"])
    op.add_column(
        "pipeline_configurations",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("pipeline_stages", sa.Column("final_status", sa.String(20)))
    op.create_check_constraint(
        "ck_pipeline_final_status",
        "pipeline_stages",
        "final_status IS NULL OR (is_final AND final_status IN ('Completed','Rejected'))",
    )
    op.execute("DROP TRIGGER protect_pipeline_configurations ON pipeline_configurations")
    op.execute("""
    CREATE FUNCTION amafh_pipeline_active_only() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Pipeline history is immutable'; END IF;
      IF (to_jsonb(OLD) - 'active') IS DISTINCT FROM (to_jsonb(NEW) - 'active') THEN
        RAISE EXCEPTION 'Pipeline version is immutable';
      END IF;
      RETURN NEW;
    END $$
    """)
    op.execute("""
    CREATE TRIGGER protect_pipeline_configurations
    BEFORE UPDATE OR DELETE ON pipeline_configurations
    FOR EACH ROW EXECUTE FUNCTION amafh_pipeline_active_only()
    """)
    op.create_table(
        "case_lifecycle_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("previous_status", sa.String(80)),
        sa.Column("status", sa.String(80), nullable=False),
        sa.Column(
            "actor_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index(
        "ix_case_lifecycle_case_time", "case_lifecycle_history", ["case_id", "occurred_at"]
    )
    op.execute("""
    CREATE TRIGGER protect_case_lifecycle_history BEFORE UPDATE OR DELETE
    ON case_lifecycle_history FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change()
    """)
    op.add_column("csv_import_batches", sa.Column("content_hash", sa.String(64)))
    op.create_index(
        "uq_csv_import_content",
        "csv_import_batches",
        ["kind", "uploaded_by_employee_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text("content_hash IS NOT NULL"),
    )
    op.create_index("ix_cases_coordinator", "cases", ["coordinator_employee_id", "current_status"])
    op.create_index("ix_cases_created", "cases", ["created_at"])


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
