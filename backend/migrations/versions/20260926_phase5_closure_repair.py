"""Require committed Asset lifecycle evidence while retaining legacy records.

Revision ID: 20260926p5repair
Revises: 20260926p5asset
"""

from alembic import op

revision = "20260926p5repair"
down_revision = "20260926p5asset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # These constraints were made legacy-aware in the Phase 5 migration for new
    # installs. Replace the earlier form on databases already at that head.
    op.drop_constraint("ck_asset_assignment_return", "asset_assignments", type_="check")
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
    op.drop_constraint("ck_asset_maintenance_notes", "asset_maintenance_history", type_="check")
    op.create_check_constraint(
        "ck_asset_maintenance_notes",
        "asset_maintenance_history",
        "started_by_employee_id IS NULL OR (notes IS NOT NULL AND length(btrim(notes)) > 0)",
    )
    op.drop_constraint(
        "ck_asset_maintenance_completion", "asset_maintenance_history", type_="check"
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
    op.drop_constraint("ck_attendance_batch_evidence", "csv_import_batches", type_="check")
    op.create_check_constraint(
        "ck_attendance_batch_evidence",
        "csv_import_batches",
        "kind <> 'attendance' OR branch_id IS NULL OR (byte_size IS NOT NULL "
        "AND data_row_count IS NOT NULL AND applied_count IS NOT NULL AND error_count IS NOT NULL)",
    )
    op.drop_constraint("ck_attendance_record_values", "attendance_records", type_="check")
    op.create_check_constraint(
        "ck_attendance_record_values",
        "attendance_records",
        "office_timing_id IS NULL OR (status = 'Present' AND check_in_time IS NOT NULL "
        "AND check_out_time IS NOT NULL AND check_out_time > check_in_time) OR "
        "(status = 'Absent' AND check_in_time IS NULL AND check_out_time IS NULL AND NOT is_late)",
    )
    op.execute("""
    CREATE FUNCTION amafh_guard_new_attendance_batch() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'UPDATE' AND OLD.kind = 'attendance' AND OLD.branch_id IS NULL
         AND NEW.kind = 'attendance' AND NEW.branch_id IS NULL
      THEN RETURN NEW; END IF;
      IF NEW.kind = 'attendance' AND (NEW.branch_id IS NULL OR NEW.byte_size IS NULL
          OR NEW.data_row_count IS NULL OR NEW.applied_count IS NULL OR NEW.error_count IS NULL)
      THEN RAISE EXCEPTION 'New Attendance batch requires complete Phase 5 evidence'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_new_attendance_batch BEFORE INSERT OR UPDATE ON csv_import_batches
      FOR EACH ROW EXECUTE FUNCTION amafh_guard_new_attendance_batch();

    """)
    op.execute("""
    CREATE OR REPLACE FUNCTION amafh_require_asset_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE required_action text; required_actor uuid; required_date date;
    DECLARE required_status text; required_previous text; target_asset uuid;
    BEGIN
      IF TG_TABLE_NAME = 'asset_assignments' THEN
        target_asset := NEW.asset_id;
        IF TG_OP = 'INSERT' THEN
          required_action := 'Issued'; required_actor := NEW.issued_by_employee_id;
          required_date := NEW.issue_date; required_status := 'Issued';
          required_previous := 'Available';
        ELSIF OLD.return_date IS NULL AND NEW.return_date IS NOT NULL THEN
          required_action := 'Returned'; required_actor := NEW.returned_by_employee_id;
          required_date := NEW.return_date; required_status := NEW.condition_on_return;
          required_previous := 'Issued';
        ELSE RETURN NEW; END IF;
      ELSIF TG_TABLE_NAME = 'asset_maintenance_history' THEN
        target_asset := NEW.asset_id;
        IF TG_OP = 'INSERT' THEN
          required_action := 'Maintenance Started'; required_actor := NEW.started_by_employee_id;
          required_date := NEW.start_date; required_status := 'Maintenance';
        ELSIF OLD.completion_date IS NULL AND NEW.completion_date IS NOT NULL THEN
          required_action := 'Maintenance Completed';
          required_actor := NEW.completed_by_employee_id;
          required_date := NEW.completion_date; required_status := NEW.resulting_status;
          required_previous := 'Maintenance';
        ELSE RETURN NEW; END IF;
      ELSE
        IF TG_OP <> 'UPDATE' OR NEW.status <> 'Damaged'
           OR OLD.status NOT IN ('Available','Needs Maintenance')
        THEN RETURN NEW; END IF;
        target_asset := NEW.id;
        required_action := 'Damaged'; required_status := 'Damaged';
        required_previous := OLD.status;
      END IF;
      IF TG_TABLE_NAME <> 'assets' AND required_actor IS NULL THEN
        RAISE EXCEPTION 'Asset lifecycle actor is required';
      END IF;
      IF NOT EXISTS (
        SELECT 1 FROM asset_history h JOIN audit_events a
          ON a.module = 'assets' AND a.entity_type = 'asset'
          AND a.entity_id = target_asset::text
          AND a.action = 'asset.' || lower(replace(required_action, ' ', '_'))
          AND a.actor_employee_id = h.actor_employee_id
          AND a.context::jsonb ->> 'historyId' = h.id::text
          AND (a.before_values::jsonb ->> 'status') IS NOT DISTINCT FROM h.previous_status
          AND (a.after_values::jsonb ->> 'status') = h.new_status
        JOIN assets current_asset ON current_asset.id = h.asset_id
        WHERE h.asset_id = target_asset AND h.action = required_action
          AND h.branch_id = current_asset.branch_id
          AND h.new_status = required_status
          AND (required_previous IS NULL OR h.previous_status = required_previous)
          AND (required_date IS NULL OR h.effective_date = required_date)
          AND (required_actor IS NULL OR h.actor_employee_id = required_actor)
          AND (TG_TABLE_NAME <> 'asset_assignments'
            OR h.employee_id::text = to_jsonb(NEW) ->> 'employee_id')
          AND (required_action <> 'Returned'
            OR h.reason = to_jsonb(NEW) ->> 'return_reason')
          AND (required_action <> 'Maintenance Started'
            OR h.reason = to_jsonb(NEW) ->> 'notes')
          AND (required_action <> 'Maintenance Completed'
            OR h.reason IS NOT DISTINCT FROM (to_jsonb(NEW) ->> 'completion_notes'))
          AND (required_action <> 'Damaged' OR length(btrim(h.reason)) > 0)
          AND h.created_at >= transaction_timestamp()
          AND ((TG_TABLE_NAME = 'asset_assignments' AND h.assignment_id = NEW.id)
            OR (TG_TABLE_NAME = 'asset_maintenance_history' AND h.maintenance_id = NEW.id)
            OR TG_TABLE_NAME = 'assets')
      ) THEN RAISE EXCEPTION 'Asset lifecycle history and audit are required'; END IF;
      RETURN NEW;
    END $$;
    CREATE CONSTRAINT TRIGGER require_asset_assignment_evidence
      AFTER INSERT OR UPDATE ON asset_assignments DEFERRABLE INITIALLY DEFERRED
      FOR EACH ROW EXECUTE FUNCTION amafh_require_asset_evidence();
    CREATE CONSTRAINT TRIGGER require_asset_maintenance_evidence
      AFTER INSERT OR UPDATE ON asset_maintenance_history DEFERRABLE INITIALLY DEFERRED
      FOR EACH ROW EXECUTE FUNCTION amafh_require_asset_evidence();
    CREATE CONSTRAINT TRIGGER require_asset_damage_evidence
      AFTER UPDATE ON assets DEFERRABLE INITIALLY DEFERRED
      FOR EACH ROW EXECUTE FUNCTION amafh_require_asset_evidence();
    """)


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
