"""Retain optional Individual Customer ISO nationality without backfilling history."""

import sqlalchemy as sa
from alembic import op

revision = "20260930custnationality"
down_revision = "20260928globalbanner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("individual_customers", sa.Column("nationality", sa.String(2), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Retained Customer nationality cannot be discarded")
