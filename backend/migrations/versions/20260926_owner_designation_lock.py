"""Keep the first Owner designation as a permanent enrollment sentinel.

Revision ID: 20260926ownerlock
Revises: 20260926teamhist
"""

from alembic import op

revision = "20260926ownerlock"
down_revision = "20260926teamhist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE FUNCTION amafh_keep_owner_designation() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.designation_id = (
          SELECT id FROM designation_user_types WHERE name = 'Owner'
        ) AND NEW.designation_id IS DISTINCT FROM OLD.designation_id THEN
        RAISE EXCEPTION 'Owner designation cannot be reassigned';
      END IF;
      RETURN NEW;
    END $$
    """)
    op.execute("""
    CREATE TRIGGER keep_owner_designation
    BEFORE UPDATE OF designation_id ON employees
    FOR EACH ROW EXECUTE FUNCTION amafh_keep_owner_designation()
    """)


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
