"""Idempotent seed of approved immutable reference data."""

import asyncio
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.organization import (
    designations,
    permissions,
    record_scope_config,
    role_permissions,
)
from app.db.session import session_factory
from app.policies import CASE_SCOPE, EMPLOYEE_SCOPE, PERMISSION_MATRIX

LOCKED_DESIGNATIONS = (
    "Owner",
    "Managing Director",
    "Sales Manager",
    "Coordinator",
    "Team Leader",
    "Sales Executive",
    "Admin Staff",
    "HR",
    "Finance",
)


async def seed() -> None:
    """Seed only locked identity, permission, and record-scope definitions."""
    async with session_factory()() as session:
        async with session.begin():
            for name in LOCKED_DESIGNATIONS:
                await session.execute(
                    insert(designations)
                    .values(id=uuid4(), name=name, locked=True)
                    .on_conflict_do_nothing(index_elements=[designations.c.name])
                )
            for key in sorted(set().union(*PERMISSION_MATRIX.values())):
                await session.execute(
                    insert(permissions)
                    .values(id=uuid4(), key=key, description=key)
                    .on_conflict_do_nothing(index_elements=[permissions.c.key])
                )
            role_rows = await session.execute(select(designations.c.name, designations.c.id))
            role_ids: dict[str, UUID] = {row.name: row.id for row in role_rows}
            permission_rows = await session.execute(select(permissions.c.key, permissions.c.id))
            permission_ids: dict[str, UUID] = {row.key: row.id for row in permission_rows}
            for role, keys in PERMISSION_MATRIX.items():
                for key in keys:
                    await session.execute(
                        insert(role_permissions)
                        .values(
                            id=uuid4(),
                            designation_id=role_ids[role],
                            permission_id=permission_ids[key],
                        )
                        .on_conflict_do_nothing(
                            constraint="role_permissions_designation_id_permission_id_key"
                        )
                    )
                await session.execute(
                    insert(record_scope_config)
                    .values(
                        id=uuid4(),
                        designation_id=role_ids[role],
                        resource="employee",
                        scope=EMPLOYEE_SCOPE[role],
                    )
                    .on_conflict_do_nothing(
                        constraint="record_scope_config_designation_id_resource_key"
                    )
                )
                await session.execute(
                    insert(record_scope_config)
                    .values(
                        id=uuid4(),
                        designation_id=role_ids[role],
                        resource="case",
                        scope=CASE_SCOPE[role],
                    )
                    .on_conflict_do_nothing(
                        constraint="record_scope_config_designation_id_resource_key"
                    )
                )


if __name__ == "__main__":
    asyncio.run(seed())
