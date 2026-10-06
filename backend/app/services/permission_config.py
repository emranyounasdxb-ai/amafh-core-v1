"""Owner-managed User Type permission configuration."""

import hashlib
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.bootstrap import LOCKED_DESIGNATIONS
from app.db.base import utcnow
from app.db.organization import designations, employees, permissions, role_permissions
from app.errors import ApiError
from app.permission_catalog import (
    MODULES,
    PERMISSION_LABELS,
    RESTRICTIONS,
    SCOPE_LABELS,
    data_scope,
    fixed_reason,
)
from app.policies import (
    ALL_PERMISSIONS,
    PERMISSION_MATRIX,
    Actor,
    is_configurable,
    require,
)
from app.repositories import permissions as permission_rows

BOUNDARY_MESSAGE = (
    "This action conflicts with a fixed business-role or security boundary. No change was saved."
)


def _order(key: str) -> tuple[int, str]:
    module, action = PERMISSION_LABELS[key]
    return MODULES.index(module), action


def _revision(rows: dict[str, dict]) -> str:
    """Changes whenever any stored grant of the User Type changes."""
    text = "|".join(f"{key}:{rows[key]['granted']}" for key in sorted(rows))
    return hashlib.sha256(text.encode()).hexdigest()[:16]


async def _stored(session: AsyncSession, designation_id: UUID, lock: bool = False):
    query = (
        select(
            permissions.c.key,
            role_permissions.c.granted,
            role_permissions.c.updated_at,
            employees.c.full_name.label("updated_by"),
        )
        .select_from(
            role_permissions.join(
                permissions, role_permissions.c.permission_id == permissions.c.id
            ).outerjoin(employees, role_permissions.c.updated_by_employee_id == employees.c.id)
        )
        .where(role_permissions.c.designation_id == designation_id)
    )
    if lock:
        query = query.with_for_update(of=role_permissions)
    return {row["key"]: dict(row) for row in (await session.execute(query)).mappings()}


def _user_type(row, stored: dict[str, dict], usage: int) -> dict:
    name = row["name"]
    boundary = PERMISSION_MATRIX[name]
    items = []
    for key in sorted(ALL_PERMISSIONS, key=_order):
        module, action = PERMISSION_LABELS[key]
        if is_configurable(name, key):
            state = "granted" if stored.get(key, {}).get("granted") else "revoked"
        elif key in boundary:
            state = "fixed"
        else:
            state = "unavailable"
        items.append(
            {
                "key": key,
                "module": module,
                "action": action,
                "state": state,
                "configurable": state in {"granted", "revoked"},
                "dataScope": SCOPE_LABELS[data_scope(name, key)] if key in boundary else None,
                "reason": fixed_reason(name, key),
            }
        )
    changed = [value for value in stored.values() if value["updated_at"] is not None]
    latest = max(changed, key=lambda value: value["updated_at"]) if changed else None
    return {
        "id": str(row["id"]),
        "name": name,
        "employeeCount": usage,
        "revision": _revision(stored),
        "lastChangedAt": latest["updated_at"].isoformat() if latest else None,
        "lastChangedBy": (latest["updated_by"] or "Unavailable") if latest else None,
        "permissions": items,
    }


async def _usage(session: AsyncSession) -> dict[UUID, int]:
    result = await session.execute(
        select(employees.c.designation_id, func.count())
        .where(employees.c.status != "Offboarded")
        .group_by(employees.c.designation_id)
    )
    return {designation_id: count for designation_id, count in result.all()}


async def effective(session: AsyncSession, actor: Actor) -> list[dict]:
    """Each User Type's currently effective grants."""
    require(actor, "permissions.read")
    names = sorted((await session.execute(select(designations.c.name))).scalars())
    rows = []
    for name in names:
        for key in sorted(await permission_rows.actor_grants(session, name)):
            rows.append({"designation": name, "key": key})
    return rows


async def read(session: AsyncSession, actor: Actor) -> dict:
    require(actor, "permissions.read")
    rows = (await session.execute(select(designations.c.id, designations.c.name))).mappings()
    ordered = sorted(rows, key=lambda row: LOCKED_DESIGNATIONS.index(row["name"]))
    usage = await _usage(session)
    user_types = [
        _user_type(row, await _stored(session, row["id"]), usage.get(row["id"], 0))
        for row in ordered
    ]
    return {
        "canManage": "permissions.write" in actor.grants,
        "userTypes": user_types,
        "restrictions": list(RESTRICTIONS),
    }


async def update(
    session: AsyncSession,
    actor: Actor,
    designation_id: UUID,
    revision: str,
    grants: dict[str, bool],
) -> dict:
    require(actor, "permissions.write")
    row = (
        (
            await session.execute(
                select(designations.c.id, designations.c.name)
                .where(designations.c.id == designation_id)
                .with_for_update()
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "User Type unavailable")
    name = row["name"]
    unknown = sorted(key for key in grants if key not in ALL_PERMISSIONS)
    if unknown:
        raise ApiError(422, "VALIDATION_ERROR", "Unknown permission. No change was saved.")
    if any(not is_configurable(name, key) for key in grants):
        raise ApiError(422, "PERMISSION_BOUNDARY", BOUNDARY_MESSAGE)
    stored = await _stored(session, designation_id, lock=True)
    if revision != _revision(stored):
        raise ApiError(
            409,
            "PERMISSION_CONFLICT",
            "These permissions changed after you opened them. Reload to review the saved values.",
        )
    changes = {
        key: granted
        for key, granted in grants.items()
        if bool(stored.get(key, {}).get("granted")) != granted
    }
    if changes:
        now = utcnow()
        ids: dict[str, UUID] = {
            row["key"]: row["id"]
            for row in (
                await session.execute(
                    select(permissions.c.key, permissions.c.id).where(
                        permissions.c.key.in_(sorted(changes))
                    )
                )
            ).mappings()
        }
        for key, granted in changes.items():
            statement = insert(role_permissions).values(
                designation_id=designation_id,
                permission_id=ids[key],
                granted=granted,
                updated_at=now,
                updated_by_employee_id=actor.employee_id,
            )
            await session.execute(
                statement.on_conflict_do_update(
                    constraint="role_permissions_designation_id_permission_id_key",
                    set_={
                        "granted": statement.excluded.granted,
                        "updated_at": statement.excluded.updated_at,
                        "updated_by_employee_id": statement.excluded.updated_by_employee_id,
                    },
                )
            )

        def granted_actions(values: dict[str, bool]) -> list[str]:
            return sorted(
                PERMISSION_LABELS[key][1]
                for key in PERMISSION_MATRIX[name]
                if is_configurable(name, key) and values.get(key)
            )

        before = {key: bool(value["granted"]) for key, value in stored.items()}
        await audit.record(
            session,
            actor=actor.employee_id,
            action="permissions.updated",
            module="settings",
            entity_type="designation",
            entity_id=designation_id,
            before={"userType": name, "grantedActions": granted_actions(before)},
            after={"userType": name, "grantedActions": granted_actions(before | changes)},
            context={
                "changes": [
                    {
                        "module": PERMISSION_LABELS[key][0],
                        "action": PERMISSION_LABELS[key][1],
                        "granted": granted,
                    }
                    for key, granted in sorted(changes.items(), key=lambda item: _order(item[0]))
                ]
            },
        )
        await session.commit()
    return await read(session, actor)
