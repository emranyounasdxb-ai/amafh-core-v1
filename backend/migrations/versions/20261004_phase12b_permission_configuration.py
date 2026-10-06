"""Configurable User Type permissions.

Role permission rows become the persisted configuration of each User Type's
configurable action grants. Every existing row was an effective grant of the
locked matrix, so it is preserved as granted. A revocation keeps its row with
``granted = false`` and records who changed it, so later reference-data seeding
cannot silently restore it. Rows cannot be deleted. The Owner-only permission
management action is added as a fixed grant.

Revision ID: 20261004p12b
Revises: 20261004p12aot
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20261004p12b"
down_revision = "20261004p12aot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "role_permissions",
        sa.Column("granted", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("role_permissions", sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.add_column(
        "role_permissions",
        sa.Column(
            "updated_by_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
        ),
    )
    op.execute(
        """
        INSERT INTO permissions (id, key, description)
        VALUES (gen_random_uuid(), 'permissions.write', 'permissions.write')
        ON CONFLICT (key) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (id, designation_id, permission_id)
        SELECT gen_random_uuid(), d.id, p.id
        FROM designation_user_types d CROSS JOIN permissions p
        WHERE d.name = 'Owner' AND p.key = 'permissions.write'
        ON CONFLICT (designation_id, permission_id) DO NOTHING
        """
    )
    op.execute(
        "CREATE TRIGGER protect_role_permissions_delete BEFORE DELETE ON role_permissions "
        "FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change()"
    )


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
