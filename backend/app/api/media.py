"""Authenticated record-scoped image upload and download endpoints."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, File, Response, UploadFile

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.services import media

router = APIRouter(tags=["media"])


@router.put("/employees/{employee_id}/media/{kind}")
async def put_employee_media(
    employee_id: UUID,
    kind: Literal["avatar", "cover"],
    db: Db,
    actor: CsrfActor,
    file: Annotated[UploadFile, File()],
):
    return await media.upload(db, actor, "employee", employee_id, kind, file)


@router.get("/employees/{employee_id}/media/{kind}")
async def get_employee_media(
    employee_id: UUID, kind: Literal["avatar", "cover"], db: Db, actor: ActorDep
):
    data, mime = await media.download(db, actor, "employee", employee_id, kind)
    return Response(data, media_type=mime, headers={"X-Content-Type-Options": "nosniff"})


@router.put("/catalog/{kind}/{record_id}/image")
async def put_catalog_image(
    kind: Literal["banks", "product-types", "product-variants"],
    record_id: UUID,
    db: Db,
    actor: CsrfActor,
    file: Annotated[UploadFile, File()],
):
    return await media.upload(db, actor, kind, record_id, "image", file)


@router.get("/catalog/{kind}/{record_id}/image")
async def get_catalog_image(
    kind: Literal["banks", "product-types", "product-variants"],
    record_id: UUID,
    db: Db,
    actor: ActorDep,
):
    data, mime = await media.download(db, actor, kind, record_id, "image")
    return Response(data, media_type=mime, headers={"X-Content-Type-Options": "nosniff"})
