"""Recipient-scoped Notification Center reads and read-state commands."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.cases import cases
from app.db.operations import notifications
from app.db.organization import employees, team_memberships, teams
from app.errors import ApiError
from app.policies import Actor
from app.repositories.case_scope import visible_case
from app.repositories.employee_scope import employee_query
from app.services import case_import_reads

DUBAI = ZoneInfo("Asia/Dubai")

SAFE_MESSAGES = {
    "case.pending_approval": "A Case is awaiting approval",
    "case.approved": "A Case was assigned to you",
    "case.final_status": "A Case reached a final status",
    "case.stage_updated": "A Case stage was updated",
    "case.booked": "A Case was booked",
    "case.csv_upload_result": "A Bank-stage CSV upload result is available",
    "case.pending_approval_reminder": "A Case is awaiting approval",
    "case.stage_delayed_reminder": "A Case stage requires attention",
    "employee.assignment_changed": "Your employee assignment was updated",
    "employee.offboarded": "An employee access update is available",
    "user.disabled": "An employee access update is available",
    "team.membership_changed": "A Team membership was updated",
    "finance.clawback_recorded": "A Clawback was recorded",
    "finance.payment_recorded": "A payment record was entered",
    "attendance.upload_result": "An Attendance upload result is available",
    "target.effective": "Your Target progress tracking is active",
    "hr_document.approval_requested": "An HR document is awaiting approval",
}


def _public(row) -> dict:
    kind = row["kind"]
    message = SAFE_MESSAGES.get(kind)
    if message is None and kind.startswith("asset."):
        message = "An Asset status changed"
    if message is None and kind.startswith("task."):
        message = "A Task update is available"
    return {
        "id": row["id"],
        "kind": kind,
        "message": message or "You have a notification",
        "availableOn": row["available_on"],
        "createdAt": row["created_at"],
        "readAt": row["read_at"],
    }


def _own_visible(actor: Actor):
    return (
        notifications.c.recipient_employee_id == actor.employee_id,
        notifications.c.suppressed_at.is_(None),
        notifications.c.available_on <= datetime.now(DUBAI).date(),
    )


async def list_notifications(
    session: AsyncSession,
    actor: Actor,
    *,
    read_status: Literal["all", "read", "unread"],
    kind: str | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
) -> dict:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ApiError(422, "DATE_RANGE_INVALID", "Start Date must not follow End Date")
    query = select(notifications).where(*_own_visible(actor))
    if read_status == "read":
        query = query.where(notifications.c.read_at.is_not(None))
    elif read_status == "unread":
        query = query.where(notifications.c.read_at.is_(None))
    if kind is not None:
        query = query.where(notifications.c.kind == kind)
    created_day = func.date(func.timezone("Asia/Dubai", notifications.c.created_at))
    if date_from is not None:
        query = query.where(created_day >= date_from)
    if date_to is not None:
        query = query.where(created_day <= date_to)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (
        (
            await session.execute(
                query.order_by(notifications.c.created_at.desc(), notifications.c.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    return {
        "items": [_public(row) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


async def unread_count(session: AsyncSession, actor: Actor) -> dict:
    count = await session.scalar(
        select(func.count())
        .select_from(notifications)
        .where(*_own_visible(actor), notifications.c.read_at.is_(None))
    )
    return {"count": count or 0}


async def mark_read(session: AsyncSession, actor: Actor, notification_id: UUID) -> dict:
    try:
        row = (
            (
                await session.execute(
                    select(notifications)
                    .where(notifications.c.id == notification_id, *_own_visible(actor))
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        if row["read_at"] is None:
            row = (
                (
                    await session.execute(
                        update(notifications)
                        .where(notifications.c.id == notification_id)
                        .values(read_at=func.now())
                        .returning(*notifications.c)
                    )
                )
                .mappings()
                .one()
            )
        result = _public(row)
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        raise


async def mark_all_read(session: AsyncSession, actor: Actor) -> dict:
    try:
        result = await session.execute(
            update(notifications)
            .where(*_own_visible(actor), notifications.c.read_at.is_(None))
            .values(read_at=func.now())
            .returning(notifications.c.id)
        )
        count = len(result.scalars().all())
        await session.commit()
        return {"markedCount": count}
    except Exception:
        await session.rollback()
        raise


async def destination(session: AsyncSession, actor: Actor, notification_id: UUID) -> dict:
    row = (
        (
            await session.execute(
                select(
                    notifications.c.case_id,
                    notifications.c.task_id,
                    notifications.c.csv_import_batch_id,
                    notifications.c.employee_id,
                    notifications.c.team_id,
                ).where(notifications.c.id == notification_id, *_own_visible(actor))
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if row["case_id"] is not None:
        case_id = await session.scalar(
            select(cases.c.id).where(cases.c.id == row["case_id"], visible_case(actor))
        )
        if case_id is not None:
            return {"path": f"/api/v1/cases/{case_id}"}
    if row["task_id"] is not None:
        from app.services.task_reads import task_visible_by_id

        if await task_visible_by_id(session, actor, row["task_id"]):
            return {"path": f"/api/v1/tasks/{row['task_id']}"}
    if row["csv_import_batch_id"] is not None:
        batch = await case_import_reads.visible_batch(session, actor, row["csv_import_batch_id"])
        if batch is not None:
            return {"path": f"/api/v1/case-imports/bank-stage/{row['csv_import_batch_id']}"}
    if row["employee_id"] is not None:
        employee = (
            await session.execute(employee_query(actor).where(employees.c.id == row["employee_id"]))
        ).first()
        if employee is not None:
            return {"path": f"/api/v1/employees/{row['employee_id']}"}
    if row["team_id"] is not None:
        team = await session.scalar(select(teams.c.id).where(teams.c.id == row["team_id"]))
        if team is not None and "team.write" in actor.grants:
            return {"path": f"/api/v1/teams/{team}"}
        if team is not None and actor.designation == "Team Leader":
            visible_team = await session.scalar(
                select(teams.c.id).where(
                    teams.c.id == team,
                    teams.c.leader_employee_id == actor.employee_id,
                    teams.c.active.is_(True),
                )
            )
            if visible_team is not None:
                return {"path": f"/api/v1/teams/{team}"}
        if team is not None:
            membership = await session.scalar(
                select(team_memberships.c.id).where(
                    team_memberships.c.team_id == team,
                    team_memberships.c.employee_id == actor.employee_id,
                )
            )
            if membership is not None:
                employee = (
                    await session.execute(
                        employee_query(actor).where(employees.c.id == actor.employee_id)
                    )
                ).first()
                if employee is not None:
                    return {"path": f"/api/v1/employees/{actor.employee_id}"}
    raise ApiError(404, "NOT_FOUND", "Record unavailable")
