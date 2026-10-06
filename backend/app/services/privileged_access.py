"""Owner-only management boundary for Owner and Managing Director accounts."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import employees, user_accounts
from app.errors import ApiError
from app.policies import Actor

PRIVILEGED_ACCOUNT_ROLES = frozenset({"Owner", "Managing Director"})


def require_owner_for_privileged_account(actor: Actor, target_role: str | None) -> None:
    if target_role in PRIVILEGED_ACCOUNT_ROLES and actor.designation != "Owner":
        raise ApiError(403, "FORBIDDEN", "Only the Owner can manage this account")


async def lock_employee(session: AsyncSession, employee_id: UUID) -> None:
    """Serialize role changes with account and password-link decisions."""
    await session.execute(
        select(employees.c.id).where(employees.c.id == employee_id).with_for_update()
    )


async def lock_account_employee(session: AsyncSession, account_id: UUID) -> None:
    employee_id = await session.scalar(
        select(user_accounts.c.employee_id).where(user_accounts.c.id == account_id)
    )
    if employee_id is not None:
        await lock_employee(session, employee_id)
