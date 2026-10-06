"""Employee email as the sign-in identifier: one email, at most one enabled account."""

import re
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import employees, user_accounts
from app.errors import ApiError
from app.repositories.identity import stored_email

EMAIL_SHAPE = re.compile(r"[^@\s]+@[^@\s]+")


def normalize(value: str) -> str:
    return value.strip().lower()


async def guard_unique(session: AsyncSession, email: str, employee_id: UUID) -> None:
    """Reject an email already used by another employee's account that is not Disabled.

    Not Provisioned accounts count because completing setup activates them without HR action.
    The transaction lock serializes concurrent commands for the same email.
    """
    key = normalize(email)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"login_email:{key}"},
    )
    clash = await session.scalar(
        select(user_accounts.c.id)
        .join(employees, user_accounts.c.employee_id == employees.c.id)
        .where(
            stored_email() == key,
            employees.c.id != employee_id,
            user_accounts.c.access_status != "Disabled",
        )
        .limit(1)
    )
    if clash:
        raise ApiError(
            409, "EMAIL_IN_USE", "This email address is already used by another sign-in account"
        )
