"""Authenticated date-filtered role Dashboard."""

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter

from app.api.dependencies import ActorDep, Db
from app.schemas.reports import ReportFilters
from app.services import dashboard, dashboard_monthly

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def get_dashboard(
    db: Db,
    actor: ActorDep,
    period: Literal["today", "week", "month", "year", "custom"] = "month",
    startDate: date | None = None,
    endDate: date | None = None,
    branchId: UUID | None = None,
    departmentId: UUID | None = None,
    teamId: UUID | None = None,
    productCode: Literal["CC", "PF"] | None = None,
    bankId: UUID | None = None,
):
    filters = ReportFilters.model_validate(
        {
            "period": period,
            "startDate": startDate,
            "endDate": endDate,
            "branchId": branchId,
            "departmentId": departmentId,
            "teamId": teamId,
            "productCode": productCode,
            "bankId": bankId,
        }
    )
    return await dashboard.read(db, actor, filters)


@router.get("/dashboard/monthly-activity")
async def get_dashboard_monthly_activity(
    db: Db,
    actor: ActorDep,
    period: Literal["today", "week", "month", "year", "custom"] = "month",
    startDate: date | None = None,
    endDate: date | None = None,
    branchId: UUID | None = None,
    departmentId: UUID | None = None,
    teamId: UUID | None = None,
    productCode: Literal["CC", "PF"] | None = None,
    bankId: UUID | None = None,
):
    filters = ReportFilters.model_validate(
        {
            "period": period,
            "startDate": startDate,
            "endDate": endDate,
            "branchId": branchId,
            "departmentId": departmentId,
            "teamId": teamId,
            "productCode": productCode,
            "bankId": bankId,
        }
    )
    return await dashboard_monthly.read(db, actor, filters)
