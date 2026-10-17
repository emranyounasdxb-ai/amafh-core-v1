"""PostgreSQL catalog reads. Search does not call the connector or the filesystem."""

import re
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.calls.contract import SOURCE_KEY
from app.calls.policy import MAX_PAGE_SIZE
from app.config import settings
from app.db.base import utcnow
from app.db.calls import call_recording_sources, call_recording_sync_state, call_recordings

_PHONE = r"^[0-9]{10}$"
_MONTH = r"^[0-9]{4}-(0[1-9]|1[0-2])$"


def _phase(row, *, configured: bool, catalog_ready: bool) -> str:
    if not configured:
        return "not_configured"
    if row is None:
        return "indexing" if catalog_ready is False else "offline"
    phase = row["phase"]
    heartbeat = row["heartbeat_at"]
    if heartbeat is not None:
        age = (utcnow() - heartbeat).total_seconds()
        if age > settings().calls_sync_interval_seconds * 3 and phase == "ready":
            return "offline"
    if not catalog_ready and phase == "ready":
        return "indexing"
    return phase


def source_view(source, state, *, configured: bool) -> dict:
    catalog_ready = bool(source and int(source["catalog_generation"]) > 0)
    return {
        "configured": configured,
        "phase": _phase(state, configured=configured, catalog_ready=catalog_ready),
        "lastIndexedAt": _iso(None if state is None else state["last_indexed_at"]),
        "lastSynchronizedAt": _iso(None if state is None else state["last_synchronized_at"]),
        "catalogReady": catalog_ready,
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


async def _rows(session: AsyncSession):
    source = (
        await session.execute(
            select(call_recording_sources).where(call_recording_sources.c.source_key == SOURCE_KEY)
        )
    ).mappings().first()
    state = None
    if source is not None:
        state = (
            await session.execute(
                select(call_recording_sync_state).where(
                    call_recording_sync_state.c.source_id == source["id"]
                )
            )
        ).mappings().first()
    return source, state


async def status(session: AsyncSession) -> dict:
    from app.calls.client import outbound_configured

    source, state = await _rows(session)
    return source_view(source, state, configured=outbound_configured())


async def months(session: AsyncSession) -> dict:
    view = await status(session)
    if not view["configured"] or not view["catalogReady"]:
        return {"months": [], "source": view}
    rows = await session.execute(
        select(call_recordings.c.month)
        .join(
            call_recording_sources,
            call_recording_sources.c.id == call_recordings.c.source_id,
        )
        .where(
            call_recording_sources.c.source_key == SOURCE_KEY,
            call_recordings.c.catalog_generation == call_recording_sources.c.catalog_generation,
            text("call_recordings.availability = 'ready'"),
        )
        .group_by(call_recordings.c.month)
        .order_by(call_recordings.c.month.desc())
    )
    return {"months": [row[0] for row in rows], "source": view}


async def search(session: AsyncSession, month: str, phone: str, page: int, page_size: int) -> dict:
    view = await status(session)
    empty = {
        "month": month,
        "customerNumber": phone,
        "page": page,
        "pageSize": page_size,
        "total": 0,
        "source": view,
        "recordings": [],
    }
    if not view["configured"] or not view["catalogReady"]:
        return empty
    where = (
        call_recording_sources.c.source_key == SOURCE_KEY,
        call_recordings.c.catalog_generation == call_recording_sources.c.catalog_generation,
        call_recordings.c.month == month,
        call_recordings.c.customer_number == phone,
        text("call_recordings.availability = 'ready'"),
    )
    joined = call_recordings.join(
        call_recording_sources,
        call_recording_sources.c.id == call_recordings.c.source_id,
    )
    total = await session.scalar(select(func.count()).select_from(joined).where(*where))
    rows = (
        await session.execute(
            select(
                call_recordings.c.id,
                call_recordings.c.month,
                call_recordings.c.customer_number,
                call_recordings.c.extension,
                call_recordings.c.filename,
                call_recordings.c.byte_size,
            )
            .select_from(joined)
            .where(*where)
            .order_by(call_recordings.c.filename, call_recordings.c.id)
            .limit(min(page_size, MAX_PAGE_SIZE))
            .offset((page - 1) * page_size)
        )
    ).mappings()
    return {
        **empty,
        "total": int(total or 0),
        "recordings": [
            {
                "id": str(row["id"]),
                "month": row["month"],
                "customerNumber": row["customer_number"],
                "extension": row["extension"],
                "filename": row["filename"],
                "byteSize": int(row["byte_size"]),
            }
            for row in rows
        ],
    }


def recording_values(source_id: UUID, generation: int, item: dict) -> dict | None:
    availability = item.get("availability")
    phone = item.get("customerNumber")
    month = item.get("month")
    filename = item.get("filename")
    connector_id = item.get("id")
    if availability not in {"ready", "missing"}:
        return None
    if not isinstance(phone, str) or phone != phone.strip():
        return None
    if re.fullmatch(_PHONE, phone) is None or re.fullmatch(_MONTH, str(month or "")) is None:
        return None
    if (
        not isinstance(filename, str)
        or not filename
        or any(mark in filename for mark in "\r\n\0/\\")
    ):
        return None
    if not isinstance(connector_id, str) or len(connector_id) > 36:
        return None
    indexed = item.get("indexedAt")
    try:
        indexed_at = datetime.fromisoformat(indexed) if isinstance(indexed, str) else None
    except ValueError:
        indexed_at = None
    return {
        "id": uuid4(),
        "source_id": source_id,
        "catalog_generation": generation,
        "connector_id": connector_id,
        "month": month,
        "customer_number": phone,
        "extension": str(item.get("extension") or "")[:32],
        "filename": filename[:255],
        "byte_size": int(item.get("byteSize") or 0),
        "file_version": str(item.get("fileVersion") or ""),
        "availability": availability,
        "source_sequence": int(item.get("sequence") or 0),
        "indexed_at": indexed_at,
        "synchronized_at": utcnow(),
    }


async def apply_recording_batch(
    session: AsyncSession, source_id: UUID, generation: int, items: list[dict]
) -> int:
    rows = []
    for item in items:
        value = recording_values(source_id, generation, item)
        if value is not None:
            rows.append(value)
    if not rows:
        return 0
    statement = pg_insert(call_recordings).values(rows)
    excluded = statement.excluded
    statement = statement.on_conflict_do_update(
        constraint="uq_call_recordings_identity",
        set_={
            "month": excluded.month,
            "customer_number": excluded.customer_number,
            "extension": excluded.extension,
            "filename": excluded.filename,
            "byte_size": excluded.byte_size,
            "file_version": excluded.file_version,
            "availability": excluded.availability,
            "source_sequence": excluded.source_sequence,
            "indexed_at": excluded.indexed_at,
            "synchronized_at": excluded.synchronized_at,
        },
        where=call_recordings.c.source_sequence < excluded.source_sequence,
    )
    await session.execute(statement)
    return len(rows)
