"""Require a nonfinal initial stage and terminal final-stage ordering.

Revision ID: 20260926initialstage
Revises: 20260926stageguard
"""

from alembic import op

revision = "20260926initialstage"
down_revision = "20260926stageguard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION amafh_check_active_pipeline_stages() RETURNS trigger
    LANGUAGE plpgsql AS $$
    DECLARE pipeline_id uuid;
    DECLARE active_pipeline boolean;
    DECLARE total_stages integer;
    DECLARE min_order integer;
    DECLARE max_order integer;
    DECLARE final_count integer;
    DECLARE bad_outcomes integer;
    DECLARE first_is_final boolean;
    DECLARE stages_after_final integer;
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
      SELECT is_final INTO first_is_final FROM pipeline_stages
      WHERE pipeline_configuration_id = pipeline_id ORDER BY stage_order LIMIT 1;
      SELECT count(*) INTO stages_after_final FROM pipeline_stages later
      WHERE later.pipeline_configuration_id = pipeline_id AND NOT later.is_final
        AND EXISTS (SELECT 1 FROM pipeline_stages earlier
                    WHERE earlier.pipeline_configuration_id = pipeline_id
                      AND earlier.is_final AND earlier.stage_order < later.stage_order);
      IF total_stages < 2 OR min_order <> 1 OR max_order <> total_stages
         OR final_count < 1 OR bad_outcomes > 0 OR first_is_final
         OR stages_after_final > 0 THEN
        RAISE EXCEPTION 'Active Pipeline has invalid ordered or final stages';
      END IF;
      RETURN NULL;
    END $$
    """)


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
