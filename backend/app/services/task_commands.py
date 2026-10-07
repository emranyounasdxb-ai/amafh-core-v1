"""Atomic, idempotent Task transitions with retained evidence."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.operations import notifications
from app.db.tasks import task_history, tasks
from app.errors import ApiError
from app.policies import Actor
from app.schemas.tasks import TaskCreate, TaskItem
from app.services.idempotency import claim, complete
from app.services.task_policy import ACTIVE, assignment_scope, may_link, may_manage
from app.services.task_reads import creation_replay, detail, scoped_task


def _state(row: dict) -> dict:
    return {
        "status": row["status"],
        "assigneeEmployeeId": str(row["assignee_employee_id"]),
        "dueAt": row["due_at"].astimezone(UTC).isoformat(),
        "branchId": str(row["branch_id"]),
        "departmentId": str(row["department_id"]),
        "teamId": str(row["team_id"]) if row["team_id"] else None,
        "completedAt": row["completed_at"].isoformat() if row["completed_at"] else None,
        "archivedAt": row["archived_at"].isoformat() if row["archived_at"] else None,
        "relatedType": row["related_type"],
        "relatedId": str(row["related_id"]) if row["related_id"] else None,
    }


async def _evidence(
    session: AsyncSession,
    actor: Actor,
    task_id: UUID,
    action: str,
    before: dict | None,
    after: dict,
    reason: str | None = None,
) -> None:
    history_id = uuid4()
    await session.execute(
        task_history.insert().values(
            id=history_id,
            task_id=task_id,
            action=action,
            actor_employee_id=actor.employee_id,
            reason=reason,
            before_values=before,
            after_values=after,
        )
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action=f"task.{action.lower().replace(' ', '_')}",
        module="tasks",
        entity_type="task",
        entity_id=task_id,
        before=before,
        after=after,
        context={"historyId": str(history_id), "reason": reason},
    )


async def _notice(session: AsyncSession, task_id: UUID, recipient_id: UUID, kind: str) -> None:
    await session.execute(
        notifications.insert().values(
            id=uuid4(),
            recipient_employee_id=recipient_id,
            task_id=task_id,
            kind=kind,
            message="A Task update is available",
        )
    )


async def create(session: AsyncSession, actor: Actor, item: TaskCreate, key: str) -> dict:
    try:
        record_id, replay = await claim(
            session, actor, "task.create", key, item.model_dump(mode="json")
        )
        if replay is not None:
            await session.rollback()
            return await creation_replay(session, actor, replay)
        if item.dueAt.astimezone(UTC) <= utcnow():
            raise ApiError(422, "TASK_DUE_INVALID", "Due time must be in the future")
        scope = await assignment_scope(session, actor, item.assigneeEmployeeId)
        if item.relatedType is not None and item.relatedId is not None:
            if not await may_link(
                session, actor, item.relatedType, item.relatedId
            ) or not await may_link(session, scope["assignee"], item.relatedType, item.relatedId):
                raise ApiError(404, "NOT_FOUND", "Related record unavailable")
        task_id = uuid4()
        row = (
            (
                await session.execute(
                    tasks.insert()
                    .values(
                        id=task_id,
                        creator_employee_id=actor.employee_id,
                        assignee_employee_id=item.assigneeEmployeeId,
                        branch_id=scope["branch_id"],
                        department_id=scope["department_id"],
                        team_id=scope["team_id"],
                        title=item.title,
                        description=item.description,
                        priority=item.priority,
                        status="Open",
                        due_at=item.dueAt.astimezone(UTC),
                        related_type=item.relatedType,
                        related_id=item.relatedId,
                    )
                    .returning(*tasks.c)
                )
            )
            .mappings()
            .one()
        )
        await _evidence(session, actor, task_id, "Created", None, _state(dict(row)))
        await _notice(session, task_id, item.assigneeEmployeeId, "task.assigned")
        result = TaskItem.model_validate(await detail(session, actor, task_id))
        await complete(session, record_id, 201, result.model_dump(mode="json"))
        await session.commit()
        return result.model_dump(mode="python")
    except Exception:
        await session.rollback()
        raise


async def command(
    session: AsyncSession,
    actor: Actor,
    task_id: UUID,
    action: str,
    payload: dict,
    key: str,
) -> dict:
    try:
        row = await scoped_task(session, actor, task_id, lock=True)
        record_id, replay = await claim(session, actor, f"task.{action}:{task_id}", key, payload)
        if replay is not None:
            await session.rollback()
            return await detail(session, actor, task_id)
        now = utcnow()
        values: dict = {"updated_at": now}
        reason: str | None = payload.get("reason")
        event: str
        notices: list[tuple[UUID, str]] = []
        if action == "status":
            if row["assignee_employee_id"] != actor.employee_id:
                raise ApiError(403, "FORBIDDEN", "Access denied")
            target = payload["status"]
            if row["status"] == target:
                return await _unchanged(session, actor, task_id, record_id)
            if row["status"] not in ACTIVE:
                raise ApiError(409, "TASK_TRANSITION_INVALID", "Task is no longer active")
            values["status"] = target
            if target == "Completed":
                values["completed_at"] = now
                event = "Completed"
                notices.append((row["creator_employee_id"], "task.completed"))
            else:
                event = "Status Changed"
        else:
            if not await may_manage(session, actor, row):
                raise ApiError(403, "FORBIDDEN", "Access denied")
            if row["archived_at"] is not None:
                raise ApiError(409, "TASK_ARCHIVED", "Task is archived")
            if action == "reassign":
                if row["status"] not in ACTIVE:
                    raise ApiError(409, "TASK_TRANSITION_INVALID", "Task is no longer active")
                replacement = UUID(payload["assigneeEmployeeId"])
                if replacement == row["assignee_employee_id"]:
                    raise ApiError(409, "TASK_ASSIGNMENT_UNCHANGED", "Assignee is unchanged")
                scope = await assignment_scope(session, actor, replacement)
                if row["related_id"] is not None and (
                    not await may_link(session, actor, row["related_type"], row["related_id"])
                    or not await may_link(
                        session, scope["assignee"], row["related_type"], row["related_id"]
                    )
                ):
                    raise ApiError(404, "NOT_FOUND", "Related record unavailable")
                values.update(
                    assignee_employee_id=replacement,
                    branch_id=scope["branch_id"],
                    department_id=scope["department_id"],
                    team_id=scope["team_id"],
                )
                event = "Reassigned"
                notices.extend(
                    [
                        (replacement, "task.reassigned"),
                        (row["assignee_employee_id"], "task.reassigned_away"),
                    ]
                )
            elif action == "cancel":
                if row["status"] not in ACTIVE:
                    raise ApiError(409, "TASK_TRANSITION_INVALID", "Task is no longer active")
                values["status"] = "Cancelled"
                event = "Cancelled"
                notices.append((row["creator_employee_id"], "task.cancelled"))
            elif action == "reopen":
                if row["status"] not in {"Completed", "Cancelled"}:
                    raise ApiError(409, "TASK_TRANSITION_INVALID", "Task is not closed")
                scope = await assignment_scope(session, actor, row["assignee_employee_id"])
                if row["related_id"] is not None and (
                    not await may_link(session, actor, row["related_type"], row["related_id"])
                    or not await may_link(
                        session, scope["assignee"], row["related_type"], row["related_id"]
                    )
                ):
                    raise ApiError(404, "NOT_FOUND", "Related record unavailable")
                due = datetime.fromisoformat(payload["dueAt"]).astimezone(UTC)
                if due <= now:
                    raise ApiError(422, "TASK_DUE_INVALID", "Due time must be in the future")
                values.update(
                    status="Open",
                    completed_at=None,
                    due_at=due,
                    branch_id=scope["branch_id"],
                    department_id=scope["department_id"],
                    team_id=scope["team_id"],
                )
                event = "Reopened"
                notices.append((row["assignee_employee_id"], "task.reopened"))
            elif action == "due_date":
                if row["status"] not in ACTIVE:
                    raise ApiError(409, "TASK_TRANSITION_INVALID", "Task is no longer active")
                due = datetime.fromisoformat(payload["dueAt"]).astimezone(UTC)
                if due == row["due_at"]:
                    return await _unchanged(session, actor, task_id, record_id)
                values["due_at"] = due
                event = "Due Date Changed"
                notices.append((row["assignee_employee_id"], "task.due_date_changed"))
            elif action == "archive":
                if row["status"] not in {"Completed", "Cancelled"}:
                    raise ApiError(409, "TASK_TRANSITION_INVALID", "Task is not closed")
                values["archived_at"] = now
                event = "Archived"
            else:
                raise ApiError(422, "TASK_ACTION_INVALID", "Unsupported Task action")
        updated = (
            (
                await session.execute(
                    update(tasks).where(tasks.c.id == task_id).values(**values).returning(*tasks.c)
                )
            )
            .mappings()
            .one()
        )
        await _evidence(session, actor, task_id, event, _state(row), _state(dict(updated)), reason)
        for recipient, kind in notices:
            await _notice(session, task_id, recipient, kind)
        await complete(session, record_id, 200, {"taskId": str(task_id)})
        await session.commit()
        return await detail(session, actor, task_id)
    except Exception:
        await session.rollback()
        raise


async def _unchanged(session: AsyncSession, actor: Actor, task_id: UUID, record_id: UUID) -> dict:
    await complete(session, record_id, 200, {"taskId": str(task_id)})
    await session.commit()
    return await detail(session, actor, task_id)


async def _assignment_cycle_started_at(session: AsyncSession, task_id: UUID) -> datetime | None:
    return await session.scalar(
        select(task_history.c.created_at)
        .where(
            task_history.c.task_id == task_id,
            task_history.c.action.in_(("Created", "Reassigned")),
        )
        .order_by(task_history.c.created_at.desc(), task_history.c.id.desc())
        .limit(1)
    )


async def _viewed_in_current_cycle(session: AsyncSession, task_id: UUID, actor_id: UUID) -> bool:
    started = await _assignment_cycle_started_at(session, task_id)
    query = select(task_history.c.id).where(
        task_history.c.task_id == task_id,
        task_history.c.action == "Viewed",
        task_history.c.actor_employee_id == actor_id,
    )
    if started is not None:
        query = query.where(task_history.c.created_at >= started)
    return await session.scalar(query.limit(1)) is not None


async def mark_viewed(session: AsyncSession, actor: Actor, task_id: UUID, key: str) -> dict:
    """Record the assignee's first successful Task Detail open for this assignment cycle."""
    try:
        row = await scoped_task(session, actor, task_id, lock=True)
        payload = {"assigneeEmployeeId": str(row["assignee_employee_id"])}
        record_id, replay = await claim(session, actor, f"task.view:{task_id}", key, payload)
        if replay is not None:
            await session.rollback()
            return await detail(session, actor, task_id)
        if row["assignee_employee_id"] != actor.employee_id:
            return await _unchanged(session, actor, task_id, record_id)
        if await _viewed_in_current_cycle(session, task_id, actor.employee_id):
            return await _unchanged(session, actor, task_id, record_id)
        await _evidence(session, actor, task_id, "Viewed", None, _state(row))
        await complete(session, record_id, 200, {"taskId": str(task_id)})
        await session.commit()
        return await detail(session, actor, task_id)
    except Exception:
        await session.rollback()
        raise
