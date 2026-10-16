"""Temporary outgoing attachments. Cleanup removes only these local files."""

import re
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.base import utcnow
from app.db.mailbox import mailbox_outgoing_files
from app.mail.errors import MailFailure

_NAME = re.compile(r"[^A-Za-z0-9._ -]+")


def display_name(value: str) -> str:
    base = Path(value or "attachment").name.replace("\x00", "")
    cleaned = _NAME.sub("", base).strip(" .") or "attachment"
    return cleaned[:200]


def _directory(account_id: UUID) -> Path:
    root = settings().media_storage_root.resolve()
    folder = root / "mailbox-outgoing" / str(account_id)
    folder.mkdir(parents=True, exist_ok=True)
    if not folder.resolve().is_relative_to(root):
        raise MailFailure("unavailable")
    return folder


def write_bytes(account_id: UUID, data: bytes) -> str:
    name = uuid4().hex
    path = _directory(account_id) / name
    path.write_bytes(data)
    return name


def read_bytes(account_id: UUID, stored_name: str) -> bytes:
    if not re.fullmatch(r"[0-9a-f]{32}", stored_name):
        raise MailFailure("ownership")
    path = (_directory(account_id) / stored_name).resolve()
    root = (
        settings().media_storage_root.resolve() / "mailbox-outgoing" / str(account_id)
    ).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise MailFailure("missing")
    return path.read_bytes()


def remove_file(account_id: UUID, stored_name: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{32}", stored_name):
        return
    path = (
        settings().media_storage_root.resolve() / "mailbox-outgoing" / str(account_id) / stored_name
    )
    try:
        resolved = path.resolve()
        root = (settings().media_storage_root.resolve() / "mailbox-outgoing").resolve()
        if resolved.is_relative_to(root):
            resolved.unlink(missing_ok=True)
    except OSError:
        return


async def purge_expired(session: AsyncSession, account_id: UUID | None = None) -> None:
    query = select(
        mailbox_outgoing_files.c.account_id,
        mailbox_outgoing_files.c.stored_name,
        mailbox_outgoing_files.c.id,
    ).where(mailbox_outgoing_files.c.expires_at <= utcnow())
    if account_id is not None:
        query = query.where(mailbox_outgoing_files.c.account_id == account_id)
    rows = (await session.execute(query)).all()
    if not rows:
        return
    for row in rows:
        remove_file(row.account_id, row.stored_name)
    await session.execute(
        delete(mailbox_outgoing_files).where(
            mailbox_outgoing_files.c.id.in_([row.id for row in rows])
        )
    )


async def purge_account_files(session: AsyncSession, account_id: UUID) -> None:
    rows = (
        await session.execute(
            select(mailbox_outgoing_files.c.stored_name).where(
                mailbox_outgoing_files.c.account_id == account_id
            )
        )
    ).scalars()
    for name in rows:
        remove_file(account_id, name)
    await session.execute(
        delete(mailbox_outgoing_files).where(mailbox_outgoing_files.c.account_id == account_id)
    )


def expiry():
    return utcnow() + timedelta(seconds=settings().mail_attachment_ttl_seconds)
