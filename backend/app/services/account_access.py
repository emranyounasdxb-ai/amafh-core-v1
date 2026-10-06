"""User-account provisioning and lifecycle transitions."""

from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.organization import designations, employees, user_accounts
from app.errors import ApiError
from app.policies import Actor, require
from app.services import login_email
from app.services.notification_events import access_changed
from app.services.privileged_access import (
    lock_account_employee,
    require_owner_for_privileged_account,
)


async def provision_account(session: AsyncSession, actor: Actor, employee_id: UUID) -> UUID:
    require(actor, "access.write")
    row = (
        (
            await session.execute(
                select(employees).where(employees.c.id == employee_id).with_for_update()
            )
        )
        .mappings()
        .first()
    )
    if not row or row["status"] != "Active" or not row["branch_id"] or not row["department_id"]:
        raise ApiError(422, "INCOMPLETE_EMPLOYEE", "Employee is not eligible for access")
    target_role = await session.scalar(
        select(designations.c.name).where(designations.c.id == row["designation_id"])
    )
    require_owner_for_privileged_account(actor, target_role)
    if await session.scalar(
        select(user_accounts.c.id).where(user_accounts.c.employee_id == employee_id)
    ):
        raise ApiError(409, "CONFLICT", "Account already exists")
    await login_email.guard_unique(session, row["personal_email"], employee_id)
    account_id = uuid4()
    await session.execute(
        user_accounts.insert().values(
            id=account_id, employee_id=employee_id, access_status="Not Provisioned"
        )
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="user.provisioned",
        module="users",
        entity_type="user_account",
        entity_id=account_id,
    )
    await session.commit()
    return account_id


async def disable_account(session: AsyncSession, actor: Actor, account_id: UUID) -> None:
    require(actor, "access.write")
    await lock_account_employee(session, account_id)
    account = (
        (
            await session.execute(
                select(user_accounts, designations.c.name.label("designation"))
                .join(employees, user_accounts.c.employee_id == employees.c.id)
                .outerjoin(designations, employees.c.designation_id == designations.c.id)
                .where(user_accounts.c.id == account_id)
                .with_for_update(of=user_accounts)
            )
        )
        .mappings()
        .first()
    )
    if not account:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if account["designation"] == "Owner":
        raise ApiError(403, "OWNER_PROTECTED", "The Owner's login access cannot be disabled.")
    require_owner_for_privileged_account(actor, account["designation"])
    from app.db.organization import password_tokens, sessions

    now = utcnow()
    await session.execute(
        update(user_accounts)
        .where(user_accounts.c.id == account_id)
        .values(access_status="Disabled")
    )
    await session.execute(
        update(password_tokens)
        .where(password_tokens.c.account_id == account_id, password_tokens.c.used_at.is_(None))
        .values(invalidated_at=now)
    )
    await session.execute(
        update(sessions)
        .where(sessions.c.account_id == account_id, sessions.c.invalidated_at.is_(None))
        .values(invalidated_at=now)
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="user.disabled",
        module="users",
        entity_type="user_account",
        entity_id=account_id,
        before={"accessStatus": account["access_status"]},
        after={"accessStatus": "Disabled"},
    )
    await access_changed(session, "user.disabled", account["employee_id"])
    await session.commit()


async def enable_account(session: AsyncSession, actor: Actor, account_id: UUID) -> None:
    require(actor, "access.write")
    await lock_account_employee(session, account_id)
    row = (
        (
            await session.execute(
                select(
                    user_accounts.c.id,
                    user_accounts.c.access_status,
                    user_accounts.c.employee_id,
                    employees.c.status,
                    employees.c.branch_id,
                    employees.c.department_id,
                    employees.c.personal_email,
                    designations.c.name.label("designation"),
                )
                .join(employees, user_accounts.c.employee_id == employees.c.id)
                .join(designations, employees.c.designation_id == designations.c.id)
                .where(user_accounts.c.id == account_id)
                .with_for_update(of=user_accounts)
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    require_owner_for_privileged_account(actor, row["designation"])
    if row["status"] != "Active" or not row["branch_id"] or not row["department_id"]:
        raise ApiError(422, "INCOMPLETE_EMPLOYEE", "Employee is not eligible for access")
    if row["access_status"] != "Disabled":
        raise ApiError(409, "CONFLICT", "Account is not disabled")
    await login_email.guard_unique(session, row["personal_email"], row["employee_id"])
    await session.execute(
        update(user_accounts)
        .where(user_accounts.c.id == account_id)
        .values(
            access_status="Not Provisioned",
            password_hash=None,
            failed_attempts=0,
            locked_at=None,
        )
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="user.enabled",
        module="users",
        entity_type="user_account",
        entity_id=account_id,
        before={"accessStatus": "Disabled"},
        after={"accessStatus": "Not Provisioned"},
    )
    await session.commit()
