"""Identity row resolution; no authorization decisions live here."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import (
    designations,
    employees,
    permissions,
    role_permissions,
    sessions,
    user_accounts,
)


def stored_email():
    """Only the explicitly configured, account-owned login identifier."""
    return func.lower(func.btrim(user_accounts.c.login_email))


def account_query():
    return (
        select(
            user_accounts.c.id.label("account_id"),
            user_accounts.c.password_hash,
            user_accounts.c.access_status,
            user_accounts.c.failed_attempts,
            user_accounts.c.locked_at,
            user_accounts.c.calls_access_granted,
            employees.c.id.label("employee_id"),
            employees.c.full_name,
            employees.c.avatar_file_id,
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
    """Every matching account; the caller must reject ambiguity."""
    result = await session.execute(
        account_query().where(stored_email() == email).order_by(user_accounts.c.id)
    )
    return result.mappings().all()


async def by_account_id(session: AsyncSession, account_id: UUID):
    result = await session.execute(account_query().where(user_accounts.c.id == account_id))
    return result.mappings().first()


async def session_snapshot(session: AsyncSession, digest: str):
    """One fresh statement for session, identity and configured permission facts.

    Keep the session when an identity join is missing, so the service can still
    invalidate it using the existing policy. No password hash or raw token is read.
    """
    grants = (
        select(func.array_agg(permissions.c.key))
        .select_from(
            role_permissions.join(permissions, role_permissions.c.permission_id == permissions.c.id)
        )
        .where(
            role_permissions.c.designation_id == designations.c.id,
            role_permissions.c.granted.is_(True),
        )
        .correlate(designations)
        .scalar_subquery()
    )
    source = (
        sessions.outerjoin(user_accounts, sessions.c.account_id == user_accounts.c.id)
        .outerjoin(employees, user_accounts.c.employee_id == employees.c.id)
        .outerjoin(designations, employees.c.designation_id == designations.c.id)
    )
    result = await session.execute(
        select(
            sessions.c.id,
            sessions.c.invalidated_at,
            sessions.c.last_active_at,
            sessions.c.csrf_hash,
            user_accounts.c.id.label("account_id"),
            user_accounts.c.access_status,
            user_accounts.c.locked_at,
            user_accounts.c.calls_access_granted,
            employees.c.id.label("employee_id"),
            employees.c.full_name,
            employees.c.status.label("employee_status"),
            employees.c.branch_id,
            employees.c.department_id,
            designations.c.name.label("designation"),
            grants.label("configured_grants"),
        )
        .select_from(source)
        .where(sessions.c.token_hash == digest)
    )
    return result.mappings().first()
