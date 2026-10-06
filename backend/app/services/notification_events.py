"""Transactional, permission-safe recipients for documented business notices."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.operations import notifications
from app.db.organization import designations, employees, user_accounts


async def notify(
    session: AsyncSession,
    recipients: set[UUID],
    kind: str,
    message: str,
    *,
    case_id: UUID | None = None,
    csv_import_batch_id: UUID | None = None,
    employee_id: UUID | None = None,
    team_id: UUID | None = None,
) -> None:
    for recipient_id in sorted(recipients, key=str):
        await session.execute(
            notifications.insert().values(
                id=uuid4(),
                recipient_employee_id=recipient_id,
                kind=kind,
                case_id=case_id,
                csv_import_batch_id=csv_import_batch_id,
                employee_id=employee_id,
                team_id=team_id,
                message=message,
            )
        )


async def active_roles(session: AsyncSession, roles: set[str]) -> set[UUID]:
    return set(
        (
            await session.scalars(
                select(employees.c.id)
                .join(designations, designations.c.id == employees.c.designation_id)
                .join(user_accounts, user_accounts.c.employee_id == employees.c.id)
                .where(
                    designations.c.name.in_(roles),
                    employees.c.status == "Active",
                    user_accounts.c.access_status == "Active",
                )
            )
        ).all()
    )


async def access_changed(session: AsyncSession, kind: str, employee_id: UUID) -> None:
    await notify(
        session,
        await active_roles(session, {"HR", "Owner", "Managing Director"}),
        kind,
        "An employee access update is available",
        employee_id=employee_id,
    )
