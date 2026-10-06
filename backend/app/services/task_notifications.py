"""Standalone, idempotent Task due and overdue notice dispatch."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.operations import notifications
from app.db.organization import employees
from app.db.tasks import task_due_events, tasks


def _missing(kind: str):
    return ~exists(
        select(task_due_events.c.id).where(
            task_due_events.c.task_id == tasks.c.id,
            task_due_events.c.due_at == tasks.c.due_at,
            task_due_events.c.kind == kind,
        )
    )


async def dispatch_due(session: AsyncSession) -> dict:
    created = 0
    try:
        while True:
            now = utcnow()
            soon = and_(
                tasks.c.due_at > now,
                tasks.c.due_at <= now + timedelta(hours=24),
                _missing("due_soon"),
            )
            overdue = and_(tasks.c.due_at <= now, _missing("overdue"))
            rows = (
                (
                    await session.execute(
                        select(tasks)
                        .join(employees, employees.c.id == tasks.c.assignee_employee_id)
                        .where(
                            tasks.c.status.in_({"Open", "In Progress"}),
                            tasks.c.archived_at.is_(None),
                            employees.c.status == "Active",
                            or_(soon, overdue),
                        )
                        .order_by(tasks.c.due_at, tasks.c.id)
                        .limit(100)
                        .with_for_update(of=tasks, skip_locked=True)
                    )
                )
                .mappings()
                .all()
            )
            if not rows:
                break
            for row in rows:
                kind = "overdue" if row["due_at"] <= now else "due_soon"
                notice_id = uuid4()
                await session.execute(
                    notifications.insert().values(
                        id=notice_id,
                        recipient_employee_id=row["assignee_employee_id"],
                        task_id=row["id"],
                        kind=f"task.{kind}",
                        message="A Task update is available",
                    )
                )
                await session.execute(
                    task_due_events.insert().values(
                        id=uuid4(),
                        task_id=row["id"],
                        due_at=row["due_at"],
                        kind=kind,
                        notification_id=notice_id,
                    )
                )
                await audit.record(
                    session,
                    actor=None,
                    action=f"task.{kind}_notified",
                    module="tasks",
                    entity_type="task",
                    entity_id=row["id"],
                    context={"notificationId": str(notice_id), "dueAt": row["due_at"].isoformat()},
                )
                created += 1
            await session.commit()
        return {"notificationsCreated": created}
    except Exception:
        await session.rollback()
        raise
