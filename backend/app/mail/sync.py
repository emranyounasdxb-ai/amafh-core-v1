"""Durable mailbox synchronization.

Remote mail stays authoritative. This module stores a bounded, account-scoped
copy so folder and message reads do not open IMAP once a folder is synchronized.
Jobs are leased rows, not an unbounded set of tasks. IMAP IDLE is not used.
One worker polls due jobs. Provider folder names, IDLE, and APPENDUID behavior
on the configured host are unverified when only the local simulator has run.

Database transactions are not held across provider calls. Publication and folder
error writes lock the connection row and then the job row, and they commit
only while that claim still owns the job and the generation, address, and
connected status still match. An expired or replaced claim cannot publish,
cancel, or finish the job. Header and body caps stay at the configured limits.
The body cap is the UTF-8 size of the stored markup; the omission note is
extra and is not counted. Opened bodies are kept ahead of never-opened mail,
and terminal job rows are pruned to a small history. A disconnected or
replaced mailbox cannot be refilled by an older snapshot.
"""

import asyncio
import json
import logging
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.base import utcnow
from app.db.mailbox import (
    mailbox_connections,
    mailbox_hidden_messages,
    mailbox_sync_folders,
    mailbox_sync_jobs,
    mailbox_sync_messages,
)
from app.db.session import session_factory
from app.mail.crypto import MailboxKeyError, open_secret, seal
from app.mail.errors import MailFailure
from app.mail.folders import ROLES
from app.mail.gateway import (
    FolderSnapshot,
    MessageContent,
    SyncHeader,
    bound_cached_html,
)
from app.mail.runtime import get_gateway, run_sync, shutdown_mail_runtime

logger = logging.getLogger(__name__)

_task: asyncio.Task[None] | None = None
_stop: asyncio.Event | None = None
_OFFLINE = {"unavailable", "timeout", "tls"}
# Completed, failed, and cancelled rows kept per account. This is not a retention increase.
_TERMINAL_HISTORY = 8


class CachedBody:
    def __init__(self, *, stale: bool = False, message: dict | None = None) -> None:
        self.stale = stale
        self.message = message


async def start_worker() -> None:
    global _task, _stop
    if _task is not None and not _task.done():
        return
    _stop = asyncio.Event()
    _task = asyncio.create_task(_loop())


async def stop_worker() -> None:
    global _task
    if _stop is not None:
        _stop.set()
    task = _task
    _task = None
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    shutdown_mail_runtime()


async def _loop() -> None:
    assert _stop is not None
    while not _stop.is_set():
        worked = False
        try:
            worked = await run_once()
        except Exception:
            logger.warning("mailbox sync step failed")
        if worked or _stop is None:
            continue
        try:
            await asyncio.wait_for(_stop.wait(), timeout=2)
        except TimeoutError:
            pass


async def schedule_sync(account_id: UUID, email: str, generation: int, priority: str) -> None:
    if priority not in ROLES:
        priority = "inbox"
    async with session_factory()() as db:
        existing = (
            await db.execute(
                select(mailbox_sync_jobs.c.id, mailbox_sync_jobs.c.status).where(
                    mailbox_sync_jobs.c.account_id == account_id,
                    mailbox_sync_jobs.c.generation == generation,
                    mailbox_sync_jobs.c.kind == "sync",
                    mailbox_sync_jobs.c.status.in_(("pending", "leased")),
                )
            )
        ).first()
        now = utcnow()
        if existing is not None:
            if existing.status == "pending":
                await db.execute(
                    update(mailbox_sync_jobs)
                    .where(mailbox_sync_jobs.c.id == existing.id)
                    .values(priority_role=priority, updated_at=now)
                )
            await db.commit()
            return
        await db.execute(
            mailbox_sync_jobs.insert().values(
                id=uuid4(),
                account_id=account_id,
                login_email=email,
                generation=generation,
                kind="sync",
                folder_role="",
                uid=0,
                uid_validity=0,
                priority_role=priority,
                status="pending",
                attempts=0,
                next_run_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()


async def schedule_seen(
    account_id: UUID,
    email: str,
    generation: int,
    role: str,
    uid: int,
    validity: int,
) -> None:
    now = utcnow()
    async with session_factory()() as db:
        await db.execute(
            update(mailbox_sync_messages)
            .where(
                mailbox_sync_messages.c.account_id == account_id,
                mailbox_sync_messages.c.generation == generation,
                mailbox_sync_messages.c.folder_role == role,
                mailbox_sync_messages.c.uid_validity == validity,
                mailbox_sync_messages.c.uid == uid,
            )
            .values(unread=False, updated_at=now)
        )
        await db.execute(
            mailbox_sync_jobs.insert().values(
                id=uuid4(),
                account_id=account_id,
                login_email=email,
                generation=generation,
                kind="seen",
                folder_role=role,
                uid=uid,
                uid_validity=validity,
                priority_role=role,
                status="pending",
                attempts=0,
                next_run_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()


async def purge_account(session: AsyncSession, account_id: UUID) -> None:
    now = utcnow()
    await session.execute(
        update(mailbox_sync_jobs)
        .where(
            mailbox_sync_jobs.c.account_id == account_id,
            mailbox_sync_jobs.c.status.in_(("pending", "leased")),
        )
        .values(status="cancelled", updated_at=now)
    )
    await session.execute(
        delete(mailbox_sync_messages).where(mailbox_sync_messages.c.account_id == account_id)
    )
    await session.execute(
        delete(mailbox_sync_folders).where(mailbox_sync_folders.c.account_id == account_id)
    )


async def cached_page(
    session: AsyncSession,
    account_id: UUID,
    email: str,
    generation: int,
    role: str,
    *,
    page: int,
    page_size: int,
    query: str,
) -> dict | None:
    folder = (
        (
            await session.execute(
                select(mailbox_sync_folders).where(
                    mailbox_sync_folders.c.account_id == account_id,
                    mailbox_sync_folders.c.login_email == email,
                    mailbox_sync_folders.c.generation == generation,
                    mailbox_sync_folders.c.folder_role == role,
                )
            )
        )
        .mappings()
        .first()
    )
    if folder is None:
        return None
    if folder["status"] == "missing":
        return {"syncState": "missing"}
    active = await _sync_active(session, account_id, generation)
    state = _state(folder["status"], folder["error_code"], active)
    filters = [
        mailbox_sync_messages.c.account_id == account_id,
        mailbox_sync_messages.c.login_email == email,
        mailbox_sync_messages.c.generation == generation,
        mailbox_sync_messages.c.folder_role == role,
        mailbox_sync_messages.c.uid_validity == folder["uid_validity"],
        ~exists(
            select(mailbox_hidden_messages.c.id).where(
                mailbox_hidden_messages.c.account_id == account_id,
                mailbox_hidden_messages.c.login_email == email,
                mailbox_hidden_messages.c.folder_role == role,
                mailbox_hidden_messages.c.uid_validity == mailbox_sync_messages.c.uid_validity,
                mailbox_hidden_messages.c.uid == mailbox_sync_messages.c.uid,
            )
        ),
    ]
    needle = query.strip()
    if needle:
        pattern = _like(needle)
        filters.append(
            or_(
                mailbox_sync_messages.c.subject.ilike(pattern, escape="\\"),
                mailbox_sync_messages.c.sender.ilike(pattern, escape="\\"),
                mailbox_sync_messages.c.recipients.ilike(pattern, escape="\\"),
                mailbox_sync_messages.c.preview.ilike(pattern, escape="\\"),
            )
        )
    total = int(
        await session.scalar(
            select(func.count()).select_from(mailbox_sync_messages).where(*filters)
        )
        or 0
    )
    rows = (
        (
            await session.execute(
                select(mailbox_sync_messages)
                .where(*filters)
                .order_by(
                    mailbox_sync_messages.c.message_date.desc().nulls_last(),
                    mailbox_sync_messages.c.uid.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    synced = folder["synced_at"].isoformat() if folder["synced_at"] else None
    return {
        "items": [_row_summary(row) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "folder": role,
        "appOnlyDeleted": False,
        "syncState": state,
        "syncedAt": synced,
    }


async def cached_message(
    session: AsyncSession,
    account_id: UUID,
    email: str,
    generation: int,
    role: str,
    validity: int,
    uid: int,
) -> CachedBody | None:
    folder = (
        (
            await session.execute(
                select(
                    mailbox_sync_folders.c.uid_validity,
                    mailbox_sync_folders.c.status,
                ).where(
                    mailbox_sync_folders.c.account_id == account_id,
                    mailbox_sync_folders.c.login_email == email,
                    mailbox_sync_folders.c.generation == generation,
                    mailbox_sync_folders.c.folder_role == role,
                )
            )
        )
        .mappings()
        .first()
    )
    if folder is None:
        return None
    if int(folder["uid_validity"]) != validity:
        return CachedBody(stale=True)
    row = (
        (
            await session.execute(
                select(mailbox_sync_messages).where(
                    mailbox_sync_messages.c.account_id == account_id,
                    mailbox_sync_messages.c.login_email == email,
                    mailbox_sync_messages.c.generation == generation,
                    mailbox_sync_messages.c.folder_role == role,
                    mailbox_sync_messages.c.uid_validity == validity,
                    mailbox_sync_messages.c.uid == uid,
                )
            )
        )
        .mappings()
        .first()
    )
    if row is None or not row["body_sealed"]:
        return None
    try:
        html = open_secret(row["body_sealed"])
    except MailboxKeyError:
        return None
    attachments = []
    if row["attachments_json"]:
        try:
            parsed = json.loads(row["attachments_json"])
        except json.JSONDecodeError:
            parsed = []
        if isinstance(parsed, list):
            attachments = [
                item
                for item in parsed
                if isinstance(item, dict) and isinstance(item.get("index"), int)
            ]
    return CachedBody(
        message={
            "subject": row["subject"] or "(no subject)",
            "sender": row["sender"],
            "recipients": row["recipients"],
            "preview": row["preview"],
            "date": row["message_date"].isoformat() if row["message_date"] else None,
            "unread": bool(row["unread"]),
            "hasAttachment": bool(row["has_attachment"]),
            "html": html,
            "cc": row["cc"],
            "bcc": row["bcc"],
            "attachments": attachments,
            "messageId": row["message_id"],
            "replyTo": row["reply_to"],
            "references": row["references_header"],
            "appOnlyDeleted": False,
        }
    )


async def cached_summary(
    session: AsyncSession, account_id: UUID, email: str, generation: int
) -> dict[str, int] | None:
    rows = (
        await session.execute(
            select(mailbox_sync_folders.c.folder_role, mailbox_sync_folders.c.status).where(
                mailbox_sync_folders.c.account_id == account_id,
                mailbox_sync_folders.c.login_email == email,
                mailbox_sync_folders.c.generation == generation,
            )
        )
    ).all()
    found = {row.folder_role: row.status for row in rows}
    if any(role not in found for role in ROLES):
        return None
    if any(found[role] not in {"ready", "missing", "failed"} for role in ROLES):
        return None
    counts = (
        await session.execute(
            select(mailbox_sync_messages.c.folder_role, func.count())
            .where(
                mailbox_sync_messages.c.account_id == account_id,
                mailbox_sync_messages.c.login_email == email,
                mailbox_sync_messages.c.generation == generation,
                mailbox_sync_messages.c.unread.is_(True),
                ~exists(
                    select(mailbox_hidden_messages.c.id).where(
                        mailbox_hidden_messages.c.account_id == account_id,
                        mailbox_hidden_messages.c.login_email == email,
                        mailbox_hidden_messages.c.folder_role
                        == mailbox_sync_messages.c.folder_role,
                        mailbox_hidden_messages.c.uid_validity
                        == mailbox_sync_messages.c.uid_validity,
                        mailbox_hidden_messages.c.uid == mailbox_sync_messages.c.uid,
                    )
                ),
            )
            .group_by(mailbox_sync_messages.c.folder_role)
        )
    ).all()
    unread = {role: 0 for role in ROLES}
    for role, count in counts:
        unread[role] = int(count)
    return unread


async def remember_opened(
    account_id: UUID,
    email: str,
    generation: int,
    role: str,
    validity: int,
    uid: int,
    content: MessageContent,
) -> None:
    """Store one successful cold read so the next open does not fetch it again."""
    now = utcnow()
    html = bound_cached_html(content.html or "", settings().mail_sync_body_bytes)
    try:
        sealed = seal(html)
    except MailboxKeyError:
        return
    summary = content.summary
    encoded = json.dumps(
        [
            {
                "index": part.index,
                "filename": part.filename,
                "contentType": part.content_type,
                "size": part.size,
            }
            for part in content.attachments
        ]
    )
    if len(encoded) > 8000:
        encoded = "[]"
    values = {
        "subject": (summary.subject or "")[:998],
        "sender": (summary.sender or "")[:998],
        "recipients": (summary.recipients or "")[:998],
        "preview": (summary.preview or "")[:180],
        "message_date": summary.message_date,
        "unread": summary.unread,
        "has_attachment": summary.has_attachment,
        "message_id": (content.message_id or "")[:998],
        "cc": (content.cc or "")[:998],
        "bcc": (content.bcc or "")[:998],
        "reply_to": (content.reply_to or summary.sender or "")[:998],
        "references_header": (content.references or "")[:998],
        "body_sealed": sealed,
        "attachments_json": encoded,
        "accessed_at": now,
        "updated_at": now,
    }
    async with session_factory()() as db:
        if not await _connection_current(db, account_id, email, generation):
            await db.rollback()
            return
        scope = (
            mailbox_sync_messages.c.account_id == account_id,
            mailbox_sync_messages.c.login_email == email,
            mailbox_sync_messages.c.generation == generation,
            mailbox_sync_messages.c.folder_role == role,
            mailbox_sync_messages.c.uid_validity == validity,
            mailbox_sync_messages.c.uid == uid,
        )
        updated = await db.execute(
            update(mailbox_sync_messages)
            .where(*scope)
            .values(**values)
            .returning(mailbox_sync_messages.c.id)
        )
        if updated.first() is None:
            await db.execute(
                pg_insert(mailbox_sync_messages).values(
                    id=uuid4(),
                    account_id=account_id,
                    login_email=email,
                    generation=generation,
                    folder_role=role,
                    uid_validity=validity,
                    uid=uid,
                    created_at=now,
                    **values,
                )
            )
        await _evict(db, {"account_id": account_id, "generation": generation}, validity, role)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()


async def touch_opened(
    account_id: UUID,
    email: str,
    generation: int,
    role: str,
    validity: int,
    uid: int,
) -> None:
    now = utcnow()
    async with session_factory()() as db:
        if not await _connection_current(db, account_id, email, generation):
            await db.rollback()
            return
        await db.execute(
            update(mailbox_sync_messages)
            .where(
                mailbox_sync_messages.c.account_id == account_id,
                mailbox_sync_messages.c.login_email == email,
                mailbox_sync_messages.c.generation == generation,
                mailbox_sync_messages.c.folder_role == role,
                mailbox_sync_messages.c.uid_validity == validity,
                mailbox_sync_messages.c.uid == uid,
                mailbox_sync_messages.c.body_sealed.is_not(None),
            )
            .values(accessed_at=now, updated_at=now)
        )
        await db.commit()


async def _connection_current(
    db: AsyncSession, account_id: UUID, email: str, generation: int
) -> bool:
    connection = (
        (
            await db.execute(
                select(mailbox_connections)
                .where(mailbox_connections.c.account_id == account_id)
                .with_for_update()
            )
        )
        .mappings()
        .first()
    )
    return bool(
        connection
        and connection["status"] == "connected"
        and connection["login_email"] == email
        and int(connection["generation"]) == generation
    )


async def run_once() -> bool:
    job = await _claim()
    if job is None:
        return False
    try:
        if job["kind"] == "seen":
            await _run_seen(job)
        else:
            await _run_sync(job)
    except MailFailure as exc:
        await _retry(job, exc.code)
    except TimeoutError:
        await _retry(job, "timeout")
    except Exception:
        logger.warning("mailbox sync job failed")
        await _retry(job, "unavailable")
    return True


async def _claim() -> dict | None:
    now = utcnow()
    lease = now + timedelta(seconds=settings().mail_sync_lease_seconds)
    async with session_factory()() as db:
        row = (
            (
                await db.execute(
                    select(mailbox_sync_jobs)
                    .where(
                        or_(
                            and_(
                                mailbox_sync_jobs.c.status == "pending",
                                mailbox_sync_jobs.c.next_run_at <= now,
                            ),
                            and_(
                                mailbox_sync_jobs.c.status == "leased",
                                mailbox_sync_jobs.c.lease_until < now,
                            ),
                        )
                    )
                    .order_by(mailbox_sync_jobs.c.next_run_at, mailbox_sync_jobs.c.created_at)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            await db.rollback()
            return None
        attempts = int(row["attempts"]) + 1
        token = uuid4()
        await db.execute(
            update(mailbox_sync_jobs)
            .where(mailbox_sync_jobs.c.id == row["id"])
            .values(
                status="leased",
                attempts=attempts,
                lease_until=lease,
                claim_token=token,
                updated_at=now,
            )
        )
        await db.commit()
        claimed = dict(row)
        claimed["attempts"] = attempts
        claimed["status"] = "leased"
        claimed["claim_token"] = token
        claimed["lease_until"] = lease
        return claimed


async def _run_sync(job: dict) -> None:
    creds = await _credentials(job)
    if creds is None:
        await _cancel(job)
        return
    email, password = creds
    priority = job["priority_role"] if job["priority_role"] in ROLES else "inbox"
    roles = [priority, *[role for role in ROLES if role != priority]]
    gateway = get_gateway()
    for role in roles:
        if not await _renew(job):
            return
        if not await _job_current(job):
            await _cancel(job)
            return
        known, bodies, validity = await _known(job, role)
        current = settings()
        try:
            snapshot = await run_sync(
                gateway.snapshot_folder,
                email,
                password,
                role,
                known_uids=known,
                known_body_uids=bodies,
                header_limit=current.mail_sync_headers,
                body_limit=current.mail_sync_bodies,
                body_bytes=current.mail_sync_body_bytes,
                previous_validity=validity,
            )
        except MailFailure as exc:
            await _mark_folder_problem(job, role, exc.code)
            raise
        if not await _renew(job):
            return
        if not await _job_current(job):
            await _cancel(job)
            return
        if not await _apply(job, role, snapshot):
            await _cancel(job)
            return
    await _complete(job)


async def _run_seen(job: dict) -> None:
    if not await _renew(job):
        return
    if not await _job_current(job):
        await _cancel(job)
        return
    creds = await _credentials(job)
    if creds is None:
        await _cancel(job)
        return
    email, password = creds
    async with session_factory()() as db:
        folder = (
            (
                await db.execute(
                    select(
                        mailbox_sync_folders.c.folder_name,
                        mailbox_sync_folders.c.uid_validity,
                    ).where(
                        mailbox_sync_folders.c.account_id == job["account_id"],
                        mailbox_sync_folders.c.generation == job["generation"],
                        mailbox_sync_folders.c.folder_role == job["folder_role"],
                    )
                )
            )
            .mappings()
            .first()
        )
        await db.rollback()
    if folder is None or int(folder["uid_validity"]) != int(job["uid_validity"]):
        await _cancel(job)
        return
    if not await _job_current(job):
        await _cancel(job)
        return
    try:
        await run_sync(
            get_gateway().store_seen,
            email,
            password,
            folder["folder_name"],
            int(job["uid"]),
            int(job["uid_validity"]),
        )
    except MailFailure as exc:
        if exc.code == "missing":
            await _cancel(job)
            return
        raise
    await _complete(job)


async def _credentials(job: dict) -> tuple[str, str] | None:
    async with session_factory()() as db:
        row = (
            (
                await db.execute(
                    select(mailbox_connections).where(
                        mailbox_connections.c.account_id == job["account_id"]
                    )
                )
            )
            .mappings()
            .first()
        )
        await db.rollback()
    if row is None or row["status"] != "connected" or not row["secret"]:
        return None
    if int(row["generation"]) != int(job["generation"]) or row["login_email"] != job["login_email"]:
        return None
    try:
        return row["login_email"], open_secret(row["secret"])
    except MailboxKeyError:
        return None


async def _known(job: dict, role: str) -> tuple[set[int], set[int], int | None]:
    async with session_factory()() as db:
        folder = (
            (
                await db.execute(
                    select(
                        mailbox_sync_folders.c.uid_validity, mailbox_sync_folders.c.status
                    ).where(
                        mailbox_sync_folders.c.account_id == job["account_id"],
                        mailbox_sync_folders.c.generation == job["generation"],
                        mailbox_sync_folders.c.folder_role == role,
                    )
                )
            )
            .mappings()
            .first()
        )
        if folder is None or folder["status"] != "ready":
            await db.rollback()
            return set(), set(), None
        validity = int(folder["uid_validity"])
        rows = (
            await db.execute(
                select(mailbox_sync_messages.c.uid, mailbox_sync_messages.c.body_sealed).where(
                    mailbox_sync_messages.c.account_id == job["account_id"],
                    mailbox_sync_messages.c.generation == job["generation"],
                    mailbox_sync_messages.c.folder_role == role,
                    mailbox_sync_messages.c.uid_validity == validity,
                )
            )
        ).all()
        await db.rollback()
    known = {int(row.uid) for row in rows}
    bodies = {int(row.uid) for row in rows if row.body_sealed}
    return known, bodies, validity


async def _publication_owner(db: AsyncSession, job: dict) -> bool:
    """Lock the connection, then this job, and accept only the current claim.

    The caller keeps both locks until it commits or rolls back. Invalidation
    updates the connection before it changes jobs, so a generation or address
    change cannot land between this check and the folder write. Provider I/O
    stays outside this transaction.
    """
    connection = (
        (
            await db.execute(
                select(mailbox_connections)
                .where(mailbox_connections.c.account_id == job["account_id"])
                .with_for_update()
            )
        )
        .mappings()
        .first()
    )
    current = (
        await db.execute(
            select(
                mailbox_sync_jobs.c.status,
                mailbox_sync_jobs.c.generation,
                mailbox_sync_jobs.c.claim_token,
            )
            .where(mailbox_sync_jobs.c.id == job["id"])
            .with_for_update()
        )
    ).first()
    return bool(
        connection
        and connection["status"] == "connected"
        and connection["login_email"] == job["login_email"]
        and int(connection["generation"]) == int(job["generation"])
        and current is not None
        and current.status == "leased"
        and current.claim_token == job.get("claim_token")
        and int(current.generation) == int(job["generation"])
    )


async def _apply(job: dict, role: str, snapshot: FolderSnapshot | None) -> bool:
    now = utcnow()
    async with session_factory()() as db:
        if not await _publication_owner(db, job):
            await db.rollback()
            return False
        if snapshot is None:
            await _upsert_folder(
                db,
                job,
                role,
                name="",
                validity=0,
                status="missing",
                total=0,
                error=None,
                when=now,
            )
            await db.execute(
                delete(mailbox_sync_messages).where(
                    mailbox_sync_messages.c.account_id == job["account_id"],
                    mailbox_sync_messages.c.generation == job["generation"],
                    mailbox_sync_messages.c.folder_role == role,
                )
            )
            await db.commit()
            return True
        await db.execute(
            delete(mailbox_sync_messages).where(
                mailbox_sync_messages.c.account_id == job["account_id"],
                mailbox_sync_messages.c.generation == job["generation"],
                mailbox_sync_messages.c.folder_role == role,
                mailbox_sync_messages.c.uid_validity != snapshot.uid_validity,
            )
        )
        remote = set(snapshot.remote_uids)
        if remote:
            await db.execute(
                delete(mailbox_sync_messages).where(
                    mailbox_sync_messages.c.account_id == job["account_id"],
                    mailbox_sync_messages.c.generation == job["generation"],
                    mailbox_sync_messages.c.folder_role == role,
                    mailbox_sync_messages.c.uid_validity == snapshot.uid_validity,
                    mailbox_sync_messages.c.uid.not_in(remote),
                )
            )
        else:
            await db.execute(
                delete(mailbox_sync_messages).where(
                    mailbox_sync_messages.c.account_id == job["account_id"],
                    mailbox_sync_messages.c.generation == job["generation"],
                    mailbox_sync_messages.c.folder_role == role,
                    mailbox_sync_messages.c.uid_validity == snapshot.uid_validity,
                )
            )
        await _upsert_headers(db, job, snapshot, now)
        await _store_bodies(db, job, snapshot, now)
        await _apply_flags(db, job, snapshot, now)
        await _evict(db, job, snapshot.uid_validity, role)
        await _upsert_folder(
            db,
            job,
            role,
            name=snapshot.name,
            validity=snapshot.uid_validity,
            status="ready",
            total=len(snapshot.remote_uids),
            error=None,
            when=now,
        )
        await db.commit()
    logger.info("mailbox sync stored %s headers", len(snapshot.headers))
    return True


async def _upsert_headers(db: AsyncSession, job: dict, snapshot: FolderSnapshot, now) -> None:
    if not snapshot.headers:
        return
    rows = [_header_values(job, snapshot, header, now) for header in snapshot.headers]
    for offset in range(0, len(rows), 100):
        chunk = rows[offset : offset + 100]
        stmt = pg_insert(mailbox_sync_messages).values(chunk)
        excluded = stmt.excluded
        await db.execute(
            stmt.on_conflict_do_update(
                constraint="uq_mailbox_sync_message",
                set_={
                    "login_email": excluded.login_email,
                    "subject": excluded.subject,
                    "sender": excluded.sender,
                    "recipients": excluded.recipients,
                    "preview": excluded.preview,
                    "message_date": excluded.message_date,
                    "unread": excluded.unread,
                    "has_attachment": excluded.has_attachment,
                    "message_id": excluded.message_id,
                    "cc": excluded.cc,
                    "bcc": excluded.bcc,
                    "reply_to": excluded.reply_to,
                    "references_header": excluded.references_header,
                    "updated_at": excluded.updated_at,
                },
            )
        )


def _header_values(job: dict, snapshot: FolderSnapshot, header: SyncHeader, now) -> dict:
    return {
        "id": uuid4(),
        "account_id": job["account_id"],
        "login_email": job["login_email"],
        "generation": int(job["generation"]),
        "folder_role": snapshot.role,
        "uid_validity": snapshot.uid_validity,
        "uid": header.uid,
        "subject": (header.subject or "")[:998],
        "sender": (header.sender or "")[:998],
        "recipients": (header.recipients or "")[:998],
        "preview": (header.preview or "")[:180],
        "message_date": header.message_date,
        "unread": header.unread,
        "has_attachment": header.has_attachment,
        "message_id": (header.message_id or "")[:998],
        "cc": (header.cc or "")[:998],
        "bcc": (header.bcc or "")[:998],
        "reply_to": (header.reply_to or "")[:998],
        "references_header": (header.references or "")[:998],
        "created_at": now,
        "updated_at": now,
    }


async def _store_bodies(db: AsyncSession, job: dict, snapshot: FolderSnapshot, now) -> None:
    limit = settings().mail_sync_body_bytes
    for body in snapshot.bodies:
        try:
            sealed = seal(bound_cached_html(body.html or "", limit))
        except MailboxKeyError:
            continue
        encoded = json.dumps(
            [
                {
                    "index": part.index,
                    "filename": part.filename,
                    "contentType": part.content_type,
                    "size": part.size,
                }
                for part in body.attachments
            ]
        )
        if len(encoded) > 8000:
            encoded = "[]"
        await db.execute(
            update(mailbox_sync_messages)
            .where(
                mailbox_sync_messages.c.account_id == job["account_id"],
                mailbox_sync_messages.c.generation == job["generation"],
                mailbox_sync_messages.c.folder_role == snapshot.role,
                mailbox_sync_messages.c.uid_validity == snapshot.uid_validity,
                mailbox_sync_messages.c.uid == body.uid,
            )
            .values(body_sealed=sealed, attachments_json=encoded, updated_at=now)
        )


async def _apply_flags(db: AsyncSession, job: dict, snapshot: FolderSnapshot, now) -> None:
    pending = set(
        (
            await db.execute(
                select(mailbox_sync_jobs.c.uid).where(
                    mailbox_sync_jobs.c.account_id == job["account_id"],
                    mailbox_sync_jobs.c.generation == job["generation"],
                    mailbox_sync_jobs.c.kind == "seen",
                    mailbox_sync_jobs.c.folder_role == snapshot.role,
                    mailbox_sync_jobs.c.status.in_(("pending", "leased")),
                )
            )
        ).scalars()
    )
    unread = [uid for uid, flag in snapshot.flags if flag and uid not in pending]
    read = [uid for uid, flag in snapshot.flags if not flag and uid not in pending]
    scope = [
        mailbox_sync_messages.c.account_id == job["account_id"],
        mailbox_sync_messages.c.generation == job["generation"],
        mailbox_sync_messages.c.folder_role == snapshot.role,
        mailbox_sync_messages.c.uid_validity == snapshot.uid_validity,
    ]
    if unread:
        await db.execute(
            update(mailbox_sync_messages)
            .where(*scope, mailbox_sync_messages.c.uid.in_(unread))
            .values(unread=True, updated_at=now)
        )
    if read:
        await db.execute(
            update(mailbox_sync_messages)
            .where(*scope, mailbox_sync_messages.c.uid.in_(read))
            .values(unread=False, updated_at=now)
        )


async def _evict(db: AsyncSession, job: dict, validity: int, role: str) -> None:
    current = settings()
    ranked = (
        select(mailbox_sync_messages.c.id)
        .where(
            mailbox_sync_messages.c.account_id == job["account_id"],
            mailbox_sync_messages.c.generation == job["generation"],
            mailbox_sync_messages.c.folder_role == role,
            mailbox_sync_messages.c.uid_validity == validity,
        )
        .order_by(
            mailbox_sync_messages.c.accessed_at.is_(None).asc(),
            mailbox_sync_messages.c.accessed_at.desc(),
            mailbox_sync_messages.c.message_date.desc().nulls_last(),
            mailbox_sync_messages.c.uid.desc(),
        )
        .offset(current.mail_sync_headers)
    )
    await db.execute(delete(mailbox_sync_messages).where(mailbox_sync_messages.c.id.in_(ranked)))
    keep = (
        select(mailbox_sync_messages.c.id)
        .where(
            mailbox_sync_messages.c.account_id == job["account_id"],
            mailbox_sync_messages.c.generation == job["generation"],
            mailbox_sync_messages.c.body_sealed.is_not(None),
        )
        .order_by(
            mailbox_sync_messages.c.accessed_at.is_(None).asc(),
            mailbox_sync_messages.c.accessed_at.desc(),
            mailbox_sync_messages.c.message_date.desc().nulls_last(),
            mailbox_sync_messages.c.uid.desc(),
        )
        .limit(current.mail_sync_bodies)
    )
    await db.execute(
        update(mailbox_sync_messages)
        .where(
            mailbox_sync_messages.c.account_id == job["account_id"],
            mailbox_sync_messages.c.generation == job["generation"],
            mailbox_sync_messages.c.body_sealed.is_not(None),
            mailbox_sync_messages.c.id.not_in(keep),
        )
        .values(body_sealed=None, attachments_json=None, accessed_at=None, updated_at=utcnow())
    )


async def _upsert_folder(
    db: AsyncSession,
    job: dict,
    role: str,
    *,
    name: str,
    validity: int,
    status: str,
    total: int,
    error: str | None,
    when,
) -> None:
    if status == "missing":
        validity = 0
    values = {
        "id": uuid4(),
        "account_id": job["account_id"],
        "login_email": job["login_email"],
        "generation": int(job["generation"]),
        "folder_role": role,
        "folder_name": name[:255],
        "uid_validity": validity,
        "status": status,
        "remote_total": total,
        "error_code": error,
        "synced_at": when if status == "ready" else None,
        "created_at": when,
        "updated_at": when,
    }
    stmt = pg_insert(mailbox_sync_folders).values(values)
    await db.execute(
        stmt.on_conflict_do_update(
            constraint="uq_mailbox_sync_folder",
            set_={
                "login_email": stmt.excluded.login_email,
                "folder_name": stmt.excluded.folder_name,
                "uid_validity": stmt.excluded.uid_validity,
                "status": stmt.excluded.status,
                "remote_total": stmt.excluded.remote_total,
                "error_code": stmt.excluded.error_code,
                "synced_at": stmt.excluded.synced_at,
                "updated_at": stmt.excluded.updated_at,
            },
        )
    )


def _claim_clause(job: dict):
    return (
        mailbox_sync_jobs.c.id == job["id"],
        mailbox_sync_jobs.c.status == "leased",
        mailbox_sync_jobs.c.claim_token == job.get("claim_token"),
    )


async def _renew(job: dict) -> bool:
    """Extend this claim only. An expired or replaced claim is left for the next owner."""
    now = utcnow()
    lease = now + timedelta(seconds=settings().mail_sync_lease_seconds)
    async with session_factory()() as db:
        renewed = await db.execute(
            update(mailbox_sync_jobs)
            .where(*_claim_clause(job), mailbox_sync_jobs.c.lease_until >= now)
            .values(lease_until=lease, updated_at=now)
            .returning(mailbox_sync_jobs.c.id)
        )
        owned = renewed.first() is not None
        await db.commit()
        return owned


async def _mark_folder_problem(job: dict, role: str, code: str) -> None:
    now = utcnow()
    async with session_factory()() as db:
        if not await _publication_owner(db, job):
            await db.rollback()
            return
        existing = (
            (
                await db.execute(
                    select(mailbox_sync_folders.c.status).where(
                        mailbox_sync_folders.c.account_id == job["account_id"],
                        mailbox_sync_folders.c.generation == job["generation"],
                        mailbox_sync_folders.c.folder_role == role,
                    )
                )
            )
            .scalars()
            .first()
        )
        if existing == "ready":
            await db.execute(
                update(mailbox_sync_folders)
                .where(
                    mailbox_sync_folders.c.account_id == job["account_id"],
                    mailbox_sync_folders.c.generation == job["generation"],
                    mailbox_sync_folders.c.folder_role == role,
                )
                .values(error_code=code, updated_at=now)
            )
        else:
            await _upsert_folder(
                db,
                job,
                role,
                name="",
                validity=1,
                status="failed",
                total=0,
                error=code,
                when=now,
            )
        await db.commit()


async def _retry(job: dict, code: str) -> None:
    now = utcnow()
    attempts = int(job["attempts"])
    async with session_factory()() as db:
        if attempts >= settings().mail_sync_attempts:
            await db.execute(
                update(mailbox_sync_jobs)
                .where(*_claim_clause(job))
                .values(status="failed", updated_at=now)
            )
            await _prune_history(db, job["account_id"])
        else:
            delay = min(60, 2**attempts)
            await db.execute(
                update(mailbox_sync_jobs)
                .where(*_claim_clause(job))
                .values(
                    status="pending", next_run_at=now + timedelta(seconds=delay), updated_at=now
                )
            )
        await db.commit()
    logger.info("mailbox sync deferred")
    if code:
        return


async def _complete(job: dict) -> None:
    await _set_status(job, "done")


async def _cancel(job: dict) -> None:
    await _set_status(job, "cancelled")


async def _set_status(job: dict, status: str) -> None:
    async with session_factory()() as db:
        await db.execute(
            update(mailbox_sync_jobs)
            .where(*_claim_clause(job))
            .values(status=status, updated_at=utcnow())
        )
        await _prune_history(db, job["account_id"])
        await db.commit()


async def _prune_history(db: AsyncSession, account_id: UUID) -> None:
    ranked = (
        select(mailbox_sync_jobs.c.id)
        .where(
            mailbox_sync_jobs.c.account_id == account_id,
            mailbox_sync_jobs.c.status.in_(("done", "failed", "cancelled")),
        )
        .order_by(mailbox_sync_jobs.c.updated_at.desc(), mailbox_sync_jobs.c.created_at.desc())
        .offset(_TERMINAL_HISTORY)
    )
    await db.execute(delete(mailbox_sync_jobs).where(mailbox_sync_jobs.c.id.in_(ranked)))


async def _job_current(job: dict) -> bool:
    async with session_factory()() as db:
        row = (
            await db.execute(
                select(
                    mailbox_sync_jobs.c.status,
                    mailbox_sync_jobs.c.claim_token,
                    mailbox_connections.c.generation,
                    mailbox_connections.c.status.label("connection_status"),
                    mailbox_connections.c.login_email,
                )
                .select_from(
                    mailbox_sync_jobs.join(
                        mailbox_connections,
                        mailbox_connections.c.account_id == mailbox_sync_jobs.c.account_id,
                    )
                )
                .where(mailbox_sync_jobs.c.id == job["id"])
            )
        ).first()
        await db.rollback()
    if row is None or row.status != "leased" or row.claim_token != job.get("claim_token"):
        return False
    return (
        int(row.generation) == int(job["generation"])
        and row.connection_status == "connected"
        and row.login_email == job["login_email"]
    )


async def _sync_active(session: AsyncSession, account_id: UUID, generation: int) -> bool:
    found = await session.scalar(
        select(mailbox_sync_jobs.c.id)
        .where(
            mailbox_sync_jobs.c.account_id == account_id,
            mailbox_sync_jobs.c.generation == generation,
            mailbox_sync_jobs.c.kind == "sync",
            mailbox_sync_jobs.c.status.in_(("pending", "leased")),
        )
        .limit(1)
    )
    return found is not None


def _state(status: str, error: str | None, active: bool) -> str:
    if status == "ready" and error in _OFFLINE:
        return "offline"
    if status == "ready" and error:
        return "failed"
    if status == "ready" and active:
        return "updating"
    if status == "ready":
        return "ready"
    if active:
        return "updating"
    return "failed"


def _row_summary(row) -> dict:
    from app.mail.service import encode_ref

    return {
        "ref": encode_ref(
            row["folder_role"],
            int(row["uid_validity"]),
            int(row["uid"]),
            int(row["generation"]),
            row["account_id"],
        ),
        "subject": row["subject"] or "(no subject)",
        "sender": row["sender"],
        "recipients": row["recipients"],
        "preview": row["preview"],
        "date": row["message_date"].isoformat() if row["message_date"] else None,
        "unread": bool(row["unread"]),
        "hasAttachment": bool(row["has_attachment"]),
    }


def _like(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
