"""Immutable salary-range points inside a CC financial-rule version."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261017ccsalary"
down_revision = "20261017callsuggest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # JSON stays on the already immutable parent row: no mutable child rows can
    # be appended after a rule has been used. Existing rules keep empty slabs.
    op.add_column(
        "financial_rules",
        sa.Column("cc_salary_points", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.execute("""
    CREATE FUNCTION amafh_valid_cc_salary_points(slabs jsonb)
    RETURNS boolean LANGUAGE plpgsql IMMUTABLE AS $$
    DECLARE row jsonb; lower_salary numeric; upper_salary numeric; previous_max numeric := -1;
    BEGIN
      IF jsonb_typeof(slabs) IS DISTINCT FROM 'array' THEN RETURN false; END IF;
      IF jsonb_array_length(slabs) > 100 THEN RETURN false; END IF;
      FOR row IN SELECT value FROM jsonb_array_elements(slabs) LOOP
        IF jsonb_typeof(row) IS DISTINCT FROM 'object'
          OR row - ARRAY['salaryMin','salaryMax','points'] <> '{}'::jsonb
          OR jsonb_typeof(row->'salaryMin') IS DISTINCT FROM 'string'
          OR jsonb_typeof(row->'salaryMax') IS DISTINCT FROM 'string'
          OR jsonb_typeof(row->'points') IS DISTINCT FROM 'number'
          OR (row->>'salaryMin') !~ '^[0-9]{1,18}$'
          OR (row->>'salaryMax') !~ '^[0-9]{1,18}$'
          OR (row->>'points') !~ '^[0-9]{1,10}$'
        THEN RETURN false; END IF;
        lower_salary := (row->>'salaryMin')::numeric;
        upper_salary := (row->>'salaryMax')::numeric;
        IF lower_salary > upper_salary OR lower_salary <= previous_max
          OR (row->>'points')::numeric < 1 OR (row->>'points')::numeric > 2147483647
        THEN RETURN false; END IF;
        previous_max := upper_salary;
      END LOOP;
      RETURN true;
    END $$;
    """)
    op.create_check_constraint(
        "ck_financial_rule_salary_points",
        "financial_rules",
        "amafh_valid_cc_salary_points(cc_salary_points) AND "
        "(cc_salary_points = '[]'::jsonb OR "
        "(product_variant_id IS NOT NULL AND cc_points IS NULL))",
    )
    op.drop_constraint("ck_financial_rule_values", "financial_rules", type_="check")
    op.create_check_constraint(
        "ck_financial_rule_values",
        "financial_rules",
        "(cc_points IS NULL OR cc_points > 0) AND "
        "(commission_aed IS NULL OR commission_aed >= 0) AND "
        "((product_variant_id IS NOT NULL AND "
        "(cc_points IS NOT NULL OR commission_aed IS NOT NULL "
        "OR cc_salary_points <> '[]'::jsonb)) OR "
        "(product_variant_id IS NULL AND pf_amount_min > 0 AND commission_aed IS NOT NULL))",
    )


def downgrade() -> None:
    # Refuse to erase configured financial history or leave unrepresentable rows.
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM financial_rules WHERE cc_salary_points <> '[]'::jsonb)
      THEN RAISE EXCEPTION 'Salary points history exists; downgrade would erase it'; END IF;
    END $$;""")
    op.drop_constraint("ck_financial_rule_values", "financial_rules", type_="check")
    op.create_check_constraint(
        "ck_financial_rule_values",
        "financial_rules",
        "(cc_points IS NULL OR cc_points > 0) AND "
        "(commission_aed IS NULL OR commission_aed >= 0) AND "
        "((product_variant_id IS NOT NULL AND "
        "(cc_points IS NOT NULL OR commission_aed IS NOT NULL)) OR "
        "(product_variant_id IS NULL AND pf_amount_min > 0 AND commission_aed IS NOT NULL))",
    )
    op.drop_constraint("ck_financial_rule_salary_points", "financial_rules", type_="check")
    op.drop_column("financial_rules", "cc_salary_points")
    op.execute("DROP FUNCTION amafh_valid_cc_salary_points(jsonb)")
