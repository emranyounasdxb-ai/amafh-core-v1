"""Date-effective attendance employment guards; retained records stay immutable."""

from alembic import op

revision = "20261007atthistory"
down_revision = "20261007variantsalary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION amafh_guard_attendance_record()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE employee_branch uuid; employee_state text; joined_on date; last_day date;
    DECLARE assignment_count integer; terminal_start date; terminal_end date;
    DECLARE terminal_created timestamptz; terminal_count integer;
    DECLARE selected_start time; latest_timing_id uuid;
    DECLARE batch_branch uuid; batch_date date; batch_state text;
    BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Attendance history is immutable'; END IF;
      SELECT e.status, e.date_of_joining, e.last_working_date
        INTO employee_state, joined_on, last_day
        FROM employees e WHERE e.id = NEW.employee_id FOR SHARE;
      IF joined_on IS NULL OR joined_on > NEW.attendance_date
         OR employee_state NOT IN ('Active','Offboarded')
         OR (employee_state = 'Offboarded' AND
            (last_day IS NULL OR NEW.attendance_date > last_day))
      THEN RAISE EXCEPTION 'Attendance employment evidence unavailable'; END IF;
      SELECT count(*), (array_agg(h.branch_id))[1] INTO assignment_count, employee_branch
        FROM employee_assignment_history h
        WHERE h.employee_id = NEW.employee_id AND h.assignment_start_date <= NEW.attendance_date
          AND (h.assignment_end_date IS NULL OR h.assignment_end_date > NEW.attendance_date);
      -- Transfers remain end-exclusive. Only the terminal offboarding row may
      -- include the last working day; current placement is never a fallback.
      IF assignment_count = 0 AND employee_state = 'Offboarded'
         AND NEW.attendance_date = last_day THEN
        SELECT h.branch_id, h.assignment_start_date, h.assignment_end_date, h.created_at
          INTO employee_branch, terminal_start, terminal_end, terminal_created
          FROM employee_assignment_history h WHERE h.employee_id = NEW.employee_id
          ORDER BY h.assignment_start_date DESC, h.created_at DESC LIMIT 1;
        SELECT count(*) INTO terminal_count FROM employee_assignment_history h
          WHERE h.employee_id = NEW.employee_id AND h.assignment_start_date = terminal_start
            AND h.created_at = terminal_created;
        IF terminal_count = 1 AND terminal_start <= NEW.attendance_date AND terminal_end = last_day
        THEN assignment_count := 1; END IF;
      END IF;
      IF assignment_count <> 1 OR employee_branch IS DISTINCT FROM NEW.branch_id
      THEN RAISE EXCEPTION 'Attendance assignment evidence unavailable'; END IF;
      SELECT branch_id, attendance_date, status INTO batch_branch, batch_date, batch_state
        FROM csv_import_batches WHERE id = NEW.csv_import_batch_id;
      IF batch_branch IS DISTINCT FROM NEW.branch_id
         OR batch_date IS DISTINCT FROM NEW.attendance_date
         OR batch_state IS DISTINCT FROM 'Applied'
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
    """)


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only")
