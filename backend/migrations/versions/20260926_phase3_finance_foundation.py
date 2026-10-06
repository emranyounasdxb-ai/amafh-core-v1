"""Retain immutable Phase 3 finance evidence and guard financial contexts.

Revision ID: 20260926finance
Revises: 20260926bankroute
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260926finance"
down_revision = "20260926bankroute"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing Phase 1/2 schemas did not write these records. Never invent a
    # historical actor, clawback reason, or payment context during upgrade.
    op.execute("""
    DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM clawbacks) OR EXISTS (SELECT 1 FROM payment_records) THEN
        RAISE EXCEPTION 'Review pre-existing Finance records before Phase 3 migration';
      END IF;
    END $$
    """)
    op.add_column(
        "financial_rules",
        sa.Column(
            "superseded_by_rule_id",
            UUID(as_uuid=True),
            sa.ForeignKey("financial_rules.id", ondelete="RESTRICT"),
        ),
    )
    op.add_column("clawbacks", sa.Column("clawback_date", sa.Date(), nullable=False))
    op.add_column("clawbacks", sa.Column("reason", sa.Text(), nullable=False))
    op.add_column(
        "clawbacks",
        sa.Column(
            "created_by_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    op.add_column(
        "payment_records",
        sa.Column(
            "created_by_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    op.create_table(
        "case_financial_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "financial_rule_id",
            UUID(as_uuid=True),
            sa.ForeignKey("financial_rules.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "credited_owner_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("product_code", sa.String(2), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cc_points", sa.Integer()),
        sa.Column("commission_aed", sa.Numeric(18, 2)),
        sa.Column("pf_amount_aed", sa.Numeric(18, 2)),
        sa.Column("rule_effective_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("product_code IN ('CC','PF')"),
        sa.CheckConstraint("cc_points IS NULL OR cc_points > 0"),
    )
    op.create_index(
        "ix_case_financial_results_owner_time",
        "case_financial_results",
        ["credited_owner_employee_id", "completed_at"],
    )
    op.create_check_constraint("ck_clawback_positive", "clawbacks", "amount_aed > 0")
    op.create_check_constraint("ck_clawback_reason", "clawbacks", "length(btrim(reason)) > 0")
    op.create_check_constraint("ck_payment_positive", "payment_records", "amount_aed > 0")
    op.create_check_constraint(
        "ck_payment_month_start", "payment_records", "EXTRACT(DAY FROM payment_month) = 1"
    )
    op.create_check_constraint(
        "ck_financial_rule_values",
        "financial_rules",
        "(cc_points IS NULL OR cc_points > 0) AND "
        "(commission_aed IS NULL OR commission_aed >= 0) AND "
        "((product_variant_id IS NOT NULL AND "
        "(cc_points IS NOT NULL OR commission_aed IS NOT NULL)) OR "
        "(product_variant_id IS NULL AND pf_amount_min > 0 AND commission_aed IS NOT NULL))",
    )
    op.create_index(
        "uq_cc_rule_effective_version",
        "financial_rules",
        ["bank_id", "product_variant_id", "effective_date"],
        unique=True,
        postgresql_where=sa.text("product_variant_id IS NOT NULL"),
    )
    op.create_index(
        "uq_pf_rule_effective_version",
        "financial_rules",
        ["bank_id", "product_type_id", "pf_amount_min", "pf_amount_max", "effective_date"],
        unique=True,
        postgresql_where=sa.text("product_variant_id IS NULL"),
    )
    # Phase 1 already installed the inclusive PF-overlap advisory-lock trigger.
    # Replace only its rule-history guard; the older guard permits deactivation
    # once but cannot record the successor or reactivate a nonhistorical rule.
    op.execute("DROP TRIGGER protect_financial_rules ON financial_rules")
    op.execute("""
    CREATE FUNCTION amafh_guard_financial_rule_history() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Financial Rule history is immutable'; END IF;
      IF (to_jsonb(NEW) - 'active' - 'superseded_by_rule_id')
        IS DISTINCT FROM (to_jsonb(OLD) - 'active' - 'superseded_by_rule_id')
        OR (OLD.superseded_by_rule_id IS NOT NULL
            AND NEW.superseded_by_rule_id IS DISTINCT FROM OLD.superseded_by_rule_id)
        OR (NEW.superseded_by_rule_id IS NOT NULL AND NEW.active) THEN
        RAISE EXCEPTION 'Financial Rule history is immutable';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_financial_rule_history
    BEFORE UPDATE OR DELETE ON financial_rules
    FOR EACH ROW EXECUTE FUNCTION amafh_guard_financial_rule_history();
    """)
    op.execute("""
    CREATE FUNCTION amafh_protect_finance_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      RAISE EXCEPTION 'Financial history is immutable';
    END $$;
    """)
    for table in (
        "case_financial_results",
        "points_wallets",
    ):
        op.execute(
            f"CREATE TRIGGER protect_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION amafh_protect_finance_evidence()"
        )


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
