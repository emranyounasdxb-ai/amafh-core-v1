"""Role-scoped, paginated Phase 4 Performance API."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.errors import ApiError
from app.schemas.performance import PerformanceFilters, RankingConfirmationInput
from app.schemas.performance_responses import (
    ComparisonPage,
    CoordinatorMetrics,
    CoordinatorOwnMetrics,
    CoordinatorPage,
    EmployeeMetrics,
    EmployeePage,
    EmployeeTrend,
    RankingConfirmation,
    RankingPage,
    TeamPage,
)
from app.services import (
    coordinator_workload,
    performance_identity,
    performance_rankings,
    performance_reads,
)

router = APIRouter(tags=["performance"])


def _filters(
    startDate: date | None = None,
    endDate: date | None = None,
    branchId: UUID | None = None,
    departmentId: UUID | None = None,
    teamId: UUID | None = None,
    designationId: UUID | None = None,
    productCode: Literal["CC", "PF"] | None = None,
) -> PerformanceFilters:
    if (startDate is None) != (endDate is None) or (
        startDate is not None and endDate is not None and startDate > endDate
    ):
        raise ApiError(422, "PERFORMANCE_DATE_INVALID", "Date range is invalid")
    return PerformanceFilters(
        startDate=startDate,
        endDate=endDate,
        branchId=branchId,
        departmentId=departmentId,
        teamId=teamId,
        designationId=designationId,
        productCode=productCode,
    )


Filters = Annotated[PerformanceFilters, Depends(_filters)]
MetricSort = Literal[
    "createdCaseCount",
    "bookedCaseCount",
    "completedCaseCount",
    "achievedCCPoints",
    "achievedPFAed",
    "targetProgress",
]


async def _with_identity(db, actor, page: dict) -> dict:
    return {**page, "items": await performance_identity.attach(db, actor, page["items"])}


@router.get("/performance/me", response_model=EmployeeMetrics)
async def my_performance(db: Db, actor: ActorDep, filters: Filters):
    item = await performance_reads.own(db, actor, filters)
    return (await performance_identity.attach(db, actor, [item]))[0]


@router.get("/performance/employees", response_model=EmployeePage)
async def employee_performance_page(
    db: Db,
    actor: ActorDep,
    filters: Filters,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    sort: Literal["employeeName"] | MetricSort | None = None,
    direction: Literal["asc", "desc"] = "asc",
    search: str | None = Query(None, max_length=100),
):
    return await _with_identity(
        db,
        actor,
        await performance_reads.employees_page(
            db,
            actor,
            filters,
            page=page,
            page_size=pageSize,
            sort=sort,
            direction=direction,
            search=search,
        ),
    )


@router.get("/performance/employees/{employee_id}", response_model=EmployeeMetrics)
async def employee_performance(employee_id: UUID, db: Db, actor: ActorDep, filters: Filters):
    item = await performance_reads.detail(db, actor, employee_id, filters)
    return (await performance_identity.attach(db, actor, [item]))[0]


@router.get("/performance/employees/{employee_id}/trend", response_model=EmployeeTrend)
async def employee_performance_trend(employee_id: UUID, db: Db, actor: ActorDep, filters: Filters):
    return await performance_reads.trend(db, actor, employee_id, filters)


@router.get("/performance/teams/{team_id}", response_model=TeamPage)
async def team_performance(
    team_id: UUID,
    db: Db,
    actor: ActorDep,
    filters: Filters,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    sort: Literal["employeeName"] | MetricSort | None = None,
    direction: Literal["asc", "desc"] = "asc",
):
    return await _with_identity(
        db,
        actor,
        await performance_reads.team_detail(
            db,
            actor,
            team_id,
            filters,
            page=page,
            page_size=pageSize,
            sort=sort,
            direction=direction,
        ),
    )


@router.get("/performance/comparisons", response_model=ComparisonPage)
async def performance_comparison(
    db: Db,
    actor: ActorDep,
    filters: Filters,
    groupBy: Literal["branch", "department"],
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    sort: Literal["name"] | MetricSort | None = None,
    direction: Literal["asc", "desc"] = "asc",
):
    return await performance_reads.comparison(
        db,
        actor,
        filters,
        group_by=groupBy,
        page=page,
        page_size=pageSize,
        sort=sort,
        direction=direction,
    )


@router.get("/performance/coordinator-workload", response_model=CoordinatorPage)
async def coordinator_workload_list(
    db: Db,
    actor: ActorDep,
    filters: Filters,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    sort: Literal["employeeName", "handledCases", "submittedBookedCases", "stageUpdatedCases"]
    | None = None,
    direction: Literal["asc", "desc"] = "asc",
):
    return await _with_identity(
        db,
        actor,
        await coordinator_workload.list_workload(
            db,
            actor,
            filters,
            page=page,
            page_size=pageSize,
            sort=sort,
            direction=direction,
        ),
    )


@router.get(
    "/performance/coordinator-workload/{employee_id}",
    response_model=CoordinatorMetrics | CoordinatorOwnMetrics,
)
async def coordinator_workload_detail(
    employee_id: UUID,
    db: Db,
    actor: ActorDep,
    filters: Filters,
):
    return await coordinator_workload.workload(db, actor, employee_id, filters)


@router.get("/performance/rankings", response_model=RankingPage)
async def ranking_page(
    db: Db,
    actor: ActorDep,
    filters: Filters,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    sort: Literal["rank", "employeeName", "achievementPercentage", "completedCaseCount"]
    | None = None,
    direction: Literal["asc", "desc"] = "asc",
):
    return await performance_rankings.read(
        db,
        actor,
        filters,
        page=page,
        page_size=pageSize,
        sort=sort,
        direction=direction,
    )


@router.post("/performance/rankings/confirm", status_code=201, response_model=RankingConfirmation)
async def ranking_confirm(
    item: RankingConfirmationInput,
    db: Db,
    actor: CsrfActor,
    filters: Filters,
):
    return await performance_rankings.confirm(db, actor, filters, item.selectedEmployeeId)
