"""Versioned branch hours and bounded, retained Attendance CSV evidence.

Revision ID: 20260926p5att
Revises: 20260926noticefix
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260926p5att"
down_revision = "20260926noticefix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "office_timings",
        sa.Column("created_by_employee_id", UUID(as_uuid=True)),
    )
    op.create_foreign_key(
        "fk_office_timing_actor",
        "office_timings",
        "employees",
        ["created_by_employee_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint("ck_office_timing_order", "office_timings", "end_time > start_time")
    op.execute("""
    CREATE FUNCTION amafh_guard_office_timing() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE branch_name text;
    BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Office Timing versions are immutable'; END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended('office_timing:' || NEW.branch_id::text, 0));
      SELECT name INTO branch_name FROM branches WHERE id = NEW.branch_id AND active FOR SHARE;
      IF branch_name NOT IN ('Dubai','Abu Dhabi') OR branch_name IS NULL
      THEN RAISE EXCEPTION 'Office Timing Branch unavailable'; END IF;
      IF EXISTS (SELECT 1 FROM office_timings WHERE branch_id = NEW.branch_id
                 AND effective_date >= NEW.effective_date)
      THEN RAISE EXCEPTION 'Office Timing effective versions conflict'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_office_timing BEFORE INSERT OR UPDATE OR DELETE ON office_timings
    FOR EACH ROW EXECUTE FUNCTION amafh_guard_office_timing();
    """)
    op.add_column(
        "csv_import_batches",
        sa.Column("branch_id", UUID(as_uuid=True)),
    )
    op.create_foreign_key(
        "fk_csv_import_batch_branch",
        "csv_import_batches",
        "branches",
        ["branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column("csv_import_batches", sa.Column("byte_size", sa.BigInteger()))
    for name in ("data_row_count", "applied_count", "error_count"):
        op.add_column("csv_import_batches", sa.Column(name, sa.Integer()))
    op.create_check_constraint(
        "ck_attendance_batch_evidence",
        "csv_import_batches",
        "kind <> 'attendance' OR branch_id IS NULL OR (byte_size IS NOT NULL "
        "AND data_row_count IS NOT NULL AND applied_count IS NOT NULL AND error_count IS NOT NULL)",
    )
    op.drop_index("uq_csv_import_content", table_name="csv_import_batches")
    op.create_index(
        "uq_csv_import_content",
        "csv_import_batches",
        ["kind", "uploaded_by_employee_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text(
            "kind NOT IN ('bank_stage','attendance') AND content_hash IS NOT NULL"
        ),
    )
    op.create_index(
        "uq_attendance_applied_branch_date",
        "csv_import_batches",
        ["branch_id", "attendance_date"],
        unique=True,
        postgresql_where=sa.text("kind = 'attendance' AND status = 'Applied'"),
    )
    op.add_column("csv_import_row_results", sa.Column("column_name", sa.String(80)))
    op.add_column("attendance_records", sa.Column("office_timing_id", UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_attendance_office_timing",
        "attendance_records",
        "office_timings",
        ["office_timing_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_attendance_record_values",
        "attendance_records",
        "office_timing_id IS NULL OR (status = 'Present' AND check_in_time IS NOT NULL "
        "AND check_out_time IS NOT NULL "
        "AND check_out_time > check_in_time) OR (status = 'Absent' AND check_in_time IS NULL "
        "AND check_out_time IS NULL AND NOT is_late)",
    )
    op.create_index(
        "ix_attendance_branch_date", "attendance_records", ["branch_id", "attendance_date"]
    )
    op.execute("""
    CREATE FUNCTION amafh_guard_attendance_record() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE employee_branch uuid; current_branch uuid; employee_state text;
    DECLARE selected_start time; latest_timing_id uuid;
    DECLARE batch_branch uuid; batch_date date; batch_state text;
    BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Attendance history is immutable'; END IF;
      SELECT e.status, e.branch_id INTO employee_state, current_branch
        FROM employees e WHERE e.id = NEW.employee_id FOR SHARE;
      SELECT h.branch_id INTO employee_branch FROM employee_assignment_history h
        WHERE h.employee_id = NEW.employee_id AND h.assignment_start_date <= NEW.attendance_date
          AND (h.assignment_end_date IS NULL OR h.assignment_end_date > NEW.attendance_date)
        ORDER BY h.assignment_start_date DESC, h.created_at DESC LIMIT 1;
      IF employee_branch IS NULL AND NOT EXISTS (
        SELECT 1 FROM employee_assignment_history WHERE employee_id = NEW.employee_id)
      THEN employee_branch := current_branch; END IF;
      IF employee_state <> 'Active' OR employee_branch IS DISTINCT FROM NEW.branch_id
      THEN RAISE EXCEPTION 'Attendance employee or Branch unavailable'; END IF;
      SELECT branch_id, attendance_date, status INTO batch_branch, batch_date, batch_state
        FROM csv_import_batches WHERE id = NEW.csv_import_batch_id;
      IF batch_branch IS DISTINCT FROM NEW.branch_id
         OR batch_date IS DISTINCT FROM NEW.attendance_date
         OR batch_state <> 'Applied'
      THEN RAISE EXCEPTION 'Attendance batch context invalid'; END IF;
      SELECT start_time INTO selected_start FROM office_timings
        WHERE id = NEW.office_timing_id AND branch_id = NEW.branch_id
          AND effective_date <= NEW.attendance_date;
      SELECT id INTO latest_timing_id FROM office_timings
        WHERE branch_id = NEW.branch_id AND effective_date <= NEW.attendance_date
        ORDER BY effective_date DESC LIMIT 1;
      IF selected_start IS NULL OR latest_timing_id IS DISTINCT FROM NEW.office_timing_id
         OR (NEW.status = 'Present' AND
         NEW.is_late IS DISTINCT FROM (NEW.check_in_time > selected_start))
      THEN RAISE EXCEPTION 'Attendance timing invalid'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_attendance_record BEFORE INSERT OR UPDATE OR DELETE ON attendance_records
    FOR EACH ROW EXECUTE FUNCTION amafh_guard_attendance_record();
    """)


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
