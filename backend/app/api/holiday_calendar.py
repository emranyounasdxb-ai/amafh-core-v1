"""Official-source UAE holiday calendar administration."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.schemas.performance import HolidayBatchInput, HolidayInput, HolidayYearInput
from app.schemas.performance_responses import (
    HolidayDate,
    HolidayDatePage,
    HolidayYearCertification,
    HolidayYearPage,
)
from app.services import holiday_calendar

router = APIRouter(tags=["performance"])


@router.get("/performance/uae-holidays", response_model=HolidayDatePage)
async def holiday_dates(
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    year: int | None = Query(default=None, ge=1900, le=9999),
    sort: Literal["holidayDate", "name", "sourceReference"] | None = None,
    direction: Literal["asc", "desc"] = "asc",
):
    return await holiday_calendar.list_dates(
        db, actor, page=page, page_size=pageSize, year=year, sort=sort, direction=direction
    )


@router.get("/performance/uae-holiday-years", response_model=HolidayYearPage)
async def holiday_years(db: Db, actor: ActorDep):
    return await holiday_calendar.list_years(db, actor)


@router.post("/performance/uae-holidays", status_code=201, response_model=HolidayDate)
async def holiday_create(item: HolidayInput, db: Db, actor: CsrfActor):
    return await holiday_calendar.add_date(db, actor, item)


@router.post("/performance/uae-holidays/bulk", status_code=201, response_model=list[HolidayDate])
async def holiday_bulk_create(item: HolidayBatchInput, db: Db, actor: CsrfActor):
    return await holiday_calendar.add_batch(db, actor, item)


@router.patch("/performance/uae-holidays/{holiday_id}", response_model=HolidayDate)
async def holiday_edit(holiday_id: UUID, item: HolidayInput, db: Db, actor: CsrfActor):
    return await holiday_calendar.edit_date(db, actor, holiday_id, item)


@router.post(
    "/performance/uae-holiday-years/certify",
    status_code=201,
    response_model=HolidayYearCertification,
)
async def holiday_certify(item: HolidayYearInput, db: Db, actor: CsrfActor):
    return await holiday_calendar.certify_year(db, actor, item)
