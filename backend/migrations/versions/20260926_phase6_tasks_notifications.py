"""Add retained Tasks and protected notification read-state evidence.

Revision ID: 20260926p6task
Revises: 20260926p5repair
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260926p6task"
down_revision = "20260926p5repair"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "creator_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assignee_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="RESTRICT")),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("related_type", sa.String(30)),
        sa.Column("related_id", UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["department_id", "branch_id"],
            ["departments.id", "departments.branch_id"],
            name="fk_task_department_branch",
        ),
        sa.CheckConstraint("length(btrim(title)) BETWEEN 1 AND 200", name="ck_task_title"),
        sa.CheckConstraint(
            "description IS NULL OR length(description) <= 5000", name="ck_task_description"
        ),
        sa.CheckConstraint("priority IN ('Low','Normal','High','Urgent')", name="ck_task_priority"),
        sa.CheckConstraint(
            "status IN ('Open','In Progress','Completed','Cancelled')", name="ck_task_status"
        ),
        sa.CheckConstraint(
            "(status = 'Completed') = (completed_at IS NOT NULL)", name="ck_task_completion"
        ),
        sa.CheckConstraint(
            "archived_at IS NULL OR status IN ('Completed','Cancelled')", name="ck_task_archive"
        ),
        sa.CheckConstraint(
            "(related_type IS NULL) = (related_id IS NULL)", name="ck_task_related_pair"
        ),
        sa.CheckConstraint(
            "related_type IS NULL OR related_type IN ('case','customer','employee','asset',"
            "'attendance','attendance_import','finance_result','clawback','payment')",
            name="ck_task_related_type",
        ),
    )
    op.create_index(
        "ix_task_assignee_status_due", "tasks", ["assignee_employee_id", "status", "due_at"]
    )
    op.create_index("ix_task_creator_created", "tasks", ["creator_employee_id", "created_at"])
    op.create_index(
        "ix_task_scope_status_due", "tasks", ["branch_id", "department_id", "status", "due_at"]
    )
    op.create_index("ix_task_team_status_due", "tasks", ["team_id", "status", "due_at"])
    op.create_table(
        "task_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column(
            "actor_employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(1000)),
        sa.Column("before_values", sa.JSON()),
        sa.Column("after_values", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "action IN ('Created','Status Changed','Completed','Reassigned','Cancelled',"
            "'Reopened','Due Date Changed','Archived')",
            name="ck_task_history_action",
        ),
        sa.CheckConstraint(
            "action NOT IN ('Reassigned','Cancelled','Reopened') OR "
            "(reason IS NOT NULL AND length(btrim(reason)) BETWEEN 1 AND 1000)",
            name="ck_task_history_reason",
        ),
    )
    op.create_index("ix_task_history_task_created", "task_history", ["task_id", "created_at", "id"])
    op.add_column("notifications", sa.Column("case_id", UUID(as_uuid=True)))
    op.add_column("notifications", sa.Column("task_id", UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_notification_case", "notifications", "cases", ["case_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "fk_notification_task", "notifications", "tasks", ["task_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_notification_case", "notifications", ["case_id"])
    op.create_index("ix_notification_task", "notifications", ["task_id"])
    op.create_index(
        "ix_notification_recipient_created",
        "notifications",
        ["recipient_employee_id", "created_at", "id"],
    )
    op.create_check_constraint(
        "ck_notification_one_source",
        "notifications",
        "(target_id IS NOT NULL)::int + (case_id IS NOT NULL)::int + "
        "(task_id IS NOT NULL)::int <= 1",
    )
    op.create_table(
        "task_due_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column(
            "notification_id",
            UUID(as_uuid=True),
            sa.ForeignKey("notifications.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("kind IN ('due_soon','overdue')", name="ck_task_due_kind"),
        sa.UniqueConstraint("task_id", "due_at", "kind", name="uq_task_due_event"),
    )
    op.execute("""
    CREATE FUNCTION amafh_guard_notification() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Notification history is retained'; END IF;
      IF ROW(NEW.recipient_employee_id, NEW.kind, NEW.target_id, NEW.case_id,
             NEW.task_id, NEW.message, NEW.available_on, NEW.created_at)
         IS DISTINCT FROM
         ROW(OLD.recipient_employee_id, OLD.kind, OLD.target_id, OLD.case_id,
             OLD.task_id, OLD.message, OLD.available_on, OLD.created_at)
         OR (OLD.read_at IS NOT NULL AND NEW.read_at IS DISTINCT FROM OLD.read_at)
         OR (OLD.suppressed_at IS NOT NULL AND NEW.suppressed_at IS DISTINCT FROM OLD.suppressed_at
             AND NOT (NEW.suppressed_at IS NULL AND OLD.kind = 'target.effective'
               AND OLD.target_id IS NULL
               AND OLD.available_on < (OLD.suppressed_at AT TIME ZONE 'Asia/Dubai')::date))
      THEN RAISE EXCEPTION 'Notification evidence is immutable'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_notification BEFORE UPDATE OR DELETE ON notifications
      FOR EACH ROW EXECUTE FUNCTION amafh_guard_notification();
    CREATE TRIGGER guard_task_history BEFORE UPDATE OR DELETE ON task_history
      FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change();
    CREATE TRIGGER guard_task_due_event BEFORE UPDATE OR DELETE ON task_due_events
      FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change();
    """)
    op.execute("""
    CREATE FUNCTION amafh_guard_task() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE assignee record;
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Task deletion is prohibited'; END IF;
      IF TG_OP = 'INSERT' OR NEW.assignee_employee_id IS DISTINCT FROM OLD.assignee_employee_id THEN
        SELECT status, branch_id, department_id INTO assignee
          FROM employees WHERE id = NEW.assignee_employee_id;
        IF assignee.status IS DISTINCT FROM 'Active' OR assignee.branch_id IS NULL
           OR assignee.department_id IS NULL OR assignee.branch_id <> NEW.branch_id
           OR assignee.department_id <> NEW.department_id
        THEN RAISE EXCEPTION 'Task assignee must be active in retained scope'; END IF;
      END IF;
      IF TG_OP = 'INSERT' THEN
        IF NEW.due_at <= now() OR NEW.title <> btrim(NEW.title) THEN
          RAISE EXCEPTION 'Task requires future due time and trimmed title'; END IF;
      ELSE
        IF OLD.archived_at IS NOT NULL OR NEW.creator_employee_id <> OLD.creator_employee_id
           OR NEW.created_at <> OLD.created_at OR NEW.title <> OLD.title
           OR NEW.description IS DISTINCT FROM OLD.description
           OR NEW.priority <> OLD.priority OR NEW.related_type IS DISTINCT FROM OLD.related_type
           OR NEW.related_id IS DISTINCT FROM OLD.related_id
        THEN RAISE EXCEPTION 'Task retained identity is immutable'; END IF;
        IF NEW.assignee_employee_id = OLD.assignee_employee_id AND
           ROW(NEW.branch_id, NEW.department_id, NEW.team_id) IS DISTINCT FROM
           ROW(OLD.branch_id, OLD.department_id, OLD.team_id)
        THEN RAISE EXCEPTION 'Task scope changes only on reassignment'; END IF;
        IF OLD.status IN ('Completed','Cancelled') AND NEW.status NOT IN (OLD.status,'Open')
           OR OLD.status IN ('Open','In Progress') AND NEW.status NOT IN
              ('Open','In Progress','Completed','Cancelled')
        THEN RAISE EXCEPTION 'Invalid Task transition'; END IF;
        IF NEW.status = 'Open' AND OLD.status IN ('Completed','Cancelled')
           AND NEW.due_at <= now() THEN
          RAISE EXCEPTION 'Reopened Task requires future due time'; END IF;
        IF NEW.assignee_employee_id IS DISTINCT FROM OLD.assignee_employee_id
           AND OLD.status NOT IN ('Open','In Progress')
        THEN RAISE EXCEPTION 'Only active Tasks may be reassigned'; END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_task BEFORE INSERT OR UPDATE OR DELETE ON tasks
      FOR EACH ROW EXECUTE FUNCTION amafh_guard_task();
    """)
    op.execute("""
    CREATE FUNCTION amafh_require_task_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE required_action text;
    BEGIN
      IF TG_OP = 'INSERT' THEN required_action := 'Created';
      ELSIF NEW.archived_at IS DISTINCT FROM OLD.archived_at THEN required_action := 'Archived';
      ELSIF NEW.status = 'Open' AND OLD.status IN ('Completed','Cancelled')
        THEN required_action := 'Reopened';
      ELSIF NEW.assignee_employee_id IS DISTINCT FROM OLD.assignee_employee_id
        THEN required_action := 'Reassigned';
      ELSIF NEW.status = 'Completed' AND OLD.status <> 'Completed'
        THEN required_action := 'Completed';
      ELSIF NEW.status = 'Cancelled' AND OLD.status <> 'Cancelled'
        THEN required_action := 'Cancelled';
      ELSIF NEW.status IS DISTINCT FROM OLD.status THEN required_action := 'Status Changed';
      ELSIF NEW.due_at IS DISTINCT FROM OLD.due_at THEN required_action := 'Due Date Changed';
      ELSE RETURN NEW; END IF;
      IF NOT EXISTS (
        SELECT 1 FROM task_history h JOIN audit_events a
          ON a.module = 'tasks' AND a.entity_type = 'task' AND a.entity_id = NEW.id::text
          AND a.actor_employee_id = h.actor_employee_id
          AND a.context::jsonb ->> 'historyId' = h.id::text
          AND a.action = 'task.' || lower(replace(required_action, ' ', '_'))
        WHERE h.task_id = NEW.id AND h.action = required_action
          AND h.created_at >= transaction_timestamp()
          AND h.after_values::jsonb ->> 'status' = NEW.status
          AND (h.after_values::jsonb ->> 'assigneeEmployeeId')::uuid = NEW.assignee_employee_id
          AND (h.after_values::jsonb ->> 'dueAt')::timestamptz = NEW.due_at
      ) THEN RAISE EXCEPTION 'Task history and audit are required'; END IF;
      RETURN NEW;
    END $$;
    CREATE CONSTRAINT TRIGGER require_task_evidence AFTER INSERT OR UPDATE ON tasks
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
      EXECUTE FUNCTION amafh_require_task_evidence();
    """)


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
