"""Server-scoped Task queues, details, and retained history."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.db.tasks import task_history, tasks
from app.errors import ApiError
from app.policies import Actor
from app.schemas.tasks import TaskItem
from app.services.task_policy import ACTIVE, may_link, visible_task


async def task_visible_by_id(session: AsyncSession, actor: Actor, task_id: UUID) -> bool:
    return (
        await session.scalar(select(tasks.c.id).where(tasks.c.id == task_id, visible_task(actor)))
        is not None
    )


async def scoped_task(
    session: AsyncSession, actor: Actor, task_id: UUID, *, lock: bool = False
) -> dict:
    query = select(tasks).where(tasks.c.id == task_id, visible_task(actor))
    if lock:
        query = query.with_for_update()
    row = (await session.execute(query)).mappings().one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return dict(row)


async def public_task(session: AsyncSession, actor: Actor, row: dict) -> dict:
    linked = row["related_id"] is not None
    link_visible = bool(
        linked and await may_link(session, actor, row["related_type"], row["related_id"])
    )
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "creatorEmployeeId": row["creator_employee_id"],
        "assigneeEmployeeId": row["assignee_employee_id"],
        "branchId": row["branch_id"],
        "departmentId": row["department_id"],
        "teamId": row["team_id"],
        "priority": row["priority"],
        "status": row["status"],
        "dueAt": row["due_at"],
        "completedAt": row["completed_at"],
        "archivedAt": row["archived_at"],
        "isOverdue": row["status"] in ACTIVE
        and row["archived_at"] is None
        and row["due_at"] < utcnow(),
        "relatedType": row["related_type"] if link_visible else None,
        "relatedId": row["related_id"] if link_visible else None,
        "relatedUnavailable": linked and not link_visible,
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


async def detail(session: AsyncSession, actor: Actor, task_id: UUID) -> dict:
    return await public_task(session, actor, await scoped_task(session, actor, task_id))


async def creation_replay(session: AsyncSession, actor: Actor, outcome: dict) -> dict:
    """Return the retained creation response after applying current read access."""
    task_id = UUID(outcome.get("id") or outcome["taskId"])
    row = await scoped_task(session, actor, task_id)
    current = await public_task(session, actor, row)

    if "title" in outcome:
        original = outcome
    else:
        created = await session.scalar(
            select(task_history.c.after_values)
            .where(task_history.c.task_id == task_id, task_history.c.action == "Created")
            .order_by(task_history.c.created_at, task_history.c.id)
            .limit(1)
        )
        if created is None:
            raise ApiError(
                500,
                "TASK_REPLAY_UNAVAILABLE",
                "The original Task creation result is unavailable",
            )
        original = {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "creatorEmployeeId": row["creator_employee_id"],
            "assigneeEmployeeId": created["assigneeEmployeeId"],
            "branchId": created["branchId"],
            "departmentId": created["departmentId"],
            "teamId": created["teamId"],
            "priority": row["priority"],
            "status": created["status"],
            "dueAt": created["dueAt"],
            "completedAt": created["completedAt"],
            "archivedAt": created["archivedAt"],
            "isOverdue": False,
            "relatedType": created["relatedType"],
            "relatedId": created["relatedId"],
            "relatedUnavailable": False,
            "createdAt": row["created_at"],
            "updatedAt": row["created_at"],
        }

    result = TaskItem.model_validate(original).model_dump(mode="python")
    if current["relatedUnavailable"]:
        result["relatedType"] = None
        result["relatedId"] = None
        result["relatedUnavailable"] = True
    return result


async def list_tasks(
    session: AsyncSession,
    actor: Actor,
    *,
    view: Literal["active", "assigned", "created", "management", "overdue", "history", "archived"],
    priority: str | None,
    status: str | None,
    assignee_id: UUID | None,
    due_from: datetime | None,
    due_to: datetime | None,
    page: int,
    page_size: int,
    q: str = "",
    sort: str,
    direction: str,
) -> dict:
    if due_from is not None and due_to is not None and due_from > due_to:
        raise ApiError(422, "DATE_RANGE_INVALID", "Start Date must not follow End Date")
    order = {
        "title": tasks.c.title,
        "dueAt": tasks.c.due_at,
        "createdAt": tasks.c.created_at,
        "status": tasks.c.status,
        "priority": tasks.c.priority,
        "isOverdue": case(
            (
                tasks.c.status.in_(ACTIVE)
                & tasks.c.archived_at.is_(None)
                & (tasks.c.due_at < func.now()),
                True,
            ),
            else_=False,
        ),
    }.get(sort)
    if order is None or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    query = select(tasks).where(visible_task(actor))
    if view in {"active", "assigned", "created", "management", "overdue"}:
        query = query.where(tasks.c.status.in_(ACTIVE), tasks.c.archived_at.is_(None))
    elif view == "history":
        query = query.where(
            tasks.c.status.in_({"Completed", "Cancelled"}), tasks.c.archived_at.is_(None)
        )
    else:
        query = query.where(tasks.c.archived_at.is_not(None))
    if view == "assigned":
        query = query.where(tasks.c.assignee_employee_id == actor.employee_id)
    if view == "created":
        query = query.where(tasks.c.creator_employee_id == actor.employee_id)
    if view == "management" and actor.designation not in {
        "Owner",
        "Managing Director",
        "Sales Manager",
        "Team Leader",
    }:
        raise ApiError(403, "FORBIDDEN", "Access denied")
    if view == "overdue":
        query = query.where(tasks.c.due_at < func.now())
    if priority is not None:
        query = query.where(tasks.c.priority == priority)
    if status is not None:
        query = query.where(tasks.c.status == status)
    if assignee_id is not None:
        query = query.where(tasks.c.assignee_employee_id == assignee_id)
    if due_from is not None:
        query = query.where(tasks.c.due_at >= due_from)
    if due_to is not None:
        query = query.where(tasks.c.due_at <= due_to)
    term = q.strip()
    if term:
        pattern = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(
            or_(
                tasks.c.title.ilike(pattern, escape="\\"),
                cast(tasks.c.assignee_employee_id, String).ilike(pattern, escape="\\"),
                tasks.c.related_type.ilike(pattern, escape="\\"),
            )
        )
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (
        (
            await session.execute(
                query.order_by(
                    (order.asc() if direction == "asc" else order.desc()).nulls_last(),
                    tasks.c.id,
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    return {
        "items": [await public_task(session, actor, dict(row)) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


async def history(
    session: AsyncSession, actor: Actor, task_id: UUID, page: int, page_size: int
) -> dict:
    task = await scoped_task(session, actor, task_id)
    linked = task["related_id"] is not None
    link_visible = bool(
        linked and await may_link(session, actor, task["related_type"], task["related_id"])
    )
    query = select(task_history).where(task_history.c.task_id == task_id)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (
        (
            await session.execute(
                query.order_by(task_history.c.created_at.desc(), task_history.c.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    items = []
    for row in rows:
        before = dict(row["before_values"]) if row["before_values"] else None
        after = dict(row["after_values"])
        if not link_visible:
            for values in (before, after):
                if values is not None:
                    values.pop("relatedType", None)
                    values.pop("relatedId", None)
        items.append(
            {
                "id": row["id"],
                "taskId": row["task_id"],
                "action": row["action"],
                "actorEmployeeId": row["actor_employee_id"],
                "reason": row["reason"],
                "beforeValues": before,
                "afterValues": after,
                "createdAt": row["created_at"],
            }
        )
    return {"items": items, "total": total, "page": page, "pageSize": page_size}


async def related_destination(session: AsyncSession, actor: Actor, task_id: UUID) -> dict:
    task = await scoped_task(session, actor, task_id)
    kind, related_id = task["related_type"], task["related_id"]
    if kind is None or related_id is None or not await may_link(session, actor, kind, related_id):
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    root = {
        "case": "cases",
        "customer": "customers",
        "employee": "employees",
        "asset": "assets",
        "attendance": "attendance",
        "attendance_import": "attendance/imports",
        "finance_result": "finance/completed-cases",
        "clawback": "finance/clawbacks",
        "payment": "finance/payments",
    }[kind]
    if kind == "finance_result":
        from app.db.finance import case_financial_results

        related_id = await session.scalar(
            select(case_financial_results.c.case_id).where(
                case_financial_results.c.id == related_id
            )
        )
    return {"path": f"/api/v1/{root}/{related_id}"}
