"""Allow Task history to retain assignee viewed/read evidence."""

from alembic import op

revision = "20261002taskviewed"
down_revision = "20260930custnationality"
branch_labels = None
depends_on = None

PREVIOUS_ACTIONS = (
    "'Created','Status Changed','Completed','Reassigned','Cancelled',"
    "'Reopened','Due Date Changed','Archived'"
)
UPDATED_ACTIONS = PREVIOUS_ACTIONS + ",'Viewed'"


def upgrade() -> None:
    op.drop_constraint("ck_task_history_action", "task_history", type_="check")
    op.create_check_constraint(
        "ck_task_history_action",
        "task_history",
        f"action IN ({UPDATED_ACTIONS})",
    )


def downgrade() -> None:
    raise RuntimeError("Retained Task viewed history cannot be discarded")
