"""Add the locked Compliance User Type with self-only employee and no Case scope."""

import sqlalchemy as sa
from alembic import op

revision = "20261022compliance"
down_revision = "20261021callsaccess"
branch_labels = None
depends_on = None

OLD_NAMES = (
    "name IN ('Owner','Managing Director','Sales Manager','Coordinator',"
    "'Team Leader','Sales Executive','Admin Staff','HR','Finance') AND locked"
)
NEW_NAMES = (
    "name IN ('Owner','Managing Director','Sales Manager','Coordinator',"
    "'Team Leader','Sales Executive','Admin Staff','HR','Finance','Compliance') AND locked"
)


def upgrade() -> None:
    op.drop_constraint("designation_user_types_check", "designation_user_types", type_="check")
    op.create_check_constraint(
        "ck_designation_user_types_locked_names", "designation_user_types", NEW_NAMES
    )
    op.execute(
        sa.text("""
        INSERT INTO designation_user_types (id, name, locked)
        VALUES (gen_random_uuid(), 'Compliance', true)
        ON CONFLICT (name) DO NOTHING
    """)
    )
    op.execute(
        sa.text("""
        INSERT INTO record_scope_config (id, designation_id, resource, scope)
        SELECT gen_random_uuid(), role.id, entry.resource, entry.scope
        FROM designation_user_types AS role
        CROSS JOIN (VALUES ('employee', 'own'), ('case', 'none')) AS entry(resource, scope)
        WHERE role.name = 'Compliance'
        ON CONFLICT (designation_id, resource) DO NOTHING
    """)
    )


def downgrade() -> None:
    # User Types are immutable reference data. Keep the existing protection trigger intact.
    raise RuntimeError(
        "Compliance is locked reference data; downgrade is refused. "
        "Use a forward migration and application code that retains Compliance support."
    )
