"""Retain Asset lifecycle and guard issue, return, maintenance and offboarding.

Revision ID: 20260926p5asset
Revises: 20260926p5att
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260926p5asset"
down_revision = "20260926p5att"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE amafh_asset_code_seq START WITH 1 INCREMENT BY 1")
    op.execute("""
    DO $$ DECLARE floor_number bigint;
    BEGIN
      SELECT COALESCE(MAX(substring(asset_code FROM 5)::bigint), 0)
        INTO floor_number FROM assets WHERE asset_code ~ '^AST-[0-9]{6,}$';
      IF floor_number > 0 THEN
        PERFORM setval('amafh_asset_code_seq', floor_number, true);
      END IF;
    END $$;
    """)
    op.add_column("assets", sa.Column("created_by_employee_id", UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_asset_created_by",
        "assets",
        "employees",
        ["created_by_employee_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("assets_check", "assets", type_="check")
    op.create_check_constraint(
        "ck_asset_category",
        "assets",
        "created_by_employee_id IS NULL OR "
        "category IN ('Mobile Phone','SIM Card','PC','Laptop','Other')",
    )
    op.create_check_constraint(
        "ck_asset_status",
        "assets",
        "created_by_employee_id IS NULL OR "
        "status IN ('Available','Issued','Needs Maintenance','Maintenance','Damaged')",
    )
    op.create_check_constraint(
        "ck_asset_required_text",
        "assets",
        "created_by_employee_id IS NULL OR (length(btrim(asset_code)) > 0 "
        "AND length(btrim(brand)) > 0 AND length(btrim(model)) > 0 "
        "AND length(btrim(serial_number)) > 0)",
    )
    op.create_check_constraint(
        "ck_asset_sim_fields",
        "assets",
        "created_by_employee_id IS NULL OR ((category = 'SIM Card' AND mobile_number IS NOT NULL "
        "AND length(btrim(mobile_number)) > 0 AND operator_provider IS NOT NULL "
        "AND length(btrim(operator_provider)) > 0) OR "
        "(category <> 'SIM Card' AND mobile_number IS NULL AND operator_provider IS NULL))",
    )
    op.create_index(
        "uq_asset_serial_canonical",
        "assets",
        [sa.text("upper(btrim(serial_number))")],
        unique=True,
        postgresql_where=sa.text("created_by_employee_id IS NOT NULL"),
    )
    op.create_index("ix_asset_branch_status", "assets", ["branch_id", "status"])
    op.add_column("asset_assignments", sa.Column("issued_by_employee_id", UUID(as_uuid=True)))
    op.add_column("asset_assignments", sa.Column("returned_by_employee_id", UUID(as_uuid=True)))
    op.add_column(
        "asset_assignments",
        sa.Column(
            "duration_days", sa.Integer(), sa.Computed("return_date - issue_date", persisted=True)
        ),
    )
    for name in ("issued_by_employee_id", "returned_by_employee_id"):
        op.create_foreign_key(
            f"fk_asset_assignment_{name}",
            "asset_assignments",
            "employees",
            [name],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_check_constraint(
        "ck_asset_assignment_return",
        "asset_assignments",
        "(issued_by_employee_id IS NULL AND returned_by_employee_id IS NULL) OR "
        "(return_date IS NULL AND return_reason IS NULL AND condition_on_return IS NULL "
        "AND returned_by_employee_id IS NULL) OR (return_date IS NOT NULL "
        "AND return_date >= issue_date AND (returned_by_employee_id IS NULL OR "
        "(return_reason IS NOT NULL AND length(btrim(return_reason)) > 0 "
        "AND condition_on_return IN ('Available','Needs Maintenance','Damaged'))))",
    )
    op.create_index(
        "ix_asset_assignment_employee", "asset_assignments", ["employee_id", "issue_date"]
    )
    for name in ("started_by_employee_id", "completed_by_employee_id"):
        op.add_column("asset_maintenance_history", sa.Column(name, UUID(as_uuid=True)))
        op.create_foreign_key(
            f"fk_asset_maintenance_{name}",
            "asset_maintenance_history",
            "employees",
            [name],
            ["id"],
            ondelete="RESTRICT",
        )
    op.add_column("asset_maintenance_history", sa.Column("completion_notes", sa.Text()))
    op.add_column(
        "asset_maintenance_history",
        sa.Column(
            "duration_days",
            sa.Integer(),
            sa.Computed("completion_date - start_date", persisted=True),
        ),
    )
    op.create_index(
        "uq_asset_open_maintenance",
        "asset_maintenance_history",
        ["asset_id"],
        unique=True,
        postgresql_where=sa.text("completion_date IS NULL"),
    )
    op.create_check_constraint(
        "ck_asset_maintenance_notes",
        "asset_maintenance_history",
        "started_by_employee_id IS NULL OR (notes IS NOT NULL AND length(btrim(notes)) > 0)",
    )
    op.create_check_constraint(
        "ck_asset_maintenance_completion",
        "asset_maintenance_history",
        "(started_by_employee_id IS NULL AND completed_by_employee_id IS NULL) OR "
        "(completion_date IS NULL AND resulting_status IS NULL "
        "AND completed_by_employee_id IS NULL) OR (completion_date IS NOT NULL "
        "AND completion_date >= start_date AND (completed_by_employee_id IS NULL OR "
        "resulting_status IN ('Available','Damaged')))",
    )
    op.create_table(
        "asset_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "asset_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("previous_status", sa.String(30)),
        sa.Column("new_status", sa.String(30), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column(
            "employee_id", UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="RESTRICT")
        ),
        sa.Column(
            "actor_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assignment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("asset_assignments.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "maintenance_id",
            UUID(as_uuid=True),
            sa.ForeignKey("asset_maintenance_history.id", ondelete="RESTRICT"),
        ),
        sa.Column("reason", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "action IN ('Created','Issued','Returned','Maintenance Started',"
            "'Maintenance Completed','Damaged')",
            name="ck_asset_history_action",
        ),
    )
    op.create_index("ix_asset_history_asset_date", "asset_history", ["asset_id", "effective_date"])
    op.execute("DROP TRIGGER protect_asset_assignments_update ON asset_assignments")
    op.execute("DROP TRIGGER protect_asset_maintenance_history_update ON asset_maintenance_history")
    op.execute("""
    CREATE TRIGGER protect_asset_history BEFORE UPDATE OR DELETE ON asset_history
      FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change();
    CREATE FUNCTION amafh_guard_asset() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Asset history is retained'; END IF;
      IF TG_OP = 'INSERT' THEN
        IF NEW.created_by_employee_id IS NULL
        THEN RAISE EXCEPTION 'Asset creator is required'; END IF;
        PERFORM pg_advisory_xact_lock(
          hashtextextended('asset_serial:' || upper(btrim(NEW.serial_number)), 0));
        IF EXISTS (SELECT 1 FROM assets
                   WHERE upper(btrim(serial_number)) = upper(btrim(NEW.serial_number)))
        THEN RAISE EXCEPTION 'Asset Serial Number conflicts'; END IF;
        IF NEW.status <> 'Available' THEN RAISE EXCEPTION 'New Asset must be Available'; END IF;
        RETURN NEW;
      END IF;
      IF (to_jsonb(NEW) - 'status' - 'updated_at') IS DISTINCT FROM
         (to_jsonb(OLD) - 'status' - 'updated_at')
      THEN RAISE EXCEPTION 'Asset identity is immutable'; END IF;
      IF OLD.status = 'Damaged' AND NEW.status <> 'Damaged'
      THEN RAISE EXCEPTION 'Damaged Asset is permanent'; END IF;
      IF NEW.status = 'Needs Maintenance' AND OLD.status <> 'Issued'
      THEN RAISE EXCEPTION 'Needs Maintenance requires recorded return'; END IF;
      IF NEW.status = 'Damaged' AND OLD.status IN ('Available','Needs Maintenance')
         AND NOT EXISTS (SELECT 1 FROM asset_history h JOIN audit_events e
           ON e.entity_id = NEW.id::text AND e.action = 'asset.damaged'
           WHERE h.asset_id = NEW.id AND h.action = 'Damaged'
             AND h.previous_status = OLD.status)
      THEN RAISE EXCEPTION 'Damage requires history and audit'; END IF;
      IF NEW.status = 'Issued' AND NOT EXISTS (
        SELECT 1 FROM asset_assignments WHERE asset_id = NEW.id AND return_date IS NULL)
      THEN RAISE EXCEPTION 'Issued Asset requires open assignment'; END IF;
      IF NEW.status <> 'Issued' AND EXISTS (
        SELECT 1 FROM asset_assignments WHERE asset_id = NEW.id AND return_date IS NULL)
      THEN RAISE EXCEPTION 'Open assignment requires Issued Asset'; END IF;
      IF NEW.status = 'Maintenance' AND NOT EXISTS (
        SELECT 1 FROM asset_maintenance_history WHERE asset_id = NEW.id AND completion_date IS NULL)
      THEN RAISE EXCEPTION 'Maintenance requires open record'; END IF;
      IF NEW.status <> 'Maintenance' AND EXISTS (
        SELECT 1 FROM asset_maintenance_history WHERE asset_id = NEW.id AND completion_date IS NULL)
      THEN RAISE EXCEPTION 'Open maintenance requires Maintenance status'; END IF;
      IF OLD.status = 'Needs Maintenance' AND NEW.status = 'Available'
      THEN RAISE EXCEPTION 'Complete maintenance before availability'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_asset BEFORE INSERT OR UPDATE OR DELETE ON assets
      FOR EACH ROW EXECUTE FUNCTION amafh_guard_asset();
    CREATE FUNCTION amafh_guard_asset_assignment() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE asset_branch uuid; asset_status text; employee_branch uuid; employee_status text;
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Asset assignment history is retained'; END IF;
      IF TG_OP = 'INSERT' THEN
        SELECT branch_id, status INTO asset_branch, asset_status FROM assets
          WHERE id = NEW.asset_id FOR UPDATE;
        SELECT branch_id, status INTO employee_branch, employee_status FROM employees
          WHERE id = NEW.employee_id FOR SHARE;
        IF asset_status <> 'Available' OR employee_status <> 'Active'
           OR employee_branch IS DISTINCT FROM asset_branch
           OR NEW.return_date IS NOT NULL
        THEN RAISE EXCEPTION 'Asset issue context invalid'; END IF;
        RETURN NEW;
      END IF;
      IF OLD.return_date IS NOT NULL OR NEW.return_date IS NULL
         OR (to_jsonb(NEW) - 'return_date' - 'return_reason' - 'condition_on_return'
             - 'returned_by_employee_id' - 'duration_days') IS DISTINCT FROM
            (to_jsonb(OLD) - 'return_date' - 'return_reason' - 'condition_on_return'
             - 'returned_by_employee_id' - 'duration_days')
      THEN RAISE EXCEPTION 'Asset assignment history is immutable'; END IF;
      RETURN NEW;
    END $$;
    CREATE FUNCTION amafh_sync_asset_assignment() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      UPDATE assets SET status = CASE WHEN TG_OP = 'INSERT' THEN 'Issued'
                                  ELSE NEW.condition_on_return END,
        updated_at = now() WHERE id = NEW.asset_id;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_asset_assignment BEFORE INSERT OR UPDATE OR DELETE ON asset_assignments
      FOR EACH ROW EXECUTE FUNCTION amafh_guard_asset_assignment();
    CREATE TRIGGER sync_asset_assignment AFTER INSERT OR UPDATE ON asset_assignments
      FOR EACH ROW EXECUTE FUNCTION amafh_sync_asset_assignment();
    CREATE FUNCTION amafh_guard_asset_maintenance() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE asset_status text;
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Asset maintenance history is retained'; END IF;
      IF TG_OP = 'INSERT' THEN
        SELECT status INTO asset_status FROM assets WHERE id = NEW.asset_id FOR UPDATE;
        IF asset_status NOT IN ('Available','Needs Maintenance') OR NEW.completion_date IS NOT NULL
        THEN RAISE EXCEPTION 'Asset maintenance context invalid'; END IF;
        RETURN NEW;
      END IF;
      IF OLD.completion_date IS NOT NULL OR NEW.completion_date IS NULL
         OR (to_jsonb(NEW) - 'completion_date' - 'resulting_status'
             - 'completed_by_employee_id' - 'completion_notes' - 'duration_days') IS DISTINCT FROM
            (to_jsonb(OLD) - 'completion_date' - 'resulting_status'
             - 'completed_by_employee_id' - 'completion_notes' - 'duration_days')
      THEN RAISE EXCEPTION 'Asset maintenance history is immutable'; END IF;
      RETURN NEW;
    END $$;
    CREATE FUNCTION amafh_sync_asset_maintenance() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      UPDATE assets SET status = CASE WHEN TG_OP = 'INSERT' THEN 'Maintenance'
                                  ELSE NEW.resulting_status END,
        updated_at = now() WHERE id = NEW.asset_id;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_asset_maintenance
      BEFORE INSERT OR UPDATE OR DELETE ON asset_maintenance_history
      FOR EACH ROW EXECUTE FUNCTION amafh_guard_asset_maintenance();
    CREATE TRIGGER sync_asset_maintenance AFTER INSERT OR UPDATE ON asset_maintenance_history
      FOR EACH ROW EXECUTE FUNCTION amafh_sync_asset_maintenance();
    CREATE FUNCTION amafh_guard_offboard_assets() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.status = 'Offboarded' AND OLD.status IS DISTINCT FROM 'Offboarded'
         AND EXISTS (SELECT 1 FROM asset_assignments WHERE employee_id = NEW.id
                     AND return_date IS NULL)
      THEN RAISE EXCEPTION 'Issued Assets must be returned before offboarding'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_offboard_assets BEFORE UPDATE OF status ON employees
      FOR EACH ROW EXECUTE FUNCTION amafh_guard_offboard_assets();
    """)


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
