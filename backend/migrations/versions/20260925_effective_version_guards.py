"""Preserve effective-dated configuration history.

Revision ID: 20260925versions
Revises: 20260925rules
"""

from alembic import op

revision = "20260925versions"
down_revision = "20260925rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("pipeline_configurations", "pipeline_stages", "office_timings"):
        op.execute(
            f"CREATE TRIGGER protect_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change()"
        )
    op.execute("""
    CREATE FUNCTION amafh_deactivate_version_once() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Effective-dated version cannot be deleted';
      END IF;
      IF OLD.active IS DISTINCT FROM TRUE OR NEW.active IS DISTINCT FROM FALSE
         OR (to_jsonb(OLD) - 'active' - 'updated_at')
            IS DISTINCT FROM (to_jsonb(NEW) - 'active' - 'updated_at')
      THEN
        RAISE EXCEPTION 'Effective-dated version is immutable';
      END IF;
      RETURN NEW;
    END $$
    """)
    for table in ("targets", "financial_rules"):
        op.execute(
            f"CREATE TRIGGER protect_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION amafh_deactivate_version_once()"
        )


def downgrade() -> None:
    raise RuntimeError("Forward-only effective-version integrity migration")
