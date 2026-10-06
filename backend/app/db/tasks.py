"""Retained Tasks, immutable transition history, and due-notice evidence."""

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from .base import created_at, metadata, pk, updated_at

tasks = Table(
    "tasks",
    metadata,
    pk(),
    Column(
        "creator_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "assignee_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "branch_id",
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "department_id",
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT")),
    Column("title", String(200), nullable=False),
    Column("description", Text),
    Column("priority", String(10), nullable=False),
    Column("status", String(20), nullable=False),
    Column("due_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    Column("archived_at", DateTime(timezone=True)),
    Column("related_type", String(30)),
    Column("related_id", UUID(as_uuid=True)),
    created_at(),
    updated_at(),
    CheckConstraint("length(btrim(title)) BETWEEN 1 AND 200", name="ck_task_title"),
    CheckConstraint(
        "description IS NULL OR length(description) <= 5000", name="ck_task_description"
    ),
    CheckConstraint("priority IN ('Low','Normal','High','Urgent')", name="ck_task_priority"),
    CheckConstraint(
        "status IN ('Open','In Progress','Completed','Cancelled')", name="ck_task_status"
    ),
    CheckConstraint(
        "(status = 'Completed') = (completed_at IS NOT NULL)", name="ck_task_completion"
    ),
    CheckConstraint(
        "archived_at IS NULL OR status IN ('Completed','Cancelled')", name="ck_task_archive"
    ),
    CheckConstraint("(related_type IS NULL) = (related_id IS NULL)", name="ck_task_related_pair"),
    CheckConstraint(
        "related_type IS NULL OR related_type IN "
        "('case','customer','employee','asset','attendance','attendance_import',"
        "'finance_result','clawback','payment')",
        name="ck_task_related_type",
    ),
    ForeignKeyConstraint(
        ["department_id", "branch_id"],
        ["departments.id", "departments.branch_id"],
        name="fk_task_department_branch",
    ),
    Index("ix_task_assignee_status_due", "assignee_employee_id", "status", "due_at"),
    Index("ix_task_creator_created", "creator_employee_id", "created_at"),
    Index("ix_task_scope_status_due", "branch_id", "department_id", "status", "due_at"),
    Index("ix_task_team_status_due", "team_id", "status", "due_at"),
)

task_history = Table(
    "task_history",
    metadata,
    pk(),
    Column(
        "task_id", UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False
    ),
    Column("action", String(30), nullable=False),
    Column(
        "actor_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("reason", String(1000)),
    Column("before_values", JSON),
    Column("after_values", JSON, nullable=False),
    created_at(),
    CheckConstraint(
        "action IN ('Created','Status Changed','Completed','Reassigned','Cancelled',"
        "'Reopened','Due Date Changed','Archived','Viewed')",
        name="ck_task_history_action",
    ),
    CheckConstraint(
        "action NOT IN ('Reassigned','Cancelled','Reopened') OR "
        "(reason IS NOT NULL AND length(btrim(reason)) BETWEEN 1 AND 1000)",
        name="ck_task_history_reason",
    ),
    Index("ix_task_history_task_created", "task_id", "created_at", "id"),
)

task_due_events = Table(
    "task_due_events",
    metadata,
    pk(),
    Column(
        "task_id", UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False
    ),
    Column("due_at", DateTime(timezone=True), nullable=False),
    Column("kind", String(20), nullable=False),
    Column(
        "notification_id",
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    created_at(),
    CheckConstraint("kind IN ('due_soon','overdue')", name="ck_task_due_kind"),
    UniqueConstraint("task_id", "due_at", "kind", name="uq_task_due_event"),
)
