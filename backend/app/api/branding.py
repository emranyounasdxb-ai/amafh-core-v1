"""Authenticated global banner reads and Owner-only management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Response, UploadFile

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.services import branding

router = APIRouter(prefix="/branding/profile-banner", tags=["branding"])


@router.get("")
async def get_global_banner(db: Db, _actor: ActorDep):
    return await branding.current(db)


@router.get("/files/{file_id}")
async def get_global_banner_image(file_id: UUID, db: Db, _actor: ActorDep):
    data, mime = await branding.image(db, file_id)
    return Response(data, media_type=mime, headers={"X-Content-Type-Options": "nosniff"})


@router.put("")
async def put_global_banner(db: Db, actor: CsrfActor, file: Annotated[UploadFile, File()]):
    return await branding.upload(db, actor, file)


@router.post("/reset")
async def reset_global_banner(db: Db, actor: CsrfActor):
    return await branding.reset(db, actor)
