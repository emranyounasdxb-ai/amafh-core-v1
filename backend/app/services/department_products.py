"""Department Product classification used by Targets and Performance (DEC-052).

A Department's Target type comes from its explicit Product classification,
never from its display name, so renaming a Department keeps its Targets and
Rankings intact.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.cases import product_types
from app.db.operations import targets
from app.db.organization import departments
from app.errors import ApiError

TARGET_PRODUCT_CODES = frozenset({"CC", "PF"})


async def department_products(session: AsyncSession) -> dict[UUID, str]:
    rows = await session.execute(
        select(departments.c.id, product_types.c.code).join(
            product_types, product_types.c.id == departments.c.product_type_id
        )
    )
    return {ident: code for ident, code in rows.all() if code in TARGET_PRODUCT_CODES}


async def require_target_product(session: AsyncSession, product_type_id: UUID) -> None:
    code = await session.scalar(
        select(product_types.c.code)
        .where(product_types.c.id == product_type_id, product_types.c.active.is_(True))
        .with_for_update(read=True)
    )
    if code not in TARGET_PRODUCT_CODES:
        raise ApiError(
            422,
            "INVALID_TARGET_PRODUCT",
            "Choose an active Credit Card or Personal Finance product",
        )


async def require_unreferenced(session: AsyncSession, department_id: UUID) -> None:
    """Targets keep the Department classification they were created under."""
    if await session.scalar(select(targets.c.id).where(targets.c.department_id == department_id)):
        raise ApiError(
            409,
            "DEPARTMENT_CLASSIFICATION_LOCKED",
            "This Department has Targets, so its Target product cannot change",
        )


async def department_product(session: AsyncSession, department_id: UUID) -> str | None:
    code = await session.scalar(
        select(product_types.c.code)
        .join(departments, departments.c.product_type_id == product_types.c.id)
        .where(departments.c.id == department_id)
    )
    return code if code in TARGET_PRODUCT_CODES else None
