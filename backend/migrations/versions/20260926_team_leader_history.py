"""Retain Team Leader tenure across reassignment and deactivation.

Revision ID: 20260926teamhist
Revises: 20260926integrity
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260926teamhist"
down_revision = "20260926integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_leader_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "leader_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_current_team_leader_history ON team_leader_history (team_id) "
        "WHERE end_date IS NULL"
    )
    op.execute("""
    INSERT INTO team_leader_history (id, team_id, leader_employee_id, start_date, end_date)
    SELECT gen_random_uuid(), id, leader_employee_id,
           (created_at AT TIME ZONE 'Asia/Dubai')::date,
           CASE WHEN active THEN NULL ELSE (updated_at AT TIME ZONE 'Asia/Dubai')::date END
    FROM teams
    """)
    op.execute("""
    CREATE FUNCTION amafh_close_team_leader_once() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.end_date IS NOT NULL OR NEW.end_date IS NULL OR
         (to_jsonb(OLD) - 'end_date') IS DISTINCT FROM (to_jsonb(NEW) - 'end_date')
      THEN
        RAISE EXCEPTION 'Immutable Team Leader history';
      END IF;
      RETURN NEW;
    END $$
    """)
    op.execute("""
    CREATE TRIGGER protect_team_leader_history_update
    BEFORE UPDATE ON team_leader_history
    FOR EACH ROW EXECUTE FUNCTION amafh_close_team_leader_once()
    """)
    op.execute("""
    CREATE TRIGGER protect_team_leader_history_delete
    BEFORE DELETE ON team_leader_history
    FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change()
    """)


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
