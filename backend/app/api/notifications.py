"""Authenticated Notification Center routes."""

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.schemas.notifications import (
    MarkAllResult,
    NotificationDestination,
    NotificationItem,
    NotificationPage,
    UnreadCount,
)
from app.services import notification_reads

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=NotificationPage)
async def notifications_list(
    db: Db,
    actor: ActorDep,
    readStatus: Literal["all", "read", "unread"] = "all",
    kind: str | None = Query(None, min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_.]*$"),
    dateFrom: date | None = None,
    dateTo: date | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
):
    return await notification_reads.list_notifications(
        db,
        actor,
        read_status=readStatus,
        kind=kind,
        date_from=dateFrom,
        date_to=dateTo,
        page=page,
        page_size=pageSize,
    )


@router.get("/notifications/unread-count", response_model=UnreadCount)
async def notification_unread_count(db: Db, actor: ActorDep):
    return await notification_reads.unread_count(db, actor)


@router.post("/notifications/read-all", response_model=MarkAllResult)
async def notifications_mark_all_read(db: Db, actor: CsrfActor):
    return await notification_reads.mark_all_read(db, actor)


@router.post("/notifications/{notification_id}/read", response_model=NotificationItem)
async def notification_mark_read(notification_id: UUID, db: Db, actor: CsrfActor):
    return await notification_reads.mark_read(db, actor, notification_id)


@router.get("/notifications/{notification_id}/destination", response_model=NotificationDestination)
async def notification_destination(notification_id: UUID, db: Db, actor: ActorDep):
    return await notification_reads.destination(db, actor, notification_id)
