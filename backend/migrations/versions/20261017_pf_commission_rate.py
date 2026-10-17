"""PF commission rate and final approved/disbursed amount; preserve legacy history."""

import sqlalchemy as sa
from alembic import op

revision = "20261017pfrate"
down_revision = "20261017ccsalary"
branch_labels = None
depends_on = None

OLD_VALUES = (
    "(cc_points IS NULL OR cc_points > 0) AND "
    "(commission_aed IS NULL OR commission_aed >= 0) AND "
    "((product_variant_id IS NOT NULL AND "
    "(cc_points IS NOT NULL OR commission_aed IS NOT NULL "
    "OR cc_salary_points <> '[]'::jsonb)) OR "
    "(product_variant_id IS NULL AND pf_amount_min > 0 AND commission_aed IS NOT NULL))"
)
NEW_VALUES = (
    "(cc_points IS NULL OR cc_points > 0) AND "
    "(commission_aed IS NULL OR commission_aed >= 0) AND "
    "((product_variant_id IS NOT NULL AND "
    "(cc_points IS NOT NULL OR commission_aed IS NOT NULL "
    "OR cc_salary_points <> '[]'::jsonb)) OR "
    "(product_variant_id IS NULL AND pf_amount_min > 0 AND cc_points IS NULL "
    "AND (commission_aed IS NOT NULL OR pf_commission_per_1000 IS NOT NULL)))"
)


def upgrade() -> None:
    op.add_column("financial_rules", sa.Column("pf_commission_per_1000", sa.Numeric(18, 0)))
    op.create_check_constraint(
        "ck_financial_rule_pf_rate",
        "financial_rules",
        "pf_commission_per_1000 IS NULL OR "
        "(product_variant_id IS NULL AND pf_commission_per_1000 >= 0 "
        "AND commission_aed IS NULL AND cc_points IS NULL)",
    )
    op.drop_constraint("ck_financial_rule_values", "financial_rules", type_="check")
    op.create_check_constraint("ck_financial_rule_values", "financial_rules", NEW_VALUES)
    op.add_column("cases", sa.Column("final_pf_amount", sa.Numeric(18, 0)))
    op.create_check_constraint(
        "ck_case_final_pf_amount",
        "cases",
        "final_pf_amount IS NULL OR final_pf_amount > 0",
    )
    op.add_column("csv_import_row_results", sa.Column("final_pf_amount", sa.Numeric(18, 0)))
    op.add_column("case_financial_results", sa.Column("pf_commission_per_1000", sa.Numeric(18, 0)))
    op.add_column("case_financial_results", sa.Column("pf_amount_basis", sa.String(32)))
    op.create_check_constraint(
        "ck_financial_result_pf_rate",
        "case_financial_results",
        "(pf_amount_basis IS NULL AND pf_commission_per_1000 IS NULL) OR "
        "(pf_amount_basis IS NOT NULL AND pf_amount_basis = 'final_approved_disbursed' "
        "AND product_code = 'PF' "
        "AND cc_points IS NULL AND pf_amount_aed IS NOT NULL AND pf_amount_aed > 0 "
        "AND pf_commission_per_1000 IS NOT NULL AND pf_commission_per_1000 >= 0 "
        "AND commission_aed IS NOT NULL "
        "AND commission_aed = round(pf_amount_aed * pf_commission_per_1000 / 1000))",
    )
    # No backfill: requested amounts and historical flat commissions are not
    # evidence of final funding or a per-1,000 rate.


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM financial_rules WHERE pf_commission_per_1000 IS NOT NULL)
        OR EXISTS (SELECT 1 FROM cases WHERE final_pf_amount IS NOT NULL)
        OR EXISTS (SELECT 1 FROM csv_import_row_results WHERE final_pf_amount IS NOT NULL)
        OR EXISTS (SELECT 1 FROM case_financial_results WHERE pf_amount_basis IS NOT NULL
                   OR pf_commission_per_1000 IS NOT NULL)
      THEN RAISE EXCEPTION 'PF rate/final amount history exists; downgrade would erase it'; END IF;
    END $$;""")
    op.drop_constraint("ck_financial_result_pf_rate", "case_financial_results", type_="check")
    op.drop_column("case_financial_results", "pf_amount_basis")
    op.drop_column("case_financial_results", "pf_commission_per_1000")
    op.drop_column("csv_import_row_results", "final_pf_amount")
    op.drop_constraint("ck_case_final_pf_amount", "cases", type_="check")
    op.drop_column("cases", "final_pf_amount")
    op.drop_constraint("ck_financial_rule_values", "financial_rules", type_="check")
    op.create_check_constraint("ck_financial_rule_values", "financial_rules", OLD_VALUES)
    op.drop_constraint("ck_financial_rule_pf_rate", "financial_rules", type_="check")
    op.drop_column("financial_rules", "pf_commission_per_1000")
