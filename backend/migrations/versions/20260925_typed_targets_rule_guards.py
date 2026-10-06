"""Use integer CC targets and guard active financial-rule contexts.

Revision ID: 20260925rules
Revises: 20260925hist
"""

import sqlalchemy as sa
from alembic import op

revision = "20260925rules"
down_revision = "20260925hist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase 1 has no Target or Financial Rule write service. Refuse to infer the
    # product type of any manually inserted records during this type correction.
    op.execute("""
    DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM targets) OR EXISTS (SELECT 1 FROM financial_rules) THEN
        RAISE EXCEPTION 'Review existing target and financial rule data before migration';
      END IF;
    END $$
    """)
    op.alter_column(
        "targets",
        "target_value",
        new_column_name="target_amount_aed",
        existing_type=sa.Numeric(18, 2),
        nullable=True,
    )
    op.add_column("targets", sa.Column("target_points", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_targets_one_typed_value",
        "targets",
        "(target_points IS NOT NULL AND target_amount_aed IS NULL AND target_points >= 0) "
        "OR (target_points IS NULL AND target_amount_aed IS NOT NULL AND target_amount_aed >= 0)",
    )
    op.create_check_constraint(
        "ck_financial_rule_context",
        "financial_rules",
        "(product_variant_id IS NOT NULL AND pf_amount_min IS NULL AND pf_amount_max IS NULL) "
        "OR (product_variant_id IS NULL AND pf_amount_min IS NOT NULL "
        "AND pf_amount_max IS NOT NULL AND pf_amount_min <= pf_amount_max)",
    )
    op.create_index(
        "uq_active_cc_financial_rule",
        "financial_rules",
        ["bank_id", "product_variant_id"],
        unique=True,
        postgresql_where=sa.text("active AND product_variant_id IS NOT NULL"),
    )
    op.create_index(
        "uq_active_pf_financial_rule_slab",
        "financial_rules",
        ["bank_id", "product_type_id", "pf_amount_min", "pf_amount_max"],
        unique=True,
        postgresql_where=sa.text(
            "active AND product_variant_id IS NULL AND pf_amount_min IS NOT NULL "
            "AND pf_amount_max IS NOT NULL"
        ),
    )


def downgrade() -> None:
    raise RuntimeError("Forward-only target and financial-rule integrity migration")
