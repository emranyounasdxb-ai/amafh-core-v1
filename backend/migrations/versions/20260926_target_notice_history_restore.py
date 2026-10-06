"""Restore legacy Target notices already historical when blanket suppression ran.

Revision ID: 20260926noticefix
Revises: 20260926targetnotice
"""

from alembic import op

revision = "20260926noticefix"
down_revision = "20260926targetnotice"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The prior revision gave every legacy Target notice a suppression timestamp.
    # The notice's own available_on date identifies those already historical then.
    op.execute("""
        UPDATE notifications SET suppressed_at = NULL
        WHERE kind = 'target.effective'
          AND target_id IS NULL
          AND suppressed_at IS NOT NULL
          AND available_on < (suppressed_at AT TIME ZONE 'Asia/Dubai')::date
    """)


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
