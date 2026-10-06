"""Independent, retained dispatch of pending and certified delayed Case notices."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.cases import (
    case_lifecycle_history,
    case_notice_events,
    case_stage_history,
    cases,
    pipeline_stages,
)
from app.db.operations import notifications
from app.db.organization import designations, employees, user_accounts
from app.services.performance_delay import count_delayed
from app.services.performance_math import DUBAI


async def _managers(session: AsyncSession, branch_id: UUID, department_id: UUID) -> set[UUID]:
    return set(
        (
            await session.scalars(
                select(employees.c.id)
                .join(designations, designations.c.id == employees.c.designation_id)
                .join(user_accounts, user_accounts.c.employee_id == employees.c.id)
                .where(
                    designations.c.name == "Sales Manager",
                    employees.c.branch_id == branch_id,
                    employees.c.department_id == department_id,
                    employees.c.status == "Active",
                    user_accounts.c.access_status == "Active",
                )
            )
        ).all()
    )


async def _active_recipients(session: AsyncSession, ids: set[UUID]) -> set[UUID]:
    if not ids:
        return set()
    return set(
        (
            await session.scalars(
                select(employees.c.id)
                .join(user_accounts, user_accounts.c.employee_id == employees.c.id)
                .where(
                    employees.c.id.in_(ids),
                    employees.c.status == "Active",
                    user_accounts.c.access_status == "Active",
                )
            )
        ).all()
    )


async def _cycle(session: AsyncSession, case: dict, now: datetime):
    if case["current_status"] == "Pending for Approval":
        event = (
            (
                await session.execute(
                    select(case_lifecycle_history)
                    .where(
                        case_lifecycle_history.c.case_id == case["id"],
                        case_lifecycle_history.c.status == "Pending for Approval",
                    )
                    .order_by(
                        case_lifecycle_history.c.occurred_at.desc(),
                        case_lifecycle_history.c.id.desc(),
                    )
                    .limit(1)
                )
            )
            .mappings()
            .one_or_none()
        )
        start = event["occurred_at"] if event else case["created_at"]
        recipients = await _managers(session, case["branch_id"], case["department_id"])
        kind = "pending_approval"
    elif case["current_status"] == "Booked" and case["current_stage"] is not None:
        event = (
            (
                await session.execute(
                    select(case_stage_history)
                    .where(case_stage_history.c.case_id == case["id"])
                    .order_by(
                        case_stage_history.c.occurred_at.desc(), case_stage_history.c.id.desc()
                    )
                    .limit(1)
                )
            )
            .mappings()
            .one_or_none()
        )
        if event is None or event["stage"] != case["current_stage"]:
            return None
        expected = await session.scalar(
            select(pipeline_stages.c.expected_business_days).where(
                pipeline_stages.c.pipeline_configuration_id == case["pipeline_configuration_id"],
                pipeline_stages.c.name == case["current_stage"],
            )
        )
        if expected is None:
            return None
        start = event["occurred_at"]
        delayed, state = await count_delayed(
            session,
            [(case["id"], start.astimezone(DUBAI).date(), expected)],
            now.astimezone(DUBAI).date(),
        )
        if state != "Available" or not delayed:
            return None
        recipients = await _active_recipients(
            session, {case["owner_employee_id"], case["coordinator_employee_id"]} - {None}
        )
        recipients |= await _managers(session, case["branch_id"], case["department_id"])
        kind = "stage_delayed"
    else:
        return None
    if kind == "pending_approval" and now - start < timedelta(hours=24):
        return None
    if not recipients:
        return None
    return kind, start, recipients


async def dispatch_due(session: AsyncSession, *, now: datetime | None = None) -> dict:
    """Run from a scheduler later; no login or request path calls this function."""
    instant = now or utcnow()
    created = 0
    last_id: UUID | None = None
    try:
        while True:
            query = (
                select(cases)
                .where(
                    cases.c.administratively_voided_at.is_(None),
                    cases.c.current_status.in_({"Pending for Approval", "Booked"}),
                )
                .order_by(cases.c.id)
                .limit(100)
                .with_for_update(of=cases, skip_locked=True)
            )
            if last_id is not None:
                query = query.where(cases.c.id > last_id)
            rows = (await session.execute(query)).mappings().all()
            if not rows:
                break
            for row in rows:
                cycle = await _cycle(session, dict(row), instant)
                if cycle is None:
                    continue
                kind, start, recipients = cycle
                prior = {
                    recipient: (last_index, last_sent_at)
                    for recipient, last_index, last_sent_at in (
                        await session.execute(
                            select(
                                case_notice_events.c.recipient_employee_id,
                                func.max(case_notice_events.c.interval_index),
                                func.max(case_notice_events.c.created_at),
                            )
                            .where(
                                case_notice_events.c.case_id == row["id"],
                                case_notice_events.c.kind == kind,
                                case_notice_events.c.cycle_started_at == start,
                            )
                            .group_by(case_notice_events.c.recipient_employee_id)
                        )
                    ).all()
                }
                for recipient in sorted(recipients, key=str):
                    last_index, last_sent_at = prior.get(recipient, (0, None))
                    if last_sent_at is not None and instant - last_sent_at < timedelta(hours=24):
                        continue
                    index = last_index + 1
                    notice_id = uuid4()
                    await session.execute(
                        notifications.insert().values(
                            id=notice_id,
                            recipient_employee_id=recipient,
                            kind=f"case.{kind}_reminder",
                            case_id=row["id"],
                            message="A Case requires attention",
                            available_on=instant.astimezone(DUBAI).date(),
                            created_at=instant,
                        )
                    )
                    await session.execute(
                        case_notice_events.insert().values(
                            id=uuid4(),
                            case_id=row["id"],
                            kind=kind,
                            cycle_started_at=start,
                            interval_index=index,
                            recipient_employee_id=recipient,
                            notification_id=notice_id,
                            created_at=instant,
                        )
                    )
                    await audit.record(
                        session,
                        actor=None,
                        action=f"case.{kind}_notified",
                        module="cases",
                        entity_type="case",
                        entity_id=row["id"],
                        context={"notificationId": str(notice_id), "intervalIndex": index},
                    )
                    created += 1
            last_id = rows[-1]["id"]
            await session.commit()
        return {"notificationsCreated": created}
    except Exception:
        await session.rollback()
        raise
