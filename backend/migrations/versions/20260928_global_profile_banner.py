"""Retain one Owner-managed global profile banner reference.

Revision ID: 20260928globalbanner
Revises: 20260927noticesrc
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260928globalbanner"
down_revision = "20260927noticesrc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("stored_files_kind_check", "stored_files", type_="check")
    op.create_check_constraint(
        "stored_files_kind_check",
        "stored_files",
        "kind IN ('employee_avatar','employee_cover','bank_logo',"
        "'product_image','product_variant_image','global_profile_banner')",
    )
    op.create_table(
        "global_profile_banner",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_id", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_employee_id", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_global_profile_banner_singleton"),
        sa.ForeignKeyConstraint(["file_id"], ["stored_files.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_employee_id"], ["employees.id"], ondelete="RESTRICT"),
    )
    op.execute("INSERT INTO global_profile_banner (id) VALUES (1)")


def downgrade() -> None:
    raise RuntimeError("Global banner history is retained and cannot be downgraded")
