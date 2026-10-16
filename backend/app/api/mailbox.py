"""Own-mailbox API. Polling reads do not record human activity."""

from uuid import UUID

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import Response

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.config import settings
from app.errors import ApiError
from app.mail import service
from app.schemas.mailbox import MailboxConnect, MailMessage, SignatureUpdate

router = APIRouter(prefix="/mailbox", tags=["mailbox"])
REQUIRED_FILE = File()
SAFE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "application/pdf",
    "text/plain",
}


@router.get("")
async def mailbox_state(actor: ActorDep, db: Db):
    return await service.connection_view(db, actor)


@router.get("/limits")
async def mailbox_limits(actor: ActorDep, db: Db):
    await service.connection_view(db, actor)
    return service.limits_payload()


@router.get("/summary")
async def mailbox_summary(actor: ActorDep, db: Db):
    return await service.summary(db, actor)


@router.post("/connection")
async def mailbox_connect(item: MailboxConnect, actor: CsrfActor, db: Db):
    return await service.connect(db, actor, item.password)


@router.delete("/connection", status_code=204)
async def mailbox_disconnect(actor: CsrfActor, db: Db):
    await service.disconnect(db, actor)


@router.get("/folders/{role}/messages")
async def mailbox_messages(
    role: str,
    actor: ActorDep,
    db: Db,
    page: int = Query(default=1, ge=1, le=1000),
    pageSize: int = Query(default=service.PAGE_SIZE, ge=1, le=50),
    q: str = Query(default="", max_length=200),
):
    if any(mark in q for mark in ("\r", "\n", "\0")):
        raise ApiError(
            422, "VALIDATION_ERROR", "Invalid search", {"q": ["Enter ordinary search text."]}
        )
    return await service.list_messages(db, actor, role, page=page, page_size=pageSize, query=q)


@router.get("/messages/{ref}")
async def mailbox_message(ref: str, actor: ActorDep, db: Db):
    return await service.read_message(db, actor, ref)


@router.get("/messages/{ref}/attachments/{index}")
async def mailbox_attachment(ref: str, index: int, actor: ActorDep, db: Db):
    filename, content_type, data = await service.attachment(db, actor, ref, index)
    served = content_type if content_type in SAFE_TYPES else "application/octet-stream"
    ascii_name = "".join(
        char if 32 <= ord(char) < 127 and char not in '"\\' else "_" for char in filename
    )
    return Response(
        content=data,
        media_type=served,
        headers={
            "Content-Disposition": f'attachment; filename="{ascii_name or "attachment"}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.post("/messages/{ref}/hide", status_code=204)
async def mailbox_hide(ref: str, actor: CsrfActor, db: Db):
    await service.hide(db, actor, ref)


@router.post("/messages/{ref}/restore", status_code=204)
async def mailbox_restore(ref: str, actor: CsrfActor, db: Db):
    await service.restore(db, actor, ref)


@router.post("/attachments")
async def mailbox_upload(actor: CsrfActor, db: Db, file: UploadFile = REQUIRED_FILE):
    limit = settings().mail_attachment_bytes
    data = await file.read(limit + 1)
    await file.close()
    return await service.store_attachment(
        db, actor, file.filename or "attachment", file.content_type or "", data
    )


@router.delete("/attachments/{file_id}", status_code=204)
async def mailbox_discard_upload(file_id: UUID, actor: CsrfActor, db: Db):
    await service.discard_attachment(db, actor, file_id)


@router.post("/drafts")
async def mailbox_draft(item: MailMessage, actor: CsrfActor, db: Db):
    return await service.save_draft(db, actor, item.model_dump(mode="json"))


@router.post("/send")
async def mailbox_send(item: MailMessage, actor: CsrfActor, db: Db):
    if item.attemptId is None:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "A send attempt is required",
            {"attemptId": ["Start the send again."]},
        )
    payload = item.model_dump(mode="json")
    return await service.send(db, actor, payload)


@router.get("/signature")
async def mailbox_signature(actor: ActorDep, db: Db):
    return await service.signature(db, actor)


@router.put("/signature")
async def mailbox_save_signature(item: SignatureUpdate, actor: CsrfActor, db: Db):
    return await service.save_signature(db, actor, item.html)


@router.delete("/signature", status_code=204)
async def mailbox_remove_signature(actor: CsrfActor, db: Db):
    await service.remove_signature(db, actor)
