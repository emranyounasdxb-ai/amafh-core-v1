"""Transactional idempotency records for duplicate-sensitive commands."""

import hashlib
import json
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.operations import idempotency_records
from app.errors import ApiError
from app.policies import Actor


def request_hash(payload: object) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(data).hexdigest()


async def claim(
    session: AsyncSession,
    actor: Actor,
    operation: str,
    key: str,
    payload: object,
) -> tuple[UUID, dict | None]:
    if len(key) < 8 or len(key) > 150 or not key.isascii():
        raise ApiError(422, "IDEMPOTENCY_KEY_INVALID", "A valid Idempotency-Key is required")
    digest = request_hash(payload)
    await session.execute(
        insert(idempotency_records)
        .values(
            id=uuid4(),
            actor_employee_id=actor.employee_id,
            operation=operation,
            idempotency_key=key,
            request_hash=digest,
        )
        .on_conflict_do_nothing(
            index_elements=[
                idempotency_records.c.actor_employee_id,
                idempotency_records.c.operation,
                idempotency_records.c.idempotency_key,
            ]
        )
    )
    row = (
        (
            await session.execute(
                select(idempotency_records)
                .where(
                    idempotency_records.c.actor_employee_id == actor.employee_id,
                    idempotency_records.c.operation == operation,
                    idempotency_records.c.idempotency_key == key,
                )
                .with_for_update()
            )
        )
        .mappings()
        .one()
    )
    if row["request_hash"] != digest:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "This key was used for a different request")
    return row["id"], row["response_json"] if row["response_status"] is not None else None


async def complete(session: AsyncSession, record_id: UUID, status: int, result: dict) -> None:
    await session.execute(
        update(idempotency_records)
        .where(idempotency_records.c.id == record_id)
        .values(response_status=status, response_json=result)
    )
