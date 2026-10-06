"""One retained global profile banner, managed only by the Owner."""

from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.operations import global_profile_banner, stored_files
from app.errors import ApiError
from app.policies import Actor
from app.services.media import read_stored_file
from app.services.media_storage import path_for, validated_image, write_image

BANNER_KIND = "global_profile_banner"


def _owner(actor: Actor) -> None:
    if actor.designation != "Owner":
        raise ApiError(403, "FORBIDDEN", "Access denied")


async def _reference(session: AsyncSession, *, lock: bool = False) -> UUID | None:
    query = select(global_profile_banner.c.file_id).where(global_profile_banner.c.id == 1)
    if lock:
        query = query.with_for_update()
    return (await session.execute(query)).scalar_one()


async def current(session: AsyncSession) -> dict:
    file_id = await _reference(session)
    return {"fileId": str(file_id) if file_id else None}


async def image(session: AsyncSession, file_id: UUID) -> tuple[bytes, str]:
    if await _reference(session) != file_id:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return await read_stored_file(session, file_id, BANNER_KIND)


async def upload(session: AsyncSession, actor: Actor, file: UploadFile) -> dict:
    _owner(actor)
    key = None
    try:
        before = await _reference(session, lock=True)
        data, mime, extension = await validated_image(file)
        key = write_image(BANNER_KIND, data, extension)
        file_id = uuid4()
        await session.execute(
            stored_files.insert().values(
                id=file_id,
                kind=BANNER_KIND,
                storage_key=key,
                content_type=mime,
                byte_size=len(data),
                uploaded_by_employee_id=actor.employee_id,
            )
        )
        await session.execute(
            update(global_profile_banner)
            .where(global_profile_banner.c.id == 1)
            .values(
                file_id=file_id,
                updated_by_employee_id=actor.employee_id,
                updated_at=utcnow(),
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="branding.profile_banner_updated",
            module="media",
            entity_type="global_profile_banner",
            before={"fileId": str(before) if before else None},
            after={"fileId": str(file_id), "byteSize": len(data)},
        )
        await session.commit()
        return {"fileId": str(file_id), "contentType": mime, "byteSize": len(data)}
    except Exception as exc:
        await session.rollback()
        if key is not None:
            path_for(key).unlink(missing_ok=True)
        if isinstance(exc, ApiError):
            await audit.record(
                session,
                actor=actor.employee_id,
                action="branding.profile_banner_rejected",
                module="media",
                entity_type="global_profile_banner",
                context={"reason": exc.code},
            )
            await session.commit()
        raise


async def reset(session: AsyncSession, actor: Actor) -> dict:
    _owner(actor)
    try:
        before = await _reference(session, lock=True)
        await session.execute(
            update(global_profile_banner)
            .where(global_profile_banner.c.id == 1)
            .values(
                file_id=None,
                updated_by_employee_id=actor.employee_id,
                updated_at=utcnow(),
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="branding.profile_banner_reset",
            module="media",
            entity_type="global_profile_banner",
            before={"fileId": str(before) if before else None},
            after={"fileId": None},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return {"fileId": None}
