"""Proxy one recording without holding a catalog transaction during the transfer.

``get_session`` stays open until the response finishes, so these routes open a
short session of their own and do not use that dependency. Playback does not
call ``record_activity``. Authorization is checked again at
``calls_auth_recheck_seconds`` (15 by default), which is the maximum revocation
delay for a transfer already in progress. A cancelled transfer is not retried.
"""

import asyncio
import contextlib
import sys
import time
from collections.abc import AsyncGenerator
from types import FrameType
from urllib.parse import quote
from uuid import UUID

import httpx
from sqlalchemy import select, text

from app.calls.client import ConnectorFailure, open_content
from app.config import settings
from app.db.calls import call_recording_sources, call_recordings
from app.db.session import session_factory
from app.errors import ApiError
from app.services import auth

catalog_sessions = 0
_gate_lock = asyncio.Lock()
_used = 0
_users: dict[UUID, int] = {}


async def acquire_slot(user_id: UUID) -> None:
    global _used
    current = settings()
    async with _gate_lock:
        owned = _users.get(user_id, 0)
        if _used >= current.calls_stream_slots or owned >= current.calls_stream_per_user:
            raise ApiError(
                429,
                "CALLS_BUSY",
                "Too many recordings are open. Try again in a moment.",
            )
        _used += 1
        _users[user_id] = _users.get(user_id, 0) + 1


async def release_slot(user_id: UUID) -> None:
    global _used
    async with _gate_lock:
        _used = max(0, _used - 1)
        left = _users.get(user_id, 0) - 1
        if left <= 0:
            _users.pop(user_id, None)
        else:
            _users[user_id] = left


async def open_slots() -> int:
    async with _gate_lock:
        return _used


async def load_for_stream(recording_id: UUID) -> dict:
    global catalog_sessions
    catalog_sessions += 1
    try:
        async with session_factory()() as session:
            row = (
                await session.execute(
                    select(
                        call_recordings.c.id,
                        call_recordings.c.connector_id,
                        call_recordings.c.file_version,
                        call_recordings.c.filename,
                        call_recordings.c.availability,
                    )
                    .join(
                        call_recording_sources,
                        call_recording_sources.c.id == call_recordings.c.source_id,
                    )
                    .where(
                        call_recordings.c.id == recording_id,
                        call_recordings.c.catalog_generation
                        == call_recording_sources.c.catalog_generation,
                        text("call_recordings.availability = 'ready'"),
                        call_recording_sources.c.enabled.is_(True),
                    )
                )
            ).mappings().first()
            await session.rollback()
    finally:
        catalog_sessions -= 1
    if row is None or not row["file_version"]:
        raise ApiError(404, "CALLS_MISSING", "This recording is no longer available")
    return dict(row)


async def still_allowed(raw_session: str | None) -> bool:
    global catalog_sessions
    catalog_sessions += 1
    try:
        async with session_factory()() as session:
            try:
                actor = await auth.resolve(session, raw_session)
                from app.calls.policy import require_calls

                require_calls(actor)
            except ApiError:
                await session.rollback()
                return False
            await session.rollback()
            return True
    finally:
        catalog_sessions -= 1


def content_disposition(kind: str, filename: str) -> str:
    cleaned = "".join(
        character if 32 < ord(character) < 127 and character not in {'"', "\\"} else "_"
        for character in filename
    )
    if not cleaned or cleaned in {".", ".."}:
        cleaned = "recording.wav"
    return f"{kind}; filename=\"{cleaned}\"; filename*=UTF-8''{quote(filename, safe='')}"


def upstream_headers(request_range: str | None, if_range: str | None) -> dict[str, str]:
    headers = {}
    if request_range:
        if "," in request_range:
            raise ApiError(416, "CALLS_RANGE", "Choose one part of the recording")
        headers["Range"] = request_range
    if if_range:
        headers["If-Range"] = if_range
    return headers


def response_headers(
    upstream: httpx.Response, filename: str, *, attachment: bool
) -> dict[str, str]:
    headers = {
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "Accept-Ranges": upstream.headers.get("Accept-Ranges", "bytes"),
        "Content-Type": "audio/wav",
        "Content-Disposition": content_disposition(
            "attachment" if attachment else "inline", filename
        ),
    }
    for name in ("Content-Length", "Content-Range", "ETag"):
        value = upstream.headers.get(name)
        if value:
            headers[name] = value
    return headers


_END = object()


def _pulling_streaming_response() -> bool:
    """True when this pull is Starlette iterating the body on the current task.

    ``stream_response`` is on the live call stack for a direct response task,
    an older AnyIO sender task, and a root request that reaches the body
    through the application and middleware. A direct ``anext`` caller does not
    have that frame and is not given a response owner.
    """
    frame: FrameType | None = sys._getframe()
    while frame is not None:
        code = frame.f_code
        if code.co_name == "stream_response" and code.co_filename.replace("\\", "/").endswith(
            "starlette/responses.py"
        ):
            return True
        frame = frame.f_back
    return False


def _response_send_blocked(task: asyncio.Task) -> bool:
    """True when ``task`` is this response and is waiting on downstream ASGI send.

    Starlette pulls the next chunk with ``async_generator_asend``. Any other
    await inside ``stream_response`` is the body send, including a middleware
    wrapper around the server's ``send``. A caller that already received a
    chunk and continued is not inside ``stream_response`` and is left alone.
    """
    if task.done():
        return False
    try:
        current = task.get_coro()
    except RuntimeError:
        return False
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        frame = getattr(current, "cr_frame", None)
        if frame is not None and frame.f_code.co_name == "stream_response":
            awaiting = getattr(current, "cr_await", None)
            return getattr(awaiting, "cr_code", None) is not None
        current = getattr(current, "cr_await", None)
    return False


class _OwnedByteStream:
    """Keep one stream's cleanup on a task that can still await after send is cancelled.

    Starlette does not close the body iterator when the response task is
    cancelled inside ``send``. The owner follows the task that is inside
    ``stream_response``, including a root request wrapped by middleware. If
    that task ends while the body is suspended, the owner closes it.
    """

    def __init__(self, body: AsyncGenerator[bytes]):
        self._body = body
        self._driver: asyncio.Task | None = None
        self._supervisor: asyncio.Task | None = None
        self._closed = False

    def __aiter__(self) -> _OwnedByteStream:
        return self

    async def __anext__(self) -> bytes:
        if self._driver is None and _pulling_streaming_response():
            current = asyncio.current_task()
            if current is not None:
                self._driver = current
                self._supervisor = asyncio.create_task(self._supervise())
        return await self._body.__anext__()

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._body.aclose()
        supervisor = self._supervisor
        if (
            supervisor is not None
            and supervisor is not asyncio.current_task()
            and not supervisor.done()
        ):
            supervisor.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await supervisor

    async def _supervise(self) -> None:
        driver = self._driver
        if driver is None:
            return
        try:
            await asyncio.wait({driver})
        except asyncio.CancelledError:
            return
        await self.aclose()


def byte_stream(
    upstream: httpx.Response,
    client: httpx.AsyncClient,
    user_id: UUID,
    raw_session: str | None,
) -> _OwnedByteStream:
    """Yield audio and recheck authorization on a clock, including a stalled read.

    The first chunk is delivered before a revocation check so a transfer that
    already passed the post-open check is not dropped before its first byte.
    Later chunks are withheld when the session, account, or role is no longer
    allowed, even if the source has not produced another byte. A downstream
    send that does not return is cancelled with this stream. If that
    cancellation abandons the body, the stream owner still closes it. Bytes
    already accepted by the client stay delivered.
    """
    return _OwnedByteStream(_byte_chunks(upstream, client, user_id, raw_session))


async def _byte_chunks(
    upstream: httpx.Response,
    client: httpx.AsyncClient,
    user_id: UUID,
    raw_session: str | None,
) -> AsyncGenerator[bytes]:
    stop = asyncio.Event()
    finish_lock = asyncio.Lock()
    cleanup: asyncio.Task | None = None
    consumer: asyncio.Task | None = None

    async def _close_and_release() -> None:
        with contextlib.suppress(Exception):
            await upstream.aclose()
        with contextlib.suppress(Exception):
            await client.aclose()
        await release_slot(user_id)

    async def finish() -> None:
        nonlocal cleanup
        async with finish_lock:
            if cleanup is None:
                stop.set()
                cleanup = asyncio.create_task(_close_and_release())
        await asyncio.shield(cleanup)

    interval = settings().calls_auth_recheck_seconds

    async def watch() -> None:
        """Recheck authorization for the whole response, including a blocked send.

        Already delivered bytes stay in the client buffer. Revocation closes
        the upstream response, releases the slot, and cancels the response
        task that is still inside this stream's ASGI send. It does not recall
        delivered bytes or cancel a caller that has already moved on.
        """
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except TimeoutError:
                pass
            if stop.is_set():
                return
            if not await still_allowed(raw_session):
                await finish()
                blocked = consumer
                if blocked is not None and _response_send_blocked(blocked):
                    blocked.cancel()
                return

    watcher = asyncio.create_task(watch())
    last_check = time.monotonic()
    iterator = upstream.aiter_bytes(settings().calls_stream_chunk_bytes).__aiter__()
    pending: asyncio.Task | None = None

    async def take():
        try:
            return await iterator.__anext__()
        except StopAsyncIteration:
            return _END

    try:
        while True:
            pending = asyncio.create_task(take())
            try:
                while not pending.done():
                    if time.monotonic() - last_check >= interval:
                        if not await still_allowed(raw_session):
                            pending.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await pending
                            raise RuntimeError("recording stream stopped")
                        last_check = time.monotonic()
                    remaining = interval - (time.monotonic() - last_check)
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(pending), max(0.01, remaining)
                        )
                    except TimeoutError:
                        continue
                chunk = pending.result()
            except asyncio.CancelledError:
                pending.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await pending
                raise
            if chunk is _END:
                return
            if time.monotonic() - last_check >= interval:
                if not await still_allowed(raw_session):
                    raise RuntimeError("recording stream stopped")
                last_check = time.monotonic()
            consumer = asyncio.current_task()
            try:
                yield chunk
            finally:
                consumer = None
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pending
        await finish()
        watcher.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watcher


def map_upstream_status(status: int) -> ApiError | None:
    if status in {200, 206, 416}:
        return None
    if status == 409:
        return ApiError(409, "CALLS_VERSION_CHANGED", "This recording changed. Search again.")
    if status == 404:
        return ApiError(404, "CALLS_MISSING", "This recording is no longer available")
    return ApiError(503, "CALLS_SOURCE_UNAVAILABLE", "The recording source is offline")


async def open_upstream(row: dict, headers: dict[str, str], method: str = "GET"):
    try:
        client, upstream = await open_content(
            row["connector_id"], row["file_version"], headers, method=method
        )
    except ConnectorFailure as exc:
        raise ApiError(503, "CALLS_SOURCE_UNAVAILABLE", "The recording source is offline") from exc
    failure = map_upstream_status(upstream.status_code)
    if failure is not None:
        await upstream.aclose()
        await client.aclose()
        raise failure
    return client, upstream
