"""Record-scoped employee and catalog images with retained file metadata."""

from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.cases import banks, product_types, product_variants
from app.db.operations import stored_files
from app.db.organization import employees, team_memberships, teams
from app.errors import ApiError
from app.policies import Actor, employee_visible, require
from app.services import catalog
from app.services.media_storage import MAX_UPLOAD_BYTES, path_for, validated_image, write_image

CATALOG = {
    "banks": (banks, "bank_logo", "logo_file_id"),
    "product-types": (product_types, "product_image", "image_file_id"),
    "product-variants": (product_variants, "product_variant_image", "image_file_id"),
}


async def _employee(
    session: AsyncSession, actor: Actor, employee_id: UUID, kind: str, *, write: bool
):
    if kind not in {"avatar", "cover"}:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if write and kind == "cover":
        raise ApiError(403, "FORBIDDEN", "Access denied")
    if (
        write
        and actor.employee_id != employee_id
        and not (kind == "avatar" and actor.designation in {"Owner", "HR"})
    ):
        raise ApiError(403, "FORBIDDEN", "Access denied")
    query = select(employees).where(employees.c.id == employee_id)
    if write:
        query = query.with_for_update()
    row = (await session.execute(query)).mappings().one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if not write:
        member_ids: set[UUID] = set()
        if actor.designation == "Team Leader":
            member_ids = set(
                (
                    await session.scalars(
                        select(team_memberships.c.employee_id)
                        .join(teams, teams.c.id == team_memberships.c.team_id)
                        .where(
                            teams.c.leader_employee_id == actor.employee_id,
                            teams.c.active.is_(True),
                            team_memberships.c.end_date.is_(None),
                        )
                    )
                ).all()
            )
        if not employee_visible(actor, dict(row), member_ids):
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return (
        employees,
        dict(row),
        "employee_avatar" if kind == "avatar" else "employee_cover",
        ("avatar_file_id" if kind == "avatar" else "cover_file_id"),
    )


async def _catalog(session: AsyncSession, actor: Actor, kind: str, record_id: UUID, *, write: bool):
    if kind not in CATALOG:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if write:
        require(actor, "pipeline.write")
    else:
        await catalog.get_record(session, actor, kind, record_id)
    table, file_kind, column = CATALOG[kind]
    query = select(table).where(table.c.id == record_id)
    if write:
        query = query.with_for_update()
    row = (await session.execute(query)).mappings().one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return table, dict(row), file_kind, column


async def upload(
    session: AsyncSession,
    actor: Actor,
    record_type: str,
    record_id: UUID,
    kind: str,
    file: UploadFile,
) -> dict:
    target = (
        await _employee(session, actor, record_id, kind, write=True)
        if record_type == "employee"
        else await _catalog(session, actor, record_type, record_id, write=True)
    )
    table, row, file_kind, column = target
    key = None
    try:
        data, mime, extension = await validated_image(file)
        key = write_image(file_kind, data, extension)
        file_id = uuid4()
        await session.execute(
            stored_files.insert().values(
                id=file_id,
                kind=file_kind,
                storage_key=key,
                content_type=mime,
                byte_size=len(data),
                uploaded_by_employee_id=actor.employee_id,
            )
        )
        await session.execute(
            update(table).where(table.c.id == record_id).values({column: file_id})
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="media.image_updated",
            module="media",
            entity_type=table.name,
            entity_id=record_id,
            before={"fileId": str(row[column]) if row[column] else None},
            after={"fileId": str(file_id), "kind": file_kind, "byteSize": len(data)},
        )
        await session.commit()
        return {"fileId": str(file_id), "contentType": mime, "byteSize": len(data)}
    except Exception as exc:
        await session.rollback()
        if key is not None:
            path_for(key).unlink(missing_ok=True)
        await audit.record(
            session,
            actor=actor.employee_id,
            action="media.upload_rejected",
            module="media",
            entity_type=table.name,
            entity_id=record_id,
            context={
                "kind": file_kind,
                "reason": exc.code if isinstance(exc, ApiError) else "UPLOAD_FAILED",
            },
        )
        await session.commit()
        raise


async def download(
    session: AsyncSession, actor: Actor, record_type: str, record_id: UUID, kind: str
) -> tuple[bytes, str]:
    target = (
        await _employee(session, actor, record_id, kind, write=False)
        if record_type == "employee"
        else await _catalog(session, actor, record_type, record_id, write=False)
    )
    _, row, file_kind, column = target
    if row[column] is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return await read_stored_file(session, row[column], file_kind)


async def read_stored_file(
    session: AsyncSession, file_id: UUID, file_kind: str
) -> tuple[bytes, str]:
    file_row = (
        (
            await session.execute(
                select(stored_files).where(
                    stored_files.c.id == file_id, stored_files.c.kind == file_kind
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if file_row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if not 0 < file_row["byte_size"] <= MAX_UPLOAD_BYTES:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    path = path_for(file_row["storage_key"])
    try:
        with path.open("rb") as source:
            data = source.read(file_row["byte_size"] + 1)
    except OSError as exc:
        raise ApiError(404, "NOT_FOUND", "Record unavailable") from exc
    if len(data) != file_row["byte_size"]:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return data, file_row["content_type"]
