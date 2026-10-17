"""Bounded prefix lookups for recording-number suggestions."""

import sqlalchemy as sa
from alembic import op

revision = "20261017callsuggest"
down_revision = "20261017callnumbers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, column in (
        ("ix_call_recordings_first_number_prefix", "extension"),
        ("ix_call_recordings_second_number_prefix", "customer_number"),
    ):
        op.create_index(
            name,
            "call_recordings",
            ["source_id", "catalog_generation", "month", sa.text(f'({column} COLLATE "C")')],
            postgresql_where=sa.text("availability = 'ready'"),
        )


def downgrade() -> None:
    op.drop_index("ix_call_recordings_second_number_prefix", table_name="call_recordings")
    op.drop_index("ix_call_recordings_first_number_prefix", table_name="call_recordings")
