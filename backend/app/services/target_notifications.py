"""Materialize effective Target notices from retained employee facts."""

from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import String, cast, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.operations import audit_events, notifications, targets
from app.db.organization import assignment_history, employees
from app.services.organization import dubai_today
from app.services.performance_math import DUBAI, assignment_on

MESSAGE = "Progress tracking against your applicable Target is active"
STATUS_ACTIONS = {"employee.activated", "employee.offboarded", "owner.bootstrap_enrolled"}


def _active_on(employee: dict, events: list[dict], day: date) -> bool:
    boundary = datetime.combine(day, time.max, tzinfo=DUBAI)
    if employee["created_at"] > boundary:
        return False
    previous = [event for event in events if event["occurred_at"] <= boundary]
    if previous:
        latest = max(previous, key=lambda event: (event["occurred_at"], str(event["id"])))
        return latest["action"] in {"employee.activated", "owner.bootstrap_enrolled"}
    if any(event["action"] == "employee.activated" for event in events):
        return False
    later_offboard = any(
        event["action"] == "employee.offboarded"
        and event["occurred_at"] > boundary
        and (event["before_values"] or {}).get("status") == "Active"
        for event in events
    )
    return employee["status"] == "Active" or later_offboard


async def dispatch_due(session: AsyncSession) -> dict:
    """Dispatch due versions in one task transaction, independently of HTTP auth."""
    today = dubai_today()
    finalized = (
        select(audit_events.c.id)
        .where(
            audit_events.c.action == "target.notification_finalized",
            audit_events.c.entity_type == "target",
            audit_events.c.entity_id == cast(targets.c.id, String),
        )
        .exists()
    )
    try:
        due = (
            (
                await session.execute(
                    select(targets)
                    .where(
                        targets.c.effective_date <= today,
                        (targets.c.inactive_from_date.is_(None))
                        | (targets.c.inactive_from_date > targets.c.effective_date),
                        (targets.c.effective_date == today) | ~finalized,
                    )
                    .order_by(targets.c.effective_date, targets.c.id)
                )
            )
            .mappings()
            .all()
        )
        created = 0
        for row in due:
            created += await dispatch_target(
                session, dict(row), today=today, finalize=row["effective_date"] < today
            )
        await session.commit()
        return {
            "status": "ok",
            "asOfDate": today.isoformat(),
            "dueTargetsExamined": len(due),
            "notificationsCreated": created,
        }
    except Exception:
        await session.rollback()
        raise


async def dispatch_target(
    session: AsyncSession, target: dict, *, today: date, finalize: bool = False
) -> int:
    locked = (
        (
            await session.execute(
                select(targets).where(targets.c.id == target["id"]).with_for_update()
            )
        )
        .mappings()
        .one()
    )
    target = dict(locked)
    if target["effective_date"] > today or (
        target["inactive_from_date"] is not None
        and target["inactive_from_date"] <= target["effective_date"]
    ):
        return 0
    if finalize and await session.scalar(
        select(audit_events.c.id).where(
            audit_events.c.action == "target.notification_finalized",
            audit_events.c.entity_type == "target",
            audit_events.c.entity_id == str(target["id"]),
        )
    ):
        return 0
    created = 0
    candidates = (
        (
            await session.execute(
                select(employees).where(employees.c.date_of_joining <= target["effective_date"])
            )
        )
        .mappings()
        .all()
    )
    for candidate in candidates:
        employee = dict(candidate)
        employee_id: UUID = employee["id"]
        assignments = [
            dict(row)
            for row in (
                await session.execute(
                    select(assignment_history).where(
                        assignment_history.c.employee_id == employee_id
                    )
                )
            ).mappings()
        ]
        if not assignments:
            assignments = [
                {
                    "id": employee_id,
                    "assignment_start_date": employee["date_of_joining"],
                    "assignment_end_date": None,
                    "branch_id": employee["branch_id"],
                    "department_id": employee["department_id"],
                    "designation_id": employee["designation_id"],
                }
            ]
        assignment = assignment_on(assignments, target["effective_date"])
        if assignment is None or any(
            assignment[key] != target[key]
            for key in ("branch_id", "department_id", "designation_id")
        ):
            continue
        events = [
            dict(row)
            for row in (
                await session.execute(
                    select(audit_events).where(
                        audit_events.c.entity_type == "employee",
                        audit_events.c.entity_id == str(employee_id),
                        audit_events.c.action.in_(STATUS_ACTIONS),
                    )
                )
            ).mappings()
        ]
        if not _active_on(employee, events, target["effective_date"]):
            continue
        if target["effective_date"] < today and await session.scalar(
            select(notifications.c.id).where(
                notifications.c.recipient_employee_id == employee_id,
                notifications.c.kind == "target.effective",
                notifications.c.target_id.is_(None),
                notifications.c.available_on == target["effective_date"],
                notifications.c.suppressed_at.is_(None),
            )
        ):
            # A retained, visible legacy notice already represents this Target date.
            continue
        result = await session.execute(
            insert(notifications)
            .values(
                recipient_employee_id=employee_id,
                target_id=target["id"],
                kind="target.effective",
                message=MESSAGE,
                available_on=target["effective_date"],
            )
            .on_conflict_do_nothing(
                index_elements=["target_id", "recipient_employee_id"],
                index_where=notifications.c.target_id.is_not(None),
            )
            .returning(notifications.c.id)
        )
        notification_id = result.scalar_one_or_none()
        if notification_id is not None:
            created += 1
            await audit.record(
                session,
                actor=None,
                action="target.notification_dispatched",
                module="targets",
                entity_type="notification",
                entity_id=notification_id,
                after={
                    "targetId": str(target["id"]),
                    "recipientEmployeeId": str(employee_id),
                    "effectiveDate": target["effective_date"].isoformat(),
                },
            )
    if finalize:
        await audit.record(
            session,
            actor=None,
            action="target.notification_finalized",
            module="targets",
            entity_type="target",
            entity_id=target["id"],
            after={"effectiveDate": target["effective_date"].isoformat()},
        )
    return created
