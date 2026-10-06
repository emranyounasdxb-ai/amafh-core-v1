"""Prevent a bank-stage CSV from being re-applied by another Coordinator.

Revision ID: 20260926csvreplay
Revises: 20260926initialstage
"""

import sqlalchemy as sa
from alembic import op

revision = "20260926csvreplay"
down_revision = "20260926initialstage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_bank_stage_import_content_global",
        "csv_import_batches",
        ["kind", "content_hash"],
        unique=True,
        postgresql_where=sa.text("kind = 'bank_stage' AND content_hash IS NOT NULL"),
    )


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
