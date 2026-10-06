"""Guard Phase 1 scope, context, canonical identity, and current ownership.

Revision ID: 20260926integrity
Revises: 20260925versions
"""

from alembic import op

revision = "20260926integrity"
down_revision = "20260925versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_department_id_branch", "departments", ["id", "branch_id"])
    op.create_unique_constraint(
        "uq_variant_id_context", "product_variants", ["id", "bank_id", "product_type_id"]
    )
    op.create_unique_constraint(
        "uq_pipeline_id_context", "pipeline_configurations", ["id", "bank_id", "product_type_id"]
    )
    op.create_check_constraint(
        "ck_employee_assignment_pair",
        "employees",
        "(branch_id IS NULL AND department_id IS NULL) OR "
        "(branch_id IS NOT NULL AND department_id IS NOT NULL)",
    )
    for table, name in (
        ("employees", "fk_employee_department_branch"),
        ("employee_assignment_history", "fk_assignment_department_branch"),
        ("teams", "fk_team_department_branch"),
        ("targets", "fk_target_department_branch"),
        ("cases", "fk_case_department_branch"),
    ):
        op.create_foreign_key(
            name, table, "departments", ["department_id", "branch_id"], ["id", "branch_id"]
        )
    op.create_foreign_key(
        "fk_case_variant_context",
        "cases",
        "product_variants",
        ["product_variant_id", "bank_id", "product_type_id"],
        ["id", "bank_id", "product_type_id"],
    )
    op.create_foreign_key(
        "fk_case_pipeline_context",
        "cases",
        "pipeline_configurations",
        ["pipeline_configuration_id", "bank_id", "product_type_id"],
        ["id", "bank_id", "product_type_id"],
    )
    op.create_foreign_key(
        "fk_financial_rule_variant_context",
        "financial_rules",
        "product_variants",
        ["product_variant_id", "bank_id", "product_type_id"],
        ["id", "bank_id", "product_type_id"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_case_current_owner ON case_ownership_history (case_id) "
        "WHERE ended_at IS NULL"
    )
    for table, index, scope, column in (
        ("business_units", "uq_business_unit_name_canonical", "", "name"),
        ("branches", "uq_branch_name_canonical", "", "name"),
        ("departments", "uq_department_name_canonical", "branch_id, ", "name"),
        ("teams", "uq_team_name_canonical", "branch_id, department_id, ", "name"),
        ("employees", "uq_employee_company_employee_code_canonical", "", "company_employee_code"),
        ("employees", "uq_employee_passport_number_canonical", "", "passport_number"),
        ("employees", "uq_employee_emirates_id_number_canonical", "", "emirates_id_number"),
    ):
        transform = "upper" if table == "employees" else "lower"
        op.execute(
            f"CREATE UNIQUE INDEX {index} ON {table} "
            f"({scope}{transform}(regexp_replace(btrim({column}), '[[:space:]]+', ' ', 'g')))"
        )
    # The context advisory lock serializes overlapping PF-slab writes without an
    # additional PostgreSQL extension. Inclusive ranges cannot share an endpoint.
    op.execute("""
    CREATE FUNCTION amafh_reject_overlapping_pf_slab() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.active AND NEW.product_variant_id IS NULL THEN
        PERFORM pg_advisory_xact_lock(
          hashtextextended(NEW.bank_id::text || ':' || NEW.product_type_id::text, 0)
        );
        IF EXISTS (
          SELECT 1 FROM financial_rules existing
          WHERE existing.id <> NEW.id AND existing.active
            AND existing.product_variant_id IS NULL
            AND existing.bank_id = NEW.bank_id
            AND existing.product_type_id = NEW.product_type_id
            AND existing.pf_amount_min <= NEW.pf_amount_max
            AND existing.pf_amount_max >= NEW.pf_amount_min
        ) THEN
          RAISE EXCEPTION 'Overlapping active PF amount slab';
        END IF;
      END IF;
      RETURN NEW;
    END $$
    """)
    op.execute("""
    CREATE TRIGGER reject_overlapping_pf_slab
    BEFORE INSERT OR UPDATE ON financial_rules
    FOR EACH ROW EXECUTE FUNCTION amafh_reject_overlapping_pf_slab()
    """)


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
