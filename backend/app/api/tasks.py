"""Authenticated Task queues, retained history, and lifecycle commands."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query
from pydantic import AwareDatetime

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.schemas.tasks import (
    Priority,
    Status,
    TaskCreate,
    TaskDueInput,
    TaskHistoryPage,
    TaskItem,
    TaskPage,
    TaskReasonInput,
    TaskReassignInput,
    TaskRelatedDestination,
    TaskRelatedOptionPage,
    TaskReopenInput,
    TaskStatusInput,
)
from app.services import task_commands, task_reads, task_related_options

router = APIRouter(tags=["tasks"])


@router.get("/tasks", response_model=TaskPage)
async def task_list(
    db: Db,
    actor: ActorDep,
    view: Literal[
        "active", "assigned", "created", "management", "overdue", "history", "archived"
    ] = "active",
    priority: Priority | None = None,
    status: Status | None = None,
    assigneeId: UUID | None = None,
    dueFrom: AwareDatetime | None = None,
    dueTo: AwareDatetime | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    q: str = Query("", max_length=128),
    sort: Literal["title", "dueAt", "createdAt", "status", "priority", "isOverdue"] = "dueAt",
    direction: Literal["asc", "desc"] = "asc",
):
    return await task_reads.list_tasks(
        db,
        actor,
        view=view,
        priority=priority,
        status=status,
        assignee_id=assigneeId,
        due_from=dueFrom,
        due_to=dueTo,
        page=page,
        page_size=pageSize,
        q=q,
        sort=sort,
        direction=direction,
    )


@router.post("/tasks", response_model=TaskItem, status_code=201)
async def create_task(
    item: TaskCreate,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await task_commands.create(db, actor, item, idempotency_key)


@router.get("/tasks/related-options", response_model=TaskRelatedOptionPage)
async def task_related_options_list(
    db: Db,
    actor: ActorDep,
    relatedType: str,
    q: str = "",
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=50),
):
    return await task_related_options.related_options(
        db, actor, related_type=relatedType, q=q, page=page, page_size=pageSize
    )


@router.get("/tasks/{task_id}", response_model=TaskItem)
async def task_detail(task_id: UUID, db: Db, actor: ActorDep):
    return await task_reads.detail(db, actor, task_id)


@router.get("/tasks/{task_id}/history", response_model=TaskHistoryPage)
async def task_history(
    task_id: UUID,
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
):
    return await task_reads.history(db, actor, task_id, page, pageSize)


@router.get("/tasks/{task_id}/related", response_model=TaskRelatedDestination)
async def task_related(task_id: UUID, db: Db, actor: ActorDep):
    return await task_reads.related_destination(db, actor, task_id)


@router.post("/tasks/{task_id}/status", response_model=TaskItem)
async def change_status(
    task_id: UUID,
    item: TaskStatusInput,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await task_commands.command(
        db, actor, task_id, "status", item.model_dump(mode="json"), idempotency_key
    )


@router.post("/tasks/{task_id}/reassign", response_model=TaskItem)
async def reassign_task(
    task_id: UUID,
    item: TaskReassignInput,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await task_commands.command(
        db, actor, task_id, "reassign", item.model_dump(mode="json"), idempotency_key
    )


@router.post("/tasks/{task_id}/cancel", response_model=TaskItem)
async def cancel_task(
    task_id: UUID,
    item: TaskReasonInput,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await task_commands.command(
        db, actor, task_id, "cancel", item.model_dump(mode="json"), idempotency_key
    )


@router.post("/tasks/{task_id}/reopen", response_model=TaskItem)
async def reopen_task(
    task_id: UUID,
    item: TaskReopenInput,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await task_commands.command(
        db, actor, task_id, "reopen", item.model_dump(mode="json"), idempotency_key
    )


@router.post("/tasks/{task_id}/due-date", response_model=TaskItem)
async def change_task_due(
    task_id: UUID,
    item: TaskDueInput,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await task_commands.command(
        db, actor, task_id, "due_date", item.model_dump(mode="json"), idempotency_key
    )


@router.post("/tasks/{task_id}/archive", response_model=TaskItem)
async def archive_task(
    task_id: UUID,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await task_commands.command(db, actor, task_id, "archive", {}, idempotency_key)


@router.post("/tasks/{task_id}/view", response_model=TaskItem)
async def view_task(
    task_id: UUID,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await task_commands.mark_viewed(db, actor, task_id, idempotency_key)
