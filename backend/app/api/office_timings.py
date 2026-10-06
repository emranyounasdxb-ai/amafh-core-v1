"""Office Timing management and retained version reads."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.schemas.attendance import OfficeTimingInput, OfficeTimingPage, OfficeTimingResponse
from app.services import office_timings

router = APIRouter(tags=["office-timings"])


@router.get("/office-timings", response_model=OfficeTimingPage)
async def list_office_timings(
    db: Db,
    actor: ActorDep,
    branchId: UUID | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    sort: Literal["effectiveDate", "branchId", "startTime", "endTime"] | None = None,
    direction: Literal["asc", "desc"] = "asc",
):
    return await office_timings.list_versions(
        db,
        actor,
        branch_id=branchId,
        page=page,
        page_size=pageSize,
        sort=sort,
        direction=direction,
    )


@router.get("/office-timings/{timing_id}", response_model=OfficeTimingResponse)
async def office_timing_detail(timing_id: UUID, db: Db, actor: ActorDep):
    return await office_timings.detail(db, actor, timing_id)


@router.post("/office-timings", status_code=201, response_model=OfficeTimingResponse)
async def create_office_timing(item: OfficeTimingInput, db: Db, actor: CsrfActor):
    return await office_timings.create(db, actor, item)
