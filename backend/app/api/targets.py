"""Restricted Phase 4 Target version API."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.schemas.performance import TargetInput, TargetPage, TargetResponse
from app.services import target_versions

router = APIRouter(tags=["targets"])


@router.get("/targets", response_model=TargetPage)
async def targets_list(
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    branchId: UUID | None = None,
    departmentId: UUID | None = None,
    designationId: UUID | None = None,
    sort: Literal["effectiveDate", "targetPoints", "targetAmountAed", "active"] | None = None,
    direction: Literal["asc", "desc"] = "asc",
):
    return await target_versions.list_versions(
        db,
        actor,
        page=page,
        page_size=pageSize,
        branch_id=branchId,
        department_id=departmentId,
        designation_id=designationId,
        sort=sort,
        direction=direction,
    )


@router.get("/targets/{target_id}", response_model=TargetResponse)
async def target_detail(target_id: UUID, db: Db, actor: ActorDep):
    return await target_versions.detail(db, actor, target_id)


@router.post("/targets", status_code=201, response_model=TargetResponse)
async def target_create(item: TargetInput, db: Db, actor: CsrfActor):
    return await target_versions.create(db, actor, item)


@router.post("/targets/{target_id}/replace", status_code=201, response_model=TargetResponse)
async def target_replace(target_id: UUID, item: TargetInput, db: Db, actor: CsrfActor):
    return await target_versions.replace(db, actor, target_id, item)


@router.post("/targets/{target_id}/deactivate", status_code=204)
async def target_deactivate(target_id: UUID, db: Db, actor: CsrfActor):
    await target_versions.deactivate(db, actor, target_id)


@router.post("/targets/{target_id}/activate", status_code=201, response_model=TargetResponse)
async def target_activate(target_id: UUID, db: Db, actor: CsrfActor):
    return await target_versions.activate(db, actor, target_id)
