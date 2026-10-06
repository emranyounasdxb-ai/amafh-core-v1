"""Identity row resolution; no authorization decisions live here."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import designations, employees, user_accounts


def stored_email():
    """Also matches rows saved before emails were trimmed and lowercased on write."""
    return func.lower(func.btrim(employees.c.personal_email))


def account_query():
    return (
        select(
            user_accounts.c.id.label("account_id"),
            user_accounts.c.password_hash,
            user_accounts.c.access_status,
            user_accounts.c.failed_attempts,
            user_accounts.c.locked_at,
            employees.c.id.label("employee_id"),
            employees.c.full_name,
            employees.c.status.label("employee_status"),
            employees.c.branch_id,
            employees.c.department_id,
            employees.c.designation_id,
            designations.c.name.label("designation"),
        )
        .join(employees, user_accounts.c.employee_id == employees.c.id)
        .join(designations, employees.c.designation_id == designations.c.id)
    )


async def by_email(session: AsyncSession, email: str):
    """Every account whose employee email matches; the caller must reject ambiguity."""
    result = await session.execute(
        account_query()
        .where(stored_email() == email)
        .order_by(user_accounts.c.id)
        .with_for_update(of=user_accounts)
    )
    return result.mappings().all()


async def by_account_id(session: AsyncSession, account_id: UUID):
    result = await session.execute(account_query().where(user_accounts.c.id == account_id))
    return result.mappings().first()
