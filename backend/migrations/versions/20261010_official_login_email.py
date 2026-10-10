"""Separate account login identity; existing mappings require explicit operator input."""

import sqlalchemy as sa
from alembic import op

revision = "20261010loginemail"
down_revision = "20261007atthistory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No backfill: contact addresses are not implicitly approved login identities.
    op.add_column("user_accounts", sa.Column("login_email", sa.String(254), nullable=True))
    op.create_check_constraint(
        "ck_user_login_email_normalized",
        "user_accounts",
        "login_email IS NULL OR (login_email = lower(btrim(login_email)) "
        "AND login_email ~ '^[^@[:space:]]+@[^@[:space:]]+$')",
    )
    op.create_index(
        "uq_user_login_email_enabled",
        "user_accounts",
        ["login_email"],
        unique=True,
        postgresql_where=sa.text("access_status <> 'Disabled' AND login_email IS NOT NULL"),
    )


def downgrade() -> None:
    raise RuntimeError("Forward-only migration; login identities must be preserved")
