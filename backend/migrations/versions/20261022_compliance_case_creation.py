"""Enable Owner-configurable personal Case creation for Compliance."""

import sqlalchemy as sa
from alembic import op

revision = "20261022compcase"
down_revision = "20261022compliance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text("""
        INSERT INTO permissions (id, key, description)
        VALUES (gen_random_uuid(), 'case.create', 'case.create')
        ON CONFLICT (key) DO NOTHING
    """)
    )
    op.execute(
        sa.text("""
        INSERT INTO role_permissions (id, designation_id, permission_id, granted)
        SELECT gen_random_uuid(), d.id, p.id, true
        FROM designation_user_types d CROSS JOIN permissions p
        WHERE d.name = 'Compliance' AND p.key = 'case.create'
        ON CONFLICT (designation_id, permission_id) DO NOTHING
    """)
    )


def downgrade() -> None:
    raise RuntimeError(
        "AMAFH permission history is forward-only; "
        "use Owner permission settings to revoke Case creation"
    )
