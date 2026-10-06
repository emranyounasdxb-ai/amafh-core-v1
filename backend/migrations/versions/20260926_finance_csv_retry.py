"""Permit retained missing-rule rejections to be retried after rule setup.

Revision ID: 20260926finretry
Revises: 20260926finance
"""

import sqlalchemy as sa
from alembic import op

revision = "20260926finretry"
down_revision = "20260926finance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing batches, row results, audit and content hashes remain untouched.
    # Other CSV kinds keep their uploader-scoped content protection.
    op.drop_index("uq_csv_import_content", table_name="csv_import_batches")
    op.create_index(
        "uq_csv_import_content",
        "csv_import_batches",
        ["kind", "uploaded_by_employee_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text("kind <> 'bank_stage' AND content_hash IS NOT NULL"),
    )
    op.drop_index("uq_bank_stage_import_content_global", table_name="csv_import_batches")
    op.create_index(
        "uq_bank_stage_import_content_global",
        "csv_import_batches",
        ["kind", "content_hash"],
        unique=True,
        postgresql_where=sa.text(
            "kind = 'bank_stage' AND status = 'Applied' AND content_hash IS NOT NULL"
        ),
    )


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
