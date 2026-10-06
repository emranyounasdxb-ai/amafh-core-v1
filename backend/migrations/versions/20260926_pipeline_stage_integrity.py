"""Validate complete active Pipeline stage sets at transaction commit.

Revision ID: 20260926stageguard
Revises: 20260926cases
"""

from alembic import op

revision = "20260926stageguard"
down_revision = "20260926cases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE FUNCTION amafh_check_active_pipeline_stages() RETURNS trigger
    LANGUAGE plpgsql AS $$
    DECLARE pipeline_id uuid;
    DECLARE active_pipeline boolean;
    DECLARE total_stages integer;
    DECLARE min_order integer;
    DECLARE max_order integer;
    DECLARE final_count integer;
    DECLARE bad_outcomes integer;
    BEGIN
      IF TG_TABLE_NAME = 'pipeline_configurations' THEN
        pipeline_id := NEW.id;
      ELSE
        pipeline_id := COALESCE(NEW.pipeline_configuration_id, OLD.pipeline_configuration_id);
      END IF;
      SELECT active INTO active_pipeline FROM pipeline_configurations WHERE id = pipeline_id;
      IF active_pipeline IS DISTINCT FROM TRUE THEN RETURN NULL; END IF;
      SELECT count(*), min(stage_order), max(stage_order),
             count(*) FILTER (WHERE is_final),
             count(*) FILTER (WHERE (is_final AND final_status IS NULL)
                                    OR (NOT is_final AND final_status IS NOT NULL))
      INTO total_stages, min_order, max_order, final_count, bad_outcomes
      FROM pipeline_stages WHERE pipeline_configuration_id = pipeline_id;
      IF total_stages < 2 OR min_order <> 1 OR max_order <> total_stages
         OR final_count < 1 OR bad_outcomes > 0 THEN
        RAISE EXCEPTION 'Active Pipeline has invalid ordered or final stages';
      END IF;
      RETURN NULL;
    END $$
    """)
    op.execute("""
    CREATE CONSTRAINT TRIGGER check_active_pipeline_configuration
    AFTER INSERT OR UPDATE ON pipeline_configurations
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION amafh_check_active_pipeline_stages()
    """)
    op.execute("""
    CREATE CONSTRAINT TRIGGER check_active_pipeline_stage
    AFTER INSERT OR UPDATE OR DELETE ON pipeline_stages
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION amafh_check_active_pipeline_stages()
    """)


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
