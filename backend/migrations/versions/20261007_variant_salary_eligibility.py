"""Explicit Variant salary criteria, current Customer salary and immutable Case salary.

Existing records retain NULL values; no salary or eligibility is inferred.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261007variantsalary"
down_revision = "20261007holidays"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("salary_aed", sa.Numeric(18, 0), nullable=True))
    op.create_check_constraint(
        "ck_customer_salary_nonnegative", "customers", "salary_aed IS NULL OR salary_aed >= 0"
    )
    op.add_column("cases", sa.Column("salary_aed", sa.Numeric(18, 0), nullable=True))
    op.create_check_constraint(
        "ck_case_salary_nonnegative", "cases", "salary_aed IS NULL OR salary_aed >= 0"
    )
    op.add_column(
        "product_variants", sa.Column("minimum_salary_aed", sa.Numeric(18, 0), nullable=True)
    )
    op.add_column(
        "product_variants", sa.Column("maximum_salary_aed", sa.Numeric(18, 0), nullable=True)
    )
    op.create_check_constraint(
        "ck_variant_salary_range",
        "product_variants",
        "(minimum_salary_aed IS NULL AND maximum_salary_aed IS NULL) OR "
        "(minimum_salary_aed IS NOT NULL AND maximum_salary_aed IS NOT NULL "
        "AND minimum_salary_aed >= 0 AND maximum_salary_aed >= minimum_salary_aed)",
    )
    op.execute("""
    CREATE FUNCTION amafh_guard_case_salary() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.salary_aed IS DISTINCT FROM OLD.salary_aed THEN
        RAISE EXCEPTION 'Case salary snapshot is immutable';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_case_salary BEFORE UPDATE ON cases
    FOR EACH ROW EXECUTE FUNCTION amafh_guard_case_salary();
    """)


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only")
