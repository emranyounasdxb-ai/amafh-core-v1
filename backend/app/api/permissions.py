"""User Type permissions: Owner/MD read, Owner-only configuration."""

from uuid import UUID

from fastapi import APIRouter

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.schemas.permissions import PermissionUpdate
from app.services import permission_config

router = APIRouter(tags=["permissions"])


@router.get("/permissions")
async def list_permissions(actor: ActorDep, db: Db):
    return await permission_config.effective(db, actor)


@router.get("/permission-configuration")
async def get_configuration(actor: ActorDep, db: Db):
    return await permission_config.read(db, actor)


@router.put("/permission-configuration/{designation_id}")
async def update_configuration(
    designation_id: UUID, payload: PermissionUpdate, actor: CsrfActor, db: Db
):
    return await permission_config.update(
        db, actor, designation_id, payload.revision, payload.grants
    )
