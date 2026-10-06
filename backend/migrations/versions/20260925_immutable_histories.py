"""Guard historical facts while allowing a single lifecycle close.

Revision ID: 20260925hist
Revises: 519604204359
"""

from alembic import op

revision = "20260925hist"
down_revision = "519604204359"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE FUNCTION amafh_close_history_once() RETURNS trigger
    LANGUAGE plpgsql AS $$
    DECLARE allowed text[];
    DECLARE close_field text;
    BEGIN
      CASE TG_TABLE_NAME
        WHEN 'employee_assignment_history' THEN
          allowed := ARRAY['assignment_end_date']; close_field := 'assignment_end_date';
        WHEN 'team_memberships' THEN
          allowed := ARRAY['end_date']; close_field := 'end_date';
        WHEN 'case_ownership_history' THEN
          allowed := ARRAY['ended_at']; close_field := 'ended_at';
        WHEN 'asset_assignments' THEN
          allowed := ARRAY['return_date', 'return_reason', 'condition_on_return'];
          close_field := 'return_date';
        WHEN 'asset_maintenance_history' THEN
          allowed := ARRAY['completion_date', 'resulting_status', 'notes'];
          close_field := 'completion_date';
        ELSE RAISE EXCEPTION 'Unsupported history table';
      END CASE;
      IF to_jsonb(OLD)->>close_field IS NOT NULL
         OR to_jsonb(NEW)->>close_field IS NULL
         OR (to_jsonb(OLD) - allowed) IS DISTINCT FROM (to_jsonb(NEW) - allowed)
      THEN
        RAISE EXCEPTION 'Immutable historical record';
      END IF;
      RETURN NEW;
    END $$
    """)
    for table in (
        "employee_assignment_history",
        "team_memberships",
        "case_ownership_history",
        "asset_assignments",
        "asset_maintenance_history",
    ):
        op.execute(
            f"CREATE TRIGGER protect_{table}_update BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION amafh_close_history_once()"
        )
    op.execute(
        "CREATE TRIGGER protect_csv_import_row_results_update "
        "BEFORE UPDATE ON csv_import_row_results "
        "FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change()"
    )


def downgrade() -> None:
    raise RuntimeError("Forward-only historical integrity migration")
