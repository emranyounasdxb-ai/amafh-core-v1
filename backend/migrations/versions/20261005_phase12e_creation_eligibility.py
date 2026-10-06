"""Phase 12E Case creation eligibility correction.

Only Sales Executive, Team Leader, Sales Manager, Coordinator and Admin Staff may
create Cases (DEC-065 as corrected). The Owner, Managing Director, HR and Finance
rows added by ``20261005p12e`` are kept, because rows cannot be deleted, but are
marked not granted; "Create Cases" is outside those User Types' boundary, so no
later configuration can grant it.

Revision ID: 20261005p12e2
Revises: 20261005p12e
"""

import sqlalchemy as sa
from alembic import op

revision = "20261005p12e2"
down_revision = "20261005p12e"
branch_labels = None
depends_on = None

EXCLUDED = ("Owner", "Managing Director", "HR", "Finance")


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE role_permissions rp SET granted = false, updated_at = now() "
            "FROM designation_user_types d, permissions p "
            "WHERE rp.designation_id = d.id AND rp.permission_id = p.id "
            "AND p.key = 'case.create' AND d.name IN :roles AND rp.granted"
        ).bindparams(sa.bindparam("roles", value=EXCLUDED, expanding=True))
    )


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
