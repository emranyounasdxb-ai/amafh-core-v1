"""Ownership-bound mailbox commands. Every call uses the signed-in account only."""

import base64
from datetime import timedelta
from email.utils import make_msgid
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.config import settings
from app.db.base import utcnow
from app.db.mailbox import (
    mailbox_connections,
    mailbox_hidden_messages,
    mailbox_outgoing_files,
    mailbox_send_attempts,
    mailbox_signatures,
)
from app.db.organization import user_accounts
from app.errors import ApiError
from app.mail.addresses import recipients
from app.mail.addresses import subject as clean_subject
from app.mail.crypto import MailboxKeyError, open_secret, seal
from app.mail.errors import PUBLIC_MESSAGES, MailFailure
from app.mail.files import (
    display_name,
    expiry,
    purge_expired,
    read_bytes,
    remove_file,
    write_bytes,
)
from app.mail.folders import ROLES
from app.mail.gateway import ImapSmtpGateway, MessageSummary
from app.mail.mime import build_message
from app.mail.received import received_html
from app.mail.runtime import get_gateway, run_mail
from app.mail.sanitize import sanitize_html
from app.policies import Actor
from app.services.auth import ensure_session_current

PAGE_SIZE = 25
TERMINAL = {"accepted", "failed", "unknown", "accepted_unrecorded", "partial"}


def failure(exc: MailFailure) -> ApiError:
    code = exc.code if exc.code in PUBLIC_MESSAGES else "unavailable"
    status = (
        422 if code in {"too_large", "address", "expired"} else 409 if code == "refused" else 503
    )
    if code in {"auth", "reconnect", "key", "ownership", "missing", "folder"}:
        status = 409 if code != "ownership" else 404
    if code == "missing":
        status = 404
    return ApiError(status, f"MAIL_{code.upper()}", PUBLIC_MESSAGES[code])


def encode_ref(
    role: str,
    uid_validity: int,
    uid: int,
    generation: int = 1,
    account_id: UUID | None = None,
) -> str:
    raw = f"{role}:{uid_validity}:{uid}:{generation}"
    if account_id is not None:
        raw = f"{raw}:{account_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_ref(value: str) -> tuple[str, int, int, int, UUID | None]:
    try:
        padded = value + "=" * (-len(value) % 4)
        parts = base64.urlsafe_b64decode(padded.encode()).decode().split(":")
        account: UUID | None = None
        if len(parts) == 3:
            role, validity, uid = parts
            generation = "1"
        elif len(parts) == 4:
            role, validity, uid, generation = parts
        elif len(parts) == 5:
            role, validity, uid, generation, account_text = parts
            account = UUID(account_text)
        else:
            raise ValueError
        if role not in ROLES or int(validity) < 1 or int(uid) < 1 or int(generation) < 1:
            raise ValueError
        return role, int(validity), int(uid), int(generation), account
    except ValueError, UnicodeError:
        raise ApiError(404, "MAIL_MISSING", PUBLIC_MESSAGES["missing"]) from None


def limits_payload() -> dict:
    current = settings()
    return {
        "attachmentBytes": current.mail_attachment_bytes,
        "attachmentsBytes": current.mail_attachments_bytes,
        "messageBytes": current.mail_message_bytes,
        "providerMessageBytes": current.mail_provider_message_bytes,
        "effectiveMessageBytes": current.effective_message_bytes(),
        "refreshSeconds": current.mail_refresh_seconds,
    }


async def _email(session: AsyncSession, actor: Actor) -> str:
    row = (
        await session.execute(
            select(user_accounts.c.login_email, user_accounts.c.access_status).where(
                user_accounts.c.id == actor.account_id
            )
        )
    ).one()
    if row.access_status != "Active":
        raise ApiError(401, "AUTH_REQUIRED", "Authentication required")
    if not row.login_email:
        raise ApiError(422, "MAIL_ADDRESS", PUBLIC_MESSAGES["address"])
    return row.login_email


async def _confirm(session: AsyncSession, actor: Actor, email: str) -> None:
    row = (
        await session.execute(
            select(user_accounts.c.login_email, user_accounts.c.access_status).where(
                user_accounts.c.id == actor.account_id
            )
        )
    ).one()
    if row.access_status != "Active" or row.login_email != email:
        raise ApiError(401, "AUTH_REQUIRED", "Authentication required")
    await ensure_session_current(session, actor)


async def _current_generation(session: AsyncSession, actor: Actor) -> int:
    row = await _connection(session, actor)
    if not row:
        raise ApiError(404, "MAIL_MISSING", PUBLIC_MESSAGES["missing"])
    return int(row["generation"])


async def _owned_ref(session: AsyncSession, actor: Actor, ref: str) -> tuple[str, int, int]:
    role, validity, uid, generation, account = decode_ref(ref)
    if account is not None and account != actor.account_id:
        raise ApiError(404, "MAIL_MISSING", PUBLIC_MESSAGES["missing"])
    if generation != await _current_generation(session, actor):
        raise ApiError(404, "MAIL_MISSING", PUBLIC_MESSAGES["missing"])
    return role, validity, uid


async def _connection(session: AsyncSession, actor: Actor):
    return (
        (
            await session.execute(
                select(mailbox_connections).where(
                    mailbox_connections.c.account_id == actor.account_id
                )
            )
        )
        .mappings()
        .first()
    )


async def _password(session: AsyncSession, actor: Actor, email: str) -> str:
    row = await _connection(session, actor)
    if not row or row["status"] != "connected" or row["login_email"] != email or not row["secret"]:
        raise ApiError(409, "MAIL_RECONNECT", PUBLIC_MESSAGES["reconnect"])
    try:
        return open_secret(row["secret"])
    except MailboxKeyError:
        await session.execute(
            update(mailbox_connections)
            .where(mailbox_connections.c.account_id == actor.account_id)
            .values(secret=None, status="reconnect")
        )
        await session.commit()
        raise ApiError(409, "MAIL_KEY", PUBLIC_MESSAGES["key"]) from None


async def connection_view(session: AsyncSession, actor: Actor) -> dict:
    email = await _email(session, actor)
    row = await _connection(session, actor)
    connected = bool(
        row and row["status"] == "connected" and row["login_email"] == email and row["secret"]
    )
    return {
        "address": email,
        "connected": connected,
        "reconnectRequired": bool(
            row and row["login_email"] == email and not connected and row["status"] == "reconnect"
        ),
    }


async def connect(session: AsyncSession, actor: Actor, password: str) -> dict:
    email = await _email(session, actor)
    if not password or len(password) > 256:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Enter the mailbox password",
            {"password": ["Enter the mailbox password."]},
        )
    try:
        sealed = seal(password)
    except MailboxKeyError:
        raise ApiError(409, "MAIL_KEY", PUBLIC_MESSAGES["key"]) from None
    try:
        await run_mail(get_gateway().verify, email, password)
    except MailFailure as exc:
        raise failure(exc) from None
    await _confirm(session, actor, email)
    existing = await _connection(session, actor)
    values = {"login_email": email, "secret": sealed, "status": "connected"}
    if existing:
        await session.execute(
            update(mailbox_connections)
            .where(mailbox_connections.c.account_id == actor.account_id)
            .values(**values)
        )
    else:
        await session.execute(
            mailbox_connections.insert().values(
                id=uuid4(), account_id=actor.account_id, generation=1, **values
            )
        )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="mailbox.connected",
        module="mailbox",
        entity_type="user_account",
        entity_id=actor.account_id,
    )
    await session.commit()
    return {"address": email, "connected": True, "reconnectRequired": False}


async def disconnect(session: AsyncSession, actor: Actor) -> None:
    await _email(session, actor)
    await session.execute(
        update(mailbox_connections)
        .where(mailbox_connections.c.account_id == actor.account_id)
        .values(secret=None, status="disconnected")
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="mailbox.disconnected",
        module="mailbox",
        entity_type="user_account",
        entity_id=actor.account_id,
    )
    await session.commit()


async def _open(session: AsyncSession, actor: Actor) -> tuple[str, str]:
    email = await _email(session, actor)
    password = await _password(session, actor, email)
    return email, password


async def _hidden(
    session: AsyncSession, actor: Actor, email: str, role: str, validity: int
) -> set[int]:
    rows = (
        await session.execute(
            select(mailbox_hidden_messages.c.uid).where(
                mailbox_hidden_messages.c.account_id == actor.account_id,
                mailbox_hidden_messages.c.login_email == email,
                mailbox_hidden_messages.c.folder_role == role,
                mailbox_hidden_messages.c.uid_validity == validity,
            )
        )
    ).scalars()
    return set(rows)


async def _folder(session: AsyncSession, actor: Actor, email: str, password: str, role: str):
    if role not in ROLES:
        raise ApiError(404, "MAIL_FOLDER", PUBLIC_MESSAGES["folder"])
    try:
        gateway = get_gateway()
        if isinstance(gateway, ImapSmtpGateway):
            match = await run_mail(gateway.folder, email, password, role)
        else:
            folders = await run_mail(gateway.folders, email, password)
            match = next((folder for folder in folders if folder.role == role), None)
    except MailFailure as exc:
        await _auth_followup(session, actor, exc)
        raise failure(exc) from None
    await _confirm(session, actor, email)
    if match is None:
        raise ApiError(404, "MAIL_FOLDER", PUBLIC_MESSAGES["folder"])
    return match


async def _auth_followup(session: AsyncSession, actor: Actor, exc: MailFailure) -> None:
    if exc.code == "auth":
        await session.execute(
            update(mailbox_connections)
            .where(mailbox_connections.c.account_id == actor.account_id)
            .values(secret=None, status="reconnect")
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="mailbox.reconnect_required",
            module="mailbox",
            entity_type="user_account",
            entity_id=actor.account_id,
        )
        await session.commit()


def _summary(item, role: str, validity: int, generation: int, account_id: UUID) -> dict:
    return {
        "ref": encode_ref(role, validity, item.uid, generation, account_id),
        "subject": item.subject or "(no subject)",
        "sender": item.sender,
        "recipients": item.recipients,
        "preview": item.preview,
        "date": item.message_date.isoformat() if item.message_date else None,
        "unread": item.unread,
        "hasAttachment": item.has_attachment,
    }


async def summary(session: AsyncSession, actor: Actor) -> dict:
    view = await connection_view(session, actor)
    unread = {role: 0 for role in (*ROLES, "deleted")}
    if not view["connected"]:
        return {**view, "unread": unread}
    email, password = await _open(session, actor)
    try:
        folders = await run_mail(get_gateway().folders, email, password)
    except MailFailure as exc:
        await _auth_followup(session, actor, exc)
        if exc.code == "auth":
            return {**await connection_view(session, actor), "unread": unread}
        raise failure(exc) from None
    for folder in folders:
        hidden = await _hidden(session, actor, email, folder.role, folder.uid_validity)
        try:
            unread[folder.role] = await run_mail(
                get_gateway().unseen, email, password, folder.name, hidden
            )
        except MailFailure as exc:
            await _auth_followup(session, actor, exc)
            raise failure(exc) from None
    await _confirm(session, actor, email)
    hidden_count = await session.scalar(
        select(mailbox_hidden_messages.c.id)
        .where(
            mailbox_hidden_messages.c.account_id == actor.account_id,
            mailbox_hidden_messages.c.login_email == email,
        )
        .limit(1)
    )
    unread["deleted"] = 0 if hidden_count is None else 1
    return {**view, "unread": unread}


async def list_messages(
    session: AsyncSession, actor: Actor, role: str, *, page: int, page_size: int, query: str
) -> dict:
    if role == "deleted":
        return await _deleted(session, actor, page, page_size, query)
    email, password = await _open(session, actor)
    folder = await _folder(session, actor, email, password, role)
    hidden = await _hidden(session, actor, email, role, folder.uid_validity)
    try:
        result = await run_mail(
            lambda: get_gateway().list_messages(
                email,
                password,
                folder.name,
                excluded=hidden,
                query=query.strip(),
                page=page,
                page_size=page_size,
            )
        )
    except MailFailure as exc:
        await _auth_followup(session, actor, exc)
        raise failure(exc) from None
    if result.uid_validity != folder.uid_validity:
        hidden = await _hidden(session, actor, email, role, result.uid_validity)
        try:
            result = await run_mail(
                lambda: get_gateway().list_messages(
                    email,
                    password,
                    folder.name,
                    excluded=hidden,
                    query=query.strip(),
                    page=page,
                    page_size=page_size,
                )
            )
        except MailFailure as exc:
            await _auth_followup(session, actor, exc)
            raise failure(exc) from None
    await _confirm(session, actor, email)
    generation = await _current_generation(session, actor)
    return {
        "items": [
            _summary(item, role, result.uid_validity, generation, actor.account_id)
            for item in result.items
        ],
        "total": result.total,
        "page": page,
        "pageSize": page_size,
        "folder": role,
        "appOnlyDeleted": False,
    }


def _like(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def _deleted(
    session: AsyncSession, actor: Actor, page: int, page_size: int, query: str
) -> dict:
    email, password = await _open(session, actor)
    try:
        folders = await run_mail(get_gateway().folders, email, password)
    except MailFailure as exc:
        await _auth_followup(session, actor, exc)
        raise failure(exc) from None
    await _confirm(session, actor, email)
    generation = await _current_generation(session, actor)
    empty = {
        "items": [],
        "total": 0,
        "page": page,
        "pageSize": page_size,
        "folder": "deleted",
        "appOnlyDeleted": True,
    }
    if not folders:
        return empty
    visible = or_(
        *[
            and_(
                mailbox_hidden_messages.c.folder_role == folder.role,
                mailbox_hidden_messages.c.uid_validity == folder.uid_validity,
            )
            for folder in folders
        ]
    )
    filters = [
        mailbox_hidden_messages.c.account_id == actor.account_id,
        mailbox_hidden_messages.c.login_email == email,
        visible,
    ]
    needle = query.strip()
    if needle:
        pattern = _like(needle)
        filters.append(
            or_(
                mailbox_hidden_messages.c.subject.ilike(pattern, escape="\\"),
                mailbox_hidden_messages.c.sender.ilike(pattern, escape="\\"),
                mailbox_hidden_messages.c.preview.ilike(pattern, escape="\\"),
            )
        )
    total = await session.scalar(
        select(func.count()).select_from(mailbox_hidden_messages).where(*filters)
    )
    rows = (
        (
            await session.execute(
                select(mailbox_hidden_messages)
                .where(*filters)
                .order_by(
                    mailbox_hidden_messages.c.hidden_at.desc(),
                    mailbox_hidden_messages.c.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    items = []
    for row in rows:
        item = _summary(
            MessageSummary(
                uid=int(row["uid"]),
                subject=row["subject"],
                sender=row["sender"],
                recipients=row["recipients"],
                preview=row["preview"],
                message_date=row["message_date"],
                unread=False,
                has_attachment=bool(row["has_attachment"]),
            ),
            row["folder_role"],
            int(row["uid_validity"]),
            generation,
            actor.account_id,
        )
        item["unread"] = False
        items.append(item)
    return {**empty, "items": items, "total": int(total or 0)}


async def read_message(session: AsyncSession, actor: Actor, ref: str) -> dict:
    role, validity, uid = await _owned_ref(session, actor, ref)
    email, password = await _open(session, actor)
    if role not in ROLES:
        raise ApiError(404, "MAIL_FOLDER", PUBLIC_MESSAGES["folder"])
    gateway = get_gateway()
    try:
        if isinstance(gateway, ImapSmtpGateway):
            content = await run_mail(
                gateway.fetch_checked,
                email,
                password,
                role,
                validity,
                uid,
                mark_seen=role != "drafts",
            )
        else:
            folder = await _folder(session, actor, email, password, role)
            if folder.uid_validity != validity:
                raise ApiError(404, "MAIL_MISSING", PUBLIC_MESSAGES["missing"])
            content = await run_mail(
                gateway.fetch,
                email,
                password,
                folder.name,
                uid,
                mark_seen=role != "drafts",
            )
    except MailFailure as exc:
        if exc.code == "folder":
            raise ApiError(404, "MAIL_FOLDER", PUBLIC_MESSAGES["folder"]) from None
        await _auth_followup(session, actor, exc)
        raise failure(exc) from None
    await _confirm(session, actor, email)
    generation = await _current_generation(session, actor)
    html = received_html(content.html, limit=settings().mail_read_bytes)
    return {
        **_summary(content.summary, role, validity, generation, actor.account_id),
        "html": html,
        "cc": content.cc,
        "bcc": content.bcc,
        "attachments": [
            {
                "index": part.index,
                "filename": part.filename,
                "contentType": part.content_type,
                "size": part.size,
            }
            for part in content.attachments
        ],
        "messageId": content.message_id,
        "replyTo": content.reply_to,
        "appOnlyDeleted": False,
    }


async def attachment(session: AsyncSession, actor: Actor, ref: str, index: int):
    role, validity, uid = await _owned_ref(session, actor, ref)
    email, password = await _open(session, actor)
    folder = await _folder(session, actor, email, password, role)
    if folder.uid_validity != validity:
        raise ApiError(404, "MAIL_MISSING", PUBLIC_MESSAGES["missing"])
    try:
        filename, content_type, data = await run_mail(
            get_gateway().fetch_attachment, email, password, folder.name, uid, index
        )
    except MailFailure as exc:
        await _auth_followup(session, actor, exc)
        raise failure(exc) from None
    await _confirm(session, actor, email)
    return display_name(filename), content_type, data


def _hidden_metadata(summary) -> dict:
    return {
        "subject": (summary.subject or "")[:998],
        "sender": (summary.sender or "")[:998],
        "recipients": (summary.recipients or "")[:998],
        "preview": (summary.preview or "")[:180],
        "message_date": summary.message_date,
        "has_attachment": bool(summary.has_attachment),
    }


async def hide(session: AsyncSession, actor: Actor, ref: str) -> None:
    role, validity, uid = await _owned_ref(session, actor, ref)
    email, password = await _open(session, actor)
    folder = await _folder(session, actor, email, password, role)
    if folder.uid_validity != validity:
        raise ApiError(404, "MAIL_MISSING", PUBLIC_MESSAGES["missing"])
    try:
        summary = await run_mail(get_gateway().message_summary, email, password, folder.name, uid)
    except MailFailure as exc:
        await _auth_followup(session, actor, exc)
        raise failure(exc) from None
    await _confirm(session, actor, email)
    await session.execute(
        pg_insert(mailbox_hidden_messages)
        .values(
            id=uuid4(),
            account_id=actor.account_id,
            login_email=email,
            folder_role=role,
            uid_validity=validity,
            uid=uid,
            hidden_at=utcnow(),
            **_hidden_metadata(summary),
        )
        .on_conflict_do_nothing(constraint="uq_mailbox_hidden_ref")
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="mailbox.message_hidden",
        module="mailbox",
        entity_type="user_account",
        entity_id=actor.account_id,
    )
    await session.commit()


async def restore(session: AsyncSession, actor: Actor, ref: str) -> None:
    role, validity, uid = await _owned_ref(session, actor, ref)
    email = await _email(session, actor)
    result = await session.execute(
        delete(mailbox_hidden_messages).where(
            mailbox_hidden_messages.c.account_id == actor.account_id,
            mailbox_hidden_messages.c.login_email == email,
            mailbox_hidden_messages.c.folder_role == role,
            mailbox_hidden_messages.c.uid_validity == validity,
            mailbox_hidden_messages.c.uid == uid,
        )
    )
    if getattr(result, "rowcount", 0) == 0:
        raise ApiError(404, "MAIL_MISSING", PUBLIC_MESSAGES["missing"])
    await audit.record(
        session,
        actor=actor.employee_id,
        action="mailbox.message_restored",
        module="mailbox",
        entity_type="user_account",
        entity_id=actor.account_id,
    )
    await session.commit()


async def save_signature(session: AsyncSession, actor: Actor, html: str) -> dict:
    await _email(session, actor)
    cleaned = sanitize_html(html)
    if not cleaned:
        raise ApiError(
            422, "VALIDATION_ERROR", "Enter signature text", {"html": ["Enter signature text."]}
        )
    await session.execute(
        pg_insert(mailbox_signatures)
        .values(account_id=actor.account_id, body_html=cleaned)
        .on_conflict_do_update(
            index_elements=[mailbox_signatures.c.account_id],
            set_={"body_html": cleaned, "updated_at": utcnow()},
        )
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="mailbox.signature_saved",
        module="mailbox",
        entity_type="user_account",
        entity_id=actor.account_id,
    )
    await session.commit()
    return {"html": cleaned}


async def signature(session: AsyncSession, actor: Actor) -> dict:
    await _email(session, actor)
    row = (
        await session.execute(
            select(mailbox_signatures.c.body_html).where(
                mailbox_signatures.c.account_id == actor.account_id
            )
        )
    ).first()
    return {"html": row[0] if row else ""}


async def remove_signature(session: AsyncSession, actor: Actor) -> None:
    await _email(session, actor)
    await session.execute(
        delete(mailbox_signatures).where(mailbox_signatures.c.account_id == actor.account_id)
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="mailbox.signature_removed",
        module="mailbox",
        entity_type="user_account",
        entity_id=actor.account_id,
    )
    await session.commit()


async def store_attachment(
    session: AsyncSession, actor: Actor, filename: str, content_type: str, data: bytes
) -> dict:
    await _email(session, actor)
    await purge_expired(session, actor.account_id)
    limit = settings().mail_attachment_bytes
    if len(data) > limit:
        raise ApiError(
            413,
            "MAIL_TOO_LARGE",
            PUBLIC_MESSAGES["too_large"],
            {"file": [f"Each attachment must be {limit} bytes or smaller."]},
        )
    if not data:
        raise ApiError(422, "VALIDATION_ERROR", "The file is empty", {"file": ["Choose a file."]})
    stored = write_bytes(actor.account_id, data)
    file_id = uuid4()
    await session.execute(
        mailbox_outgoing_files.insert().values(
            id=file_id,
            account_id=actor.account_id,
            stored_name=stored,
            filename=display_name(filename),
            content_type=(content_type or "application/octet-stream")[:120],
            size_bytes=len(data),
            expires_at=expiry(),
        )
    )
    await session.commit()
    return {"id": str(file_id), "filename": display_name(filename), "size": len(data)}


async def discard_attachment(session: AsyncSession, actor: Actor, file_id: UUID) -> None:
    row = (
        (
            await session.execute(
                select(mailbox_outgoing_files).where(
                    mailbox_outgoing_files.c.id == file_id,
                    mailbox_outgoing_files.c.account_id == actor.account_id,
                )
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ApiError(404, "MAIL_OWNERSHIP", PUBLIC_MESSAGES["ownership"])
    remove_file(actor.account_id, row["stored_name"])
    await session.execute(
        delete(mailbox_outgoing_files).where(mailbox_outgoing_files.c.id == file_id)
    )
    await session.commit()


async def _owned_files(
    session: AsyncSession, actor: Actor, file_ids: list[UUID]
) -> list[tuple[str, str, bytes]]:
    if not file_ids:
        return []
    await purge_expired(session, actor.account_id)
    rows = (
        (
            await session.execute(
                select(mailbox_outgoing_files).where(
                    mailbox_outgoing_files.c.id.in_(file_ids),
                    mailbox_outgoing_files.c.account_id == actor.account_id,
                )
            )
        )
        .mappings()
        .all()
    )
    if len(rows) != len(set(file_ids)):
        raise ApiError(404, "MAIL_OWNERSHIP", PUBLIC_MESSAGES["ownership"])
    now = utcnow()
    files = []
    total = 0
    for row in rows:
        if row["expires_at"] <= now:
            raise ApiError(409, "MAIL_EXPIRED", PUBLIC_MESSAGES["expired"])
        total += row["size_bytes"]
        if (
            row["size_bytes"] > settings().mail_attachment_bytes
            or total > settings().mail_attachments_bytes
        ):
            raise ApiError(413, "MAIL_TOO_LARGE", PUBLIC_MESSAGES["too_large"])
        files.append(
            (row["filename"], row["content_type"], read_bytes(actor.account_id, row["stored_name"]))
        )
    return files


def _compose_bytes(
    email: str,
    to: list[str],
    cc: list[str],
    bcc: list[str],
    title: str,
    html: str,
    files,
    *,
    token: str,
    copy: bool,
    extra: dict | None = None,
    message_id: str | None = None,
) -> bytes:
    raw = build_message(
        sender=email,
        to=to,
        cc=cc,
        bcc=bcc,
        subject=title,
        html=html,
        attachments=files,
        extra_headers=extra,
        include_bcc=copy,
        token=token,
        message_id=message_id,
    )
    if len(raw) > settings().effective_message_bytes():
        raise ApiError(413, "MAIL_TOO_LARGE", PUBLIC_MESSAGES["too_large"])
    return raw


def _kept_indexes(payload: dict) -> list[int]:
    indexes = payload.get("keptAttachmentIndexes") or []
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in indexes):
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Choose an attachment from this draft",
            {"keptAttachmentIndexes": ["Choose an attachment from this draft."]},
        )
    return list(dict.fromkeys(indexes))


async def _draft_attachments(
    session: AsyncSession, actor: Actor, email: str, password: str, payload: dict
) -> list[tuple[str, str, bytes]]:
    indexes = _kept_indexes(payload)
    if not indexes:
        return []
    previous = payload.get("previousRef")
    if not previous:
        raise ApiError(404, "MAIL_MISSING", PUBLIC_MESSAGES["missing"])
    role, validity, uid, generation, account = decode_ref(previous)
    if account is not None and account != actor.account_id:
        raise ApiError(404, "MAIL_MISSING", PUBLIC_MESSAGES["missing"])
    if role != "drafts" or generation != await _current_generation(session, actor):
        raise ApiError(404, "MAIL_MISSING", PUBLIC_MESSAGES["missing"])
    folder = await _folder(session, actor, email, password, "drafts")
    if folder.uid_validity != validity:
        raise ApiError(404, "MAIL_MISSING", PUBLIC_MESSAGES["missing"])
    files: list[tuple[str, str, bytes]] = []
    for index in indexes:
        try:
            filename, content_type, data = await run_mail(
                get_gateway().fetch_attachment, email, password, folder.name, uid, index
            )
        except MailFailure as exc:
            await _auth_followup(session, actor, exc)
            raise failure(exc) from None
        if len(data) > settings().mail_attachment_bytes:
            raise ApiError(413, "MAIL_TOO_LARGE", PUBLIC_MESSAGES["too_large"])
        files.append((display_name(filename), content_type, data))
    return files


async def _outgoing_files(
    session: AsyncSession, actor: Actor, email: str, password: str, payload: dict
) -> list[tuple[str, str, bytes]]:
    uploaded = await _owned_files(
        session, actor, [UUID(item) for item in payload.get("attachmentIds") or []]
    )
    kept = await _draft_attachments(session, actor, email, password, payload)
    total = sum(len(data) for _name, _kind, data in (*uploaded, *kept))
    if total > settings().mail_attachments_bytes:
        raise ApiError(413, "MAIL_TOO_LARGE", PUBLIC_MESSAGES["too_large"])
    return [*kept, *uploaded]


async def save_draft(session: AsyncSession, actor: Actor, payload: dict) -> dict:
    email, password = await _open(session, actor)
    folder = await _folder(session, actor, email, password, "drafts")
    to = recipients(payload.get("to") or [], "to")
    cc = recipients(payload.get("cc") or [], "cc")
    bcc = recipients(payload.get("bcc") or [], "bcc")
    title = clean_subject(payload.get("subject") or "")
    html = sanitize_html(payload.get("html") or "", limit=100_000)
    files = await _outgoing_files(session, actor, email, password, payload)
    token = uuid4().hex
    raw = _compose_bytes(email, to, cc, bcc, title, html, files, token=token, copy=True)
    try:
        validity, uid = await run_mail(
            get_gateway().append, email, password, folder.name, raw, "\\Draft"
        )
    except MailFailure as exc:
        await _auth_followup(session, actor, exc)
        raise failure(exc) from None
    generation = await _current_generation(session, actor)
    previous = payload.get("previousRef")
    replaced = False
    old_validity = old_uid = 0
    metadata = {
        "subject": "",
        "sender": "",
        "recipients": "",
        "preview": "",
        "message_date": None,
        "has_attachment": False,
    }
    if previous:
        try:
            old_role, old_validity, old_uid, old_generation, old_account = decode_ref(previous)
        except ApiError:
            old_role, old_generation, old_account = "", -1, None
            old_validity = old_uid = 0
        if (
            old_role == "drafts"
            and old_generation == generation
            and (old_account is None or old_account == actor.account_id)
        ):
            replaced = True
            if folder.uid_validity == old_validity:
                try:
                    previous_summary = await run_mail(
                        get_gateway().message_summary, email, password, folder.name, old_uid
                    )
                except MailFailure as exc:
                    await _auth_followup(session, actor, exc)
                else:
                    metadata = _hidden_metadata(previous_summary)
    await _confirm(session, actor, email)
    if replaced:
        await session.execute(
            pg_insert(mailbox_hidden_messages)
            .values(
                id=uuid4(),
                account_id=actor.account_id,
                login_email=email,
                folder_role="drafts",
                uid_validity=old_validity,
                uid=old_uid,
                hidden_at=utcnow(),
                **metadata,
            )
            .on_conflict_do_nothing(constraint="uq_mailbox_hidden_ref")
        )
    await session.commit()
    return {
        "ref": encode_ref("drafts", validity, uid, generation, actor.account_id),
        "replacedPrevious": replaced,
    }


async def send(session: AsyncSession, actor: Actor, payload: dict) -> dict:
    email, password = await _open(session, actor)
    attempt_id = UUID(payload["attemptId"])
    existing = (
        (
            await session.execute(
                select(mailbox_send_attempts).where(
                    mailbox_send_attempts.c.account_id == actor.account_id,
                    mailbox_send_attempts.c.attempt_id == attempt_id,
                )
            )
        )
        .mappings()
        .first()
    )
    if existing:
        if existing["login_email"] != email:
            raise ApiError(409, "MAIL_RECONNECT", PUBLIC_MESSAGES["reconnect"])
        if existing["status"] == "pending":
            if existing["updated_at"] < utcnow() - timedelta(
                seconds=settings().mail_timeout_seconds * 2
            ):
                await _status(session, actor, attempt_id, "unknown")
                return {"status": "unknown", "detail": PUBLIC_MESSAGES["unknown"]}
            return {"status": "sending", "detail": "Sending is already in progress."}
        return {"status": existing["status"], "detail": _status_detail(existing["status"])}
    to = recipients(payload.get("to") or [], "to")
    cc = recipients(payload.get("cc") or [], "cc")
    bcc = recipients(payload.get("bcc") or [], "bcc")
    if not to and not cc and not bcc:
        raise ApiError(
            422, "VALIDATION_ERROR", "Add a recipient", {"to": ["Add at least one recipient."]}
        )
    title = clean_subject(payload.get("subject") or "")
    html = sanitize_html(payload.get("html") or "", limit=100_000)
    files = await _outgoing_files(session, actor, email, password, payload)
    extra = {}
    if payload.get("inReplyTo"):
        extra["In-Reply-To"] = clean_subject(payload["inReplyTo"])[:998]
    if payload.get("references"):
        extra["References"] = clean_subject(payload["references"])[:998]
    token = uuid4().hex
    message_id = make_msgid(domain=email.partition("@")[2] or "localhost")
    delivered = _compose_bytes(
        email,
        to,
        cc,
        bcc,
        title,
        html,
        files,
        token=token,
        copy=False,
        extra=extra,
        message_id=message_id,
    )
    stored = _compose_bytes(
        email,
        to,
        cc,
        bcc,
        title,
        html,
        files,
        token=token,
        copy=True,
        extra=extra,
        message_id=message_id,
    )
    try:
        await session.execute(
            mailbox_send_attempts.insert().values(
                id=uuid4(),
                account_id=actor.account_id,
                attempt_id=attempt_id,
                login_email=email,
                status="pending",
            )
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return await send(session, actor, payload)
    try:
        await run_mail(get_gateway().send, email, password, [*to, *cc, *bcc], delivered)
    except MailFailure as exc:
        await _auth_followup(session, actor, exc)
        if exc.code == "partial":
            return await _partial_result(session, actor, email, password, attempt_id, exc, stored)
        status = "unknown" if exc.code == "unknown" else "failed"
        await _status(session, actor, attempt_id, status)
        await _confirm(session, actor, email)
        return {
            "status": status,
            "detail": PUBLIC_MESSAGES[exc.code if exc.code in PUBLIC_MESSAGES else "refused"],
        }
    sent_saved = False
    try:
        folder = await _folder(session, actor, email, password, "sent")
        await run_mail(get_gateway().append, email, password, folder.name, stored, "\\Seen")
        sent_saved = True
    except ApiError as error:
        if error.status == 401:
            await _status(session, actor, attempt_id, "accepted_unrecorded")
            raise
        sent_saved = False
    except MailFailure:
        sent_saved = False
    outcome = "accepted" if sent_saved else "accepted_unrecorded"
    await _status(session, actor, attempt_id, outcome)
    await _confirm(session, actor, email)
    if outcome == "accepted":
        return {
            "status": "accepted",
            "detail": (
                "The mail server accepted the message. "
                "This does not confirm the recipient received it."
            ),
        }
    return {
        "status": "accepted_unrecorded",
        "detail": (
            "The mail server accepted the message, but the Sent copy was not saved. "
            "It was not sent again. Acceptance is not proof the recipient received it."
        ),
    }


async def _partial_result(
    session: AsyncSession,
    actor: Actor,
    email: str,
    password: str,
    attempt_id: UUID,
    exc: MailFailure,
    stored: bytes,
) -> dict:
    await _status(session, actor, attempt_id, "partial")
    sent_note = ""
    try:
        folder = await _folder(session, actor, email, password, "sent")
        await run_mail(get_gateway().append, email, password, folder.name, stored, "\\Seen")
    except ApiError as error:
        if error.status == 401:
            raise
        sent_note = " The Sent copy was not saved. It was not sent again."
    except MailFailure:
        sent_note = " The Sent copy was not saved. It was not sent again."
    await _confirm(session, actor, email)
    detail = PUBLIC_MESSAGES["partial"]
    if exc.accepted:
        detail += " Accepted: " + ", ".join(exc.accepted) + "."
    if exc.refused:
        detail += " Refused: " + ", ".join(exc.refused) + "."
    return {
        "status": "partial",
        "detail": detail + sent_note,
        "accepted": exc.accepted,
        "refused": exc.refused,
    }


def _status_detail(status: str) -> str:
    if status == "accepted":
        return (
            "The mail server accepted the message. This does not confirm the recipient received it."
        )
    if status == "accepted_unrecorded":
        return (
            "The mail server accepted the message, but the Sent copy was not saved. "
            "It was not sent again."
        )
    if status == "unknown":
        return PUBLIC_MESSAGES["unknown"]
    if status == "failed":
        return PUBLIC_MESSAGES["refused"]
    if status == "partial":
        return PUBLIC_MESSAGES["partial"]
    return "Sending is already in progress."


async def _status(session: AsyncSession, actor: Actor, attempt_id: UUID, status: str) -> None:
    await session.execute(
        update(mailbox_send_attempts)
        .where(
            mailbox_send_attempts.c.account_id == actor.account_id,
            mailbox_send_attempts.c.attempt_id == attempt_id,
        )
        .values(status=status, updated_at=utcnow())
    )
    if status in {"accepted", "partial"}:
        await audit.record(
            session,
            actor=actor.employee_id,
            action="mailbox.send_accepted" if status == "accepted" else "mailbox.send_partial",
            module="mailbox",
            entity_type="user_account",
            entity_id=actor.account_id,
        )
    await session.commit()
