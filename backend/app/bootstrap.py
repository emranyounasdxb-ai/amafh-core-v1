"""Idempotent seed of approved immutable reference data."""

import asyncio
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.cases import product_types
from app.db.organization import (
    branches,
    departments,
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
OPERATING_CITIES = ("Dubai", "Abu Dhabi")


async def seed(*, departments_seeded: bool = True) -> None:
    """Seed reference data for the head schema.

    ``departments_seeded=False`` skips Departments and the Branch operating city,
    whose classification columns only exist from revisions 20261004p12a and
    20261004p12aot; upgrade rehearsals use it for older schemas.
    """
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
            for name in OPERATING_CITIES:
                if departments_seeded and await session.scalar(
                    select(branches.c.id).where(branches.c.operating_city == name)
                ):
                    continue
                await session.execute(
                    insert(branches)
                    .values(
                        id=uuid4(),
                        name=name,
                        **({"operating_city": name} if departments_seeded else {}),
                    )
                    .on_conflict_do_nothing(index_elements=[branches.c.name])
                )
            for name, code in (("Credit Card", "CC"), ("Personal Finance", "PF")):
                await session.execute(
                    insert(product_types)
                    .values(id=uuid4(), name=name, code=code)
                    .on_conflict_do_nothing(index_elements=[product_types.c.code])
                )
            if not departments_seeded:
                return
            product_ids: dict[str, UUID] = {
                row["code"]: row["id"]
                for row in (
                    await session.execute(select(product_types.c.code, product_types.c.id))
                ).mappings()
            }
            branch_ids = (
                await session.scalars(
                    select(branches.c.id).where(branches.c.operating_city.is_not(None))
                )
            ).all()
            for branch_id in branch_ids:
                for name, code in (("Credit Card Sales", "CC"), ("Personal Finance Sales", "PF")):
                    classified = await session.scalar(
                        select(departments.c.id).where(
                            departments.c.branch_id == branch_id,
                            departments.c.product_type_id == product_ids[code],
                        )
                    )
                    if classified:
                        continue
                    await session.execute(
                        insert(departments)
                        .values(
                            id=uuid4(),
                            branch_id=branch_id,
                            name=name,
                            product_type_id=product_ids[code],
                        )
                        .on_conflict_do_nothing(constraint="departments_branch_id_name_key")
                    )


if __name__ == "__main__":
    asyncio.run(seed())
