"""Pull the connector catalog. Network I/O stays outside database transactions.

A claim token is checked in the same locked statement that writes the cursor,
snapshot, error, or publication. The source row is locked before the sync row.
An older token cannot publish. Calls does not use the Email worker or its caps.
"""

import asyncio
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.calls import client
from app.calls.catalog import apply_recording_batch
from app.calls.client import ConnectorFailure, outbound_configured
from app.calls.contract import SOURCE_KEY
from app.config import settings
from app.db.base import utcnow
from app.db.calls import call_recording_sources, call_recording_sync_state, call_recordings
from app.db.session import session_factory

_task: asyncio.Task | None = None
_stop = asyncio.Event()


async def start_worker() -> None:
    global _task
    if not settings().calls_enabled or _task is not None:
        return
    _stop.clear()
    _task = asyncio.create_task(_loop())


async def stop_worker() -> None:
    global _task
    if _task is None:
        return
    _stop.set()
    await _task
    _task = None
    _stop.clear()


async def _loop() -> None:
    while not _stop.is_set():
        if outbound_configured():
            try:
                await run_once()
            except Exception:
                await asyncio.sleep(0)
        try:
            await asyncio.wait_for(_stop.wait(), timeout=settings().calls_sync_interval_seconds)
        except TimeoutError:
            continue


async def run_once() -> None:
    if not outbound_configured():
        return
    claimed = await _claim()
    if claimed is None:
        return
    source_id, token = claimed
    try:
        status = await client.get_status()
        await _write(source_id, token, _heartbeat(status))
        state = await _read_state(source_id)
        if state is None:
            return
        if _needs_snapshot(state, status):
            await _snapshot(source_id, token, status)
        else:
            await _deltas(source_id, token)
    except ConnectorFailure as exc:
        if exc.code == "cursor_expired":
            await _write(source_id, token, _arm_snapshot)
        else:
            await _fail(source_id, token, exc.code)
    finally:
        await _release(source_id, token)


def _needs_snapshot(state, status: dict) -> bool:
    epoch = status.get("epoch")
    if not epoch or state["published_epoch"] != epoch:
        return True
    return state["snapshot_generation"] is not None


async def _claim() -> tuple[UUID, UUID] | None:
    async with session_factory()() as session:
        source = await _ensure_source(session)
        await session.execute(
            select(call_recording_sources.c.id)
            .where(call_recording_sources.c.id == source)
            .with_for_update()
        )
        now = utcnow()
        token = uuid4()
        until = now + timedelta(seconds=settings().calls_sync_lease_seconds)
        row = (
            await session.execute(
                update(call_recording_sync_state)
                .where(
                    call_recording_sync_state.c.source_id == source,
                    or_(
                        call_recording_sync_state.c.status != "leased",
                        call_recording_sync_state.c.lease_until < now,
                    ),
                )
                .values(
                    status="leased",
                    claim_token=token,
                    lease_until=until,
                    heartbeat_at=now,
                )
                .returning(call_recording_sync_state.c.source_id)
            )
        ).first()
        if row is None:
            await session.rollback()
            return None
        await session.commit()
        return source, token


async def _ensure_source(session: AsyncSession) -> UUID:
    existing = await session.scalar(
        select(call_recording_sources.c.id).where(call_recording_sources.c.source_key == SOURCE_KEY)
    )
    if existing is None:
        source_id = uuid4()
        await session.execute(
            call_recording_sources.insert().values(
                id=source_id,
                source_key=SOURCE_KEY,
                display_name=settings().calls_source_name[:80],
                enabled=True,
                catalog_generation=0,
            )
        )
        await session.execute(
            call_recording_sync_state.insert().values(
                source_id=source_id,
                status="idle",
                phase="indexing",
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await session.scalar(
                select(call_recording_sources.c.id).where(
                    call_recording_sources.c.source_key == SOURCE_KEY
                )
            )
            if existing is None:
                raise
            return existing
        return source_id
    return existing


async def _owned(session: AsyncSession, source_id: UUID, token: UUID):
    await session.execute(
        select(call_recording_sources.c.id)
        .where(call_recording_sources.c.id == source_id)
        .with_for_update()
    )
    return (
        await session.execute(
            select(call_recording_sync_state)
            .where(
                call_recording_sync_state.c.source_id == source_id,
                call_recording_sync_state.c.claim_token == token,
                call_recording_sync_state.c.status == "leased",
            )
            .with_for_update()
        )
    ).mappings().first()


async def _write(source_id: UUID, token: UUID, apply) -> bool:
    async with session_factory()() as session:
        state = await _owned(session, source_id, token)
        if state is None:
            await session.rollback()
            return False
        await apply(session, state)
        await session.commit()
        return True


async def _read_state(source_id: UUID):
    async with session_factory()() as session:
        return (
            await session.execute(
                select(call_recording_sync_state).where(
                    call_recording_sync_state.c.source_id == source_id
                )
            )
        ).mappings().first()


def _heartbeat(status: dict):
    async def apply(session: AsyncSession, locked) -> None:
        indexed = status.get("lastIndexedAt")
        try:
            indexed_at = datetime.fromisoformat(indexed) if isinstance(indexed, str) else None
        except ValueError:
            indexed_at = None
        phase = _connector_phase(status)
        await session.execute(
            update(call_recording_sync_state)
            .where(call_recording_sync_state.c.source_id == locked["source_id"])
            .values(
                heartbeat_at=utcnow(),
                last_indexed_at=indexed_at,
                phase=phase,
                error_code=None,
                lease_until=utcnow() + timedelta(seconds=settings().calls_sync_lease_seconds),
            )
        )

    return apply


def _connector_phase(status: dict) -> str:
    if status.get("phase") == "offline":
        return "offline"
    if status.get("phase") != "ready" or not status.get("indexReady"):
        return "indexing"
    return "ready"


async def _arm_snapshot(session: AsyncSession, state) -> None:
    await session.execute(
        update(call_recording_sync_state)
        .where(call_recording_sync_state.c.source_id == state["source_id"])
        .values(
            snapshot_epoch=None,
            snapshot_generation=None,
            snapshot_cursor="",
            snapshot_journal_max=None,
            phase="updating",
        )
    )


async def _fail(source_id: UUID, token: UUID, code: str) -> None:
    async def apply(session: AsyncSession, state) -> None:
        await session.execute(
            update(call_recording_sync_state)
            .where(call_recording_sync_state.c.source_id == state["source_id"])
            .values(
                phase="offline",
                error_code=code[:40],
                error_count=int(state["error_count"]) + 1,
                heartbeat_at=utcnow(),
            )
        )

    await _write(source_id, token, apply)


async def _release(source_id: UUID, token: UUID) -> None:
    async def apply(session: AsyncSession, state) -> None:
        await session.execute(
            update(call_recording_sync_state)
            .where(
                call_recording_sync_state.c.source_id == state["source_id"],
                call_recording_sync_state.c.claim_token == token,
            )
            .values(status="idle", claim_token=None, lease_until=None)
        )

    await _write(source_id, token, apply)


async def _deltas(source_id: UUID, token: UUID) -> None:
    while not _stop.is_set():
        state = await _read_state(source_id)
        if state is None:
            return
        try:
            page = await client.get_changes(
                int(state["applied_sequence"]), settings().calls_sync_batch
            )
        except ConnectorFailure as exc:
            if exc.code == "cursor_expired":
                await _write(source_id, token, _arm_snapshot)
                fresh = await _read_state(source_id)
                status = await client.get_status()
                if fresh is not None:
                    await _snapshot(source_id, token, status)
                return
            raise
        generation = await _active_generation(source_id)
        if generation <= 0:
            status = await client.get_status()
            await _snapshot(source_id, token, status)
            return
        if not _same_epoch(page, state["published_epoch"]):
            await _write(source_id, token, _arm_snapshot)
            return

        async def apply(
            session: AsyncSession, locked, generation=generation, page=page
        ) -> None:
            await apply_recording_batch(session, source_id, generation, page["changes"])
            await session.execute(
                update(call_recording_sync_state)
                .where(call_recording_sync_state.c.source_id == locked["source_id"])
                .values(
                    applied_sequence=int(page["through"]),
                    last_synchronized_at=utcnow(),
                    phase=locked["phase"],
                    error_code=None,
                    lease_until=utcnow() + timedelta(seconds=settings().calls_sync_lease_seconds),
                )
            )

        if not await _write(source_id, token, apply):
            return
        if int(page["through"]) >= int(page["journalMax"]) or not page["changes"]:
            return


def _same_epoch(page, epoch) -> bool:
    if not isinstance(page, dict):
        return False
    return str(page.get("epoch") or "") == str(epoch or "")


async def _journal_covers(after: int, epoch: str) -> bool:
    """False when the watermark's epoch or sequence can no longer be replayed."""
    try:
        page = await client.get_changes(after, 1)
    except ConnectorFailure as exc:
        if exc.code == "cursor_expired":
            return False
        raise
    return _same_epoch(page, epoch)


async def _snapshot(source_id: UUID, token: UUID, status: dict) -> None:
    epoch = str(status.get("epoch") or "")
    fresh_journal = int(status.get("journalMax") or 0)
    if not epoch:
        await _fail(source_id, token, "contract")
        return
    state = await _read_state(source_id)
    if state is None:
        return
    active = await _active_generation(source_id)
    stored_watermark = state["snapshot_journal_max"]
    resume = (
        state["snapshot_epoch"] == epoch
        and state["snapshot_generation"] is not None
        and stored_watermark is not None
    )
    if resume:
        cursor = state["snapshot_cursor"] or ""
        generation_now = int(state["snapshot_generation"])
        journal_max = int(stored_watermark)
    else:
        generation = active + 1
        journal_max = fresh_journal

        async def reset(session: AsyncSession, locked) -> None:
            await session.execute(
                delete(call_recordings).where(
                    call_recordings.c.source_id == source_id,
                    call_recordings.c.catalog_generation == generation,
                )
            )
            await session.execute(
                update(call_recording_sync_state)
                .where(call_recording_sync_state.c.source_id == locked["source_id"])
                .values(
                    snapshot_epoch=epoch,
                    snapshot_generation=generation,
                    snapshot_cursor="",
                    snapshot_journal_max=journal_max,
                    phase="updating",
                )
            )

        if not await _write(source_id, token, reset):
            return
        cursor = ""
        generation_now = generation
    while not _stop.is_set():
        page = await client.get_snapshot(cursor, settings().calls_sync_batch)
        if page.get("epoch") != epoch:
            await _write(source_id, token, _arm_snapshot)
            return
        if page["complete"] and not await _journal_covers(journal_max, epoch):
            await _write(source_id, token, _arm_snapshot)
            return

        async def apply(
            session: AsyncSession,
            locked,
            page=page,
            generation_now=generation_now,
        ) -> None:
            await apply_recording_batch(session, source_id, generation_now, page["recordings"])
            values = {
                "snapshot_cursor": page["nextCursor"] or "",
                "lease_until": utcnow() + timedelta(seconds=settings().calls_sync_lease_seconds),
                "phase": "updating",
            }
            if page["complete"]:
                values.update(
                    {
                        "phase": _connector_phase(status),
                        "published_epoch": epoch,
                        "applied_sequence": journal_max,
                        "snapshot_epoch": None,
                        "snapshot_generation": None,
                        "snapshot_cursor": "",
                        "snapshot_journal_max": None,
                        "last_synchronized_at": utcnow(),
                        "error_code": None,
                        "error_count": 0,
                    }
                )
                await session.execute(
                    update(call_recording_sources)
                    .where(call_recording_sources.c.id == source_id)
                    .values(catalog_generation=generation_now, enabled=True)
                )
                await session.execute(
                    delete(call_recordings).where(
                        call_recordings.c.source_id == source_id,
                        call_recordings.c.catalog_generation != generation_now,
                    )
                )
            await session.execute(
                update(call_recording_sync_state)
                .where(call_recording_sync_state.c.source_id == locked["source_id"])
                .values(**values)
            )

        if not await _write(source_id, token, apply):
            return
        if page["complete"]:
            return
        cursor = page["nextCursor"] or ""


async def _active_generation(source_id: UUID) -> int:
    async with session_factory()() as session:
        value = await session.scalar(
            select(call_recording_sources.c.catalog_generation).where(
                call_recording_sources.c.id == source_id
            )
        )
        return int(value or 0)
