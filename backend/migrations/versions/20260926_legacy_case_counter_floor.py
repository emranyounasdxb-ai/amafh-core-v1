"""Start each Dubai-year Case counter beyond retained matching legacy IDs.

Revision ID: 20260926casefloor
Revises: 20260926csvreplay
"""

from alembic import op

revision = "20260926casefloor"
down_revision = "20260926csvreplay"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    INSERT INTO case_id_counters (id, dubai_year, last_value)
    SELECT gen_random_uuid(), substring(internal_case_id from 6 for 4)::integer,
           max(substring(internal_case_id from 11)::bigint)
    FROM cases
    WHERE internal_case_id ~ '^CASE-[0-9]{4}-[0-9]{6,}$'
    GROUP BY substring(internal_case_id from 6 for 4)::integer
    ON CONFLICT (dubai_year) DO UPDATE
    SET last_value = greatest(case_id_counters.last_value, EXCLUDED.last_value)
    """)


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
