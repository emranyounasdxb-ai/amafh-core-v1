"""Allowlisted permanent audit events, kept in command transactions."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.db.operations import audit_events


def _safe_values(values: dict | None) -> dict | None:
    if values is None:
        return None

    def clean(value):
        if isinstance(value, dict):
            return {
                key: "[REDACTED]"
                if any(
                    secret in key.lower()
                    for secret in (
                        "password",
                        "token",
                        "secret",
                        "cookie",
                        "csrf",
                        "session",
                    )
                )
                else clean(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    return clean(values)


async def record(
    session: AsyncSession,
    *,
    actor: UUID | None,
    action: str,
    module: str,
    entity_type: str | None = None,
    entity_id: UUID | str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    context: dict | None = None,
) -> None:
    # Callers pass only approved business values. Authentication secrets are never accepted here.
    await session.execute(
        audit_events.insert().values(
            actor_employee_id=actor,
            action=action,
            module=module,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            occurred_at=utcnow(),
            before_values=_safe_values(before),
            after_values=_safe_values(after),
            context=_safe_values(context) or {},
        )
    )
