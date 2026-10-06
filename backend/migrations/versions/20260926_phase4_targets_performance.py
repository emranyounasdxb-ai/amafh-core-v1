"""Guard effective Target versions and retain Phase 4 calendar and ranking facts.

Revision ID: 20260926phase4
Revises: 20260926finretry
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260926phase4"
down_revision = "20260926finretry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("targets", sa.Column("inactive_from_date", sa.Date()))
    op.add_column("targets", sa.Column("superseded_by_target_id", UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_targets_successor",
        "targets",
        "targets",
        ["superseded_by_target_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("ck_targets_one_typed_value", "targets", type_="check")
    op.create_check_constraint(
        "ck_targets_one_typed_value",
        "targets",
        "(target_points IS NOT NULL AND target_amount_aed IS NULL AND target_points > 0) "
        "OR (target_points IS NULL AND target_amount_aed IS NOT NULL AND target_amount_aed > 0)",
    )
    op.create_check_constraint(
        "ck_targets_effective_state",
        "targets",
        "(active AND inactive_from_date IS NULL AND superseded_by_target_id IS NULL) "
        "OR (NOT active AND inactive_from_date IS NOT NULL)",
    )
    op.execute("DROP TRIGGER protect_targets ON targets")
    op.execute("""
    CREATE FUNCTION amafh_guard_target_version() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE department_name text;
    DECLARE today_dubai date := (now() AT TIME ZONE 'Asia/Dubai')::date;
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Target history is immutable'; END IF;
      IF TG_OP = 'UPDATE' THEN
        IF (to_jsonb(NEW) - 'active' - 'inactive_from_date' - 'superseded_by_target_id')
           IS DISTINCT FROM
           (to_jsonb(OLD) - 'active' - 'inactive_from_date' - 'superseded_by_target_id')
           OR OLD.superseded_by_target_id IS NOT NULL
           OR (OLD.active = FALSE AND NEW.active = TRUE)
           OR (OLD.inactive_from_date IS NOT NULL
               AND NEW.inactive_from_date IS DISTINCT FROM OLD.inactive_from_date)
           OR (OLD.active = TRUE AND NEW.active = FALSE
               AND (NEW.inactive_from_date IS NULL
                    OR NEW.inactive_from_date < today_dubai
                    OR NEW.inactive_from_date < OLD.effective_date))
           OR (OLD.active = FALSE AND
               (NEW.active IS DISTINCT FROM OLD.active
                OR NEW.inactive_from_date IS DISTINCT FROM OLD.inactive_from_date
                OR NEW.superseded_by_target_id IS NULL))
        THEN RAISE EXCEPTION 'Target history is immutable'; END IF;
        IF NEW.superseded_by_target_id IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM targets successor WHERE successor.id = NEW.superseded_by_target_id
          AND successor.branch_id = OLD.branch_id
          AND successor.department_id = OLD.department_id
          AND successor.designation_id = OLD.designation_id
          AND successor.effective_date = NEW.inactive_from_date
        ) THEN RAISE EXCEPTION 'Invalid Target successor'; END IF;
        RETURN NEW;
      END IF;
      IF NEW.active IS DISTINCT FROM TRUE OR NEW.inactive_from_date IS NOT NULL
         OR NEW.superseded_by_target_id IS NOT NULL
         OR NEW.effective_date < today_dubai
      THEN RAISE EXCEPTION 'New Target version must start active'; END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended(
        NEW.branch_id::text || NEW.department_id::text || NEW.designation_id::text, 0));
      SELECT d.name INTO department_name FROM departments d JOIN branches b
        ON b.id = d.branch_id WHERE d.id = NEW.department_id
        AND d.branch_id = NEW.branch_id AND d.active AND b.active FOR SHARE OF d, b;
      IF department_name IS NULL OR NOT EXISTS (
          SELECT 1 FROM designation_user_types des
          WHERE des.id = NEW.designation_id AND des.locked
      ) THEN RAISE EXCEPTION 'Inactive Target context'; END IF;
      IF (department_name = 'Credit Card Sales' AND
          (NEW.target_points IS NULL OR NEW.target_amount_aed IS NOT NULL))
         OR (department_name = 'Personal Finance Sales' AND
          (NEW.target_amount_aed IS NULL OR NEW.target_points IS NOT NULL))
         OR department_name NOT IN ('Credit Card Sales', 'Personal Finance Sales')
      THEN RAISE EXCEPTION 'Target type does not match Department'; END IF;
      IF EXISTS (
          SELECT 1 FROM targets t WHERE t.branch_id = NEW.branch_id
          AND t.department_id = NEW.department_id
          AND t.designation_id = NEW.designation_id
          AND t.effective_date < 'infinity'::date
          AND (t.inactive_from_date IS NULL OR t.inactive_from_date > NEW.effective_date)
      ) THEN RAISE EXCEPTION 'Target effective periods overlap'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_target_version BEFORE INSERT OR UPDATE OR DELETE ON targets
    FOR EACH ROW EXECUTE FUNCTION amafh_guard_target_version();
    """)
    op.create_table(
        "uae_public_holidays",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("holiday_date", sa.Date(), nullable=False, unique=True),
        sa.Column("applicable_year", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column(
            "created_by_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("applicable_year = EXTRACT(YEAR FROM holiday_date)"),
        sa.CheckConstraint("length(btrim(name)) > 0 AND length(btrim(source_reference)) > 0"),
    )
    op.create_table(
        "uae_holiday_year_certifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("applicable_year", sa.Integer(), nullable=False, unique=True),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column(
            "certified_by_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("applicable_year BETWEEN 1900 AND 9999"),
        sa.CheckConstraint("length(btrim(source_reference)) > 0"),
    )
    op.execute("""
    CREATE FUNCTION amafh_guard_holiday_date() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      PERFORM pg_advisory_xact_lock(hashtextextended(
        'uae_holidays:' || NEW.applicable_year::text, 0));
      IF EXISTS (SELECT 1 FROM uae_holiday_year_certifications
                 WHERE applicable_year = NEW.applicable_year)
      THEN RAISE EXCEPTION 'Certified holiday year is immutable'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_holiday_date BEFORE INSERT ON uae_public_holidays
    FOR EACH ROW EXECUTE FUNCTION amafh_guard_holiday_date();
    CREATE FUNCTION amafh_guard_holiday_certification() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      PERFORM pg_advisory_xact_lock(hashtextextended(
        'uae_holidays:' || NEW.applicable_year::text, 0));
      IF NOT EXISTS (SELECT 1 FROM uae_public_holidays
                     WHERE applicable_year = NEW.applicable_year)
      THEN RAISE EXCEPTION 'Holiday year requires official dates'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_holiday_certification BEFORE INSERT ON uae_holiday_year_certifications
    FOR EACH ROW EXECUTE FUNCTION amafh_guard_holiday_certification();
    """)
    op.add_column(
        "notifications",
        sa.Column(
            "available_on",
            sa.Date(),
            nullable=False,
            server_default=sa.text("(now() AT TIME ZONE 'Asia/Dubai')::date"),
        ),
    )
    for table in ("uae_public_holidays", "uae_holiday_year_certifications"):
        op.execute(
            f"CREATE TRIGGER protect_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change()"
        )
    op.create_table(
        "ranking_confirmations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("context_key", sa.String(64), nullable=False, unique=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column(
            "branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="RESTRICT")
        ),
        sa.Column(
            "department_id",
            UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
        ),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="RESTRICT")),
        sa.Column(
            "designation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("designation_user_types.id", ondelete="RESTRICT"),
        ),
        sa.Column("product_code", sa.String(2), nullable=False),
        sa.Column("eligible_candidate_ids", sa.Text(), nullable=False),
        sa.Column(
            "selected_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "confirmed_by_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("period_start <= period_end"),
        sa.CheckConstraint("product_code IN ('CC','PF')"),
    )
    op.execute(
        "CREATE TRIGGER protect_ranking_confirmations BEFORE UPDATE OR DELETE ON "
        "ranking_confirmations FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change()"
    )


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
