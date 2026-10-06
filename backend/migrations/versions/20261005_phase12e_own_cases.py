"""Phase 12E Own Cases.

Every User Type may create Cases it owns (DEC-065). "Create Cases" joins the
boundary of the Owner, Managing Director, HR, Finance and Admin Staff, granted
by default; existing rows, including revoked ones, are left unchanged.

Revision ID: 20261005p12e
Revises: 20261005p12c
"""

import sqlalchemy as sa
from alembic import op

revision = "20261005p12e"
down_revision = "20261005p12c"
branch_labels = None
depends_on = None

NEW_CREATORS = ("Owner", "Managing Director", "HR", "Finance", "Admin Staff")


def upgrade() -> None:
    for role in NEW_CREATORS:
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (id, designation_id, permission_id) "
                "SELECT gen_random_uuid(), d.id, p.id "
                "FROM designation_user_types d CROSS JOIN permissions p "
                "WHERE d.name = :role AND p.key = 'case.create' "
                "ON CONFLICT (designation_id, permission_id) DO NOTHING"
            ).bindparams(role=role)
        )


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
