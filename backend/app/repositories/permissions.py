"""Persisted User Type permission configuration; decisions live in app.policies."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import designations, permissions, role_permissions
from app.policies import effective_grants


async def configured_grants(session: AsyncSession, designation: str) -> set[str]:
    result = await session.execute(
        select(permissions.c.key)
        .select_from(
            role_permissions.join(
                permissions, role_permissions.c.permission_id == permissions.c.id
            ).join(designations, role_permissions.c.designation_id == designations.c.id)
        )
        .where(designations.c.name == designation, role_permissions.c.granted.is_(True))
    )
    return set(result.scalars())


async def actor_grants(session: AsyncSession, designation: str) -> frozenset[str]:
    """Read on every request, so a saved change applies to existing sessions immediately."""
    return effective_grants(designation, await configured_grants(session, designation))
