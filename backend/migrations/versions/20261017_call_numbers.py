"""Support exact phone and extension numbers on either side of a recording."""

import sqlalchemy as sa
from alembic import op

revision = "20261017callnumbers"
down_revision = "20261016calls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_call_recordings_customer_number", "call_recordings", type_="check")
    op.alter_column(
        "call_recordings", "customer_number", existing_type=sa.String(10), type_=sa.String(32)
    )
    op.create_check_constraint(
        "ck_call_recordings_customer_number", "call_recordings", "customer_number ~ '^[0-9]{1,32}$'"
    )
    op.create_index(
        "ix_call_recordings_first_number_search",
        "call_recordings",
        ["source_id", "catalog_generation", "month", "extension", "filename", "id"],
        postgresql_where=sa.text("availability = 'ready'"),
    )


def downgrade() -> None:
    # Never truncate a catalog number to fit the previous schema.
    connection = op.get_bind()
    if connection.execute(
        sa.text("SELECT 1 FROM call_recordings WHERE customer_number !~ '^[0-9]{10}$' LIMIT 1")
    ).first():
        raise RuntimeError("Catalog contains non-ten-digit numbers; downgrade would lose data.")
    op.drop_index("ix_call_recordings_first_number_search", table_name="call_recordings")
    op.drop_constraint("ck_call_recordings_customer_number", "call_recordings", type_="check")
    op.alter_column(
        "call_recordings", "customer_number", existing_type=sa.String(32), type_=sa.String(10)
    )
    op.create_check_constraint(
        "ck_call_recordings_customer_number", "call_recordings", "customer_number ~ '^[0-9]{10}$'"
    )
