"""Owner-managed individual Calls access; preserve existing role-eligible users."""

import sqlalchemy as sa
from alembic import op

revision = "20261021callsaccess"
down_revision = "20261017pfrate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_accounts",
        sa.Column("calls_access_granted", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "user_accounts",
        sa.Column("calls_access_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("user_accounts", sa.Column("calls_access_updated_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_user_calls_access_revision", "user_accounts", "calls_access_revision >= 0"
    )


def downgrade() -> None:
    # Do not silently remove a saved block or any individual permission history.
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM user_accounts
                 WHERE NOT calls_access_granted OR calls_access_revision > 0)
      THEN RAISE EXCEPTION 'Individual Calls access history exists; downgrade would erase it';
      END IF;
    END $$;""")
    op.drop_constraint("ck_user_calls_access_revision", "user_accounts", type_="check")
    for name in (
        "calls_access_updated_at",
        "calls_access_revision",
        "calls_access_granted",
    ):
        op.drop_column("user_accounts", name)
