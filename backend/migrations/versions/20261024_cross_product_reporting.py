"""Index explicit reporting assignments used by cross-product employee/Case scope."""

from alembic import op

revision = "20261024reporting"
down_revision = "20261022compcase"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_employees_reporting_manager",
        "employees",
        ["reporting_manager_id", "branch_id", "department_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_employees_reporting_manager", table_name="employees")
