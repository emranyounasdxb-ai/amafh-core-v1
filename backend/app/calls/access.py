"""Owner-only individual Calls grants, independent of User Type action permissions."""

from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.calls.policy import CALLS_ROLES, calls_access
from app.db.base import utcnow
from app.db.organization import branches, designations, employees, user_accounts
from app.errors import ApiError
from app.policies import Actor
from app.services.privileged_access import lock_account_employee


def require_owner(actor: Actor) -> None:
    if actor.designation != "Owner":
        raise ApiError(403, "FORBIDDEN", "Only the Owner can manage individual Calls access")


def _query():
    return select(
        user_accounts.c.id,
        user_accounts.c.employee_id,
        user_accounts.c.access_status,
        user_accounts.c.calls_access_granted,
        user_accounts.c.calls_access_revision,
        user_accounts.c.calls_access_updated_at,
        employees.c.full_name,
        employees.c.company_employee_code,
        employees.c.avatar_file_id,
        employees.c.status.label("employee_status"),
        designations.c.name.label("designation"),
        branches.c.name.label("branch"),
    ).select_from(
        user_accounts.join(employees, user_accounts.c.employee_id == employees.c.id)
        .join(designations, employees.c.designation_id == designations.c.id)
        .outerjoin(branches, employees.c.branch_id == branches.c.id)
    )


def _view(row) -> dict:
    granted = calls_access(row["designation"], row["calls_access_granted"])
    return {
        "id": str(row["id"]),
        "employeeId": str(row["employee_id"]),
        "name": row["full_name"],
        "employeeCode": row["company_employee_code"],
        "avatarFileId": str(row["avatar_file_id"]) if row["avatar_file_id"] else None,
        "designation": row["designation"],
        "branch": row["branch"],
        "accountStatus": row["access_status"],
        "employeeStatus": row["employee_status"],
        "granted": granted,
        "effective": granted
        and row["access_status"] == "Active"
        and row["employee_status"] == "Active",
        "fixed": row["designation"] == "Owner",
        "revision": row["calls_access_revision"],
        "changedAt": row["calls_access_updated_at"].isoformat()
        if row["calls_access_updated_at"]
        else None,
    }


async def list_access(
    session: AsyncSession, actor: Actor, *, query: str, page: int, page_size: int
) -> dict:
    require_owner(actor)
    conditions = [designations.c.name.in_(CALLS_ROLES), employees.c.status != "Offboarded"]
    if query.strip():
        conditions.append(
            or_(
                employees.c.full_name.icontains(query.strip(), autoescape=True),
                employees.c.company_employee_code.icontains(query.strip(), autoescape=True),
                designations.c.name.icontains(query.strip(), autoescape=True),
            )
        )
    statement = _query().where(*conditions)
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (
        await session.execute(
            statement.order_by(employees.c.full_name, user_accounts.c.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).mappings()
    return {
        "items": [_view(row) for row in rows],
        "total": int(total or 0),
        "page": page,
        "pageSize": page_size,
    }


async def set_access(
    session: AsyncSession, actor: Actor, account_id: UUID, *, granted: bool, revision: int
) -> dict:
    require_owner(actor)
    # Keep the employee -> account order used by transfers, account security and recovery.
    await lock_account_employee(session, account_id)
    row = (
        (
            await session.execute(
                _query().where(user_accounts.c.id == account_id).with_for_update(of=user_accounts)
            )
        )
        .mappings()
        .first()
    )
    if row is None or row["employee_status"] == "Offboarded":
        raise ApiError(404, "NOT_FOUND", "Account unavailable")
    if row["designation"] == "Owner":
        raise ApiError(422, "CALLS_OWNER_PROTECTED", "Owner Calls access is fixed")
    if row["designation"] not in CALLS_ROLES:
        raise ApiError(422, "CALLS_ROLE_BOUNDARY", "This User Type cannot access Calls")
    if row["calls_access_revision"] != revision:
        raise ApiError(
            409,
            "CALLS_ACCESS_CONFLICT",
            "Calls access changed. Refresh and review the saved value.",
        )
    if row["calls_access_granted"] != granted:
        now = utcnow()
        await session.execute(
            update(user_accounts)
            .where(user_accounts.c.id == account_id)
            .values(
                calls_access_granted=granted,
                calls_access_revision=revision + 1,
                calls_access_updated_at=now,
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="calls.access_changed",
            module="calls",
            entity_type="user_account",
            entity_id=account_id,
            before={"granted": row["calls_access_granted"]},
            after={"granted": granted},
            context={"employeeId": str(row["employee_id"]), "designation": row["designation"]},
        )
        await session.commit()
    updated = (
        (await session.execute(_query().where(user_accounts.c.id == account_id))).mappings().one()
    )
    return _view(updated)
