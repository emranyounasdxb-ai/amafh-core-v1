"""Role-scoped Dashboard projection from existing report and Performance facts."""

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.operations import notifications
from app.db.organization import employees
from app.db.tasks import tasks
from app.policies import Actor
from app.schemas.performance import PerformanceFilters
from app.schemas.reports import ReportFilters
from app.services import performance_rankings, performance_reads, reports
from app.services.performance_math import DUBAI
from app.services.performance_records import preload
from app.services.performance_scope import resolve, visible_employee_ids
from app.services.task_policy import ACTIVE, visible_task

MANAGEMENT = {"Owner", "Managing Director"}
REPORT_ROLES = MANAGEMENT | {"Sales Manager", "Finance"}
PERFORMANCE_ROLES = REPORT_ROLES | {"Team Leader", "Sales Executive", "Coordinator"}


async def read(session: AsyncSession, actor: Actor, filters: ReportFilters) -> dict:
    """Cache retained source facts only for this read; never across transactions."""
    session.info["performance_records_cache"] = {}
    session.info["performance_metrics_cache"] = {}
    session.info["holiday_calendar_cache"] = {}
    try:
        return await _read(session, actor, filters)
    finally:
        session.info.pop("performance_records_cache", None)
        session.info.pop("performance_metrics_cache", None)
        session.info.pop("holiday_calendar_cache", None)


async def preload_visible_performance(
    session: AsyncSession, actor: Actor, filters: PerformanceFilters
) -> None:
    scope = await resolve(session, actor, filters, finance_report=actor.designation == "Finance")
    visible = await visible_employee_ids(session, scope)
    if visible:
        rows = (
            await session.execute(select(employees).where(employees.c.id.in_(visible)))
        ).mappings()
        await preload(session, [dict(row) for row in rows])


async def _read(session: AsyncSession, actor: Actor, filters: ReportFilters) -> dict:
    start, end = reports.interval(filters)
    if end > datetime.now(DUBAI).date():
        from app.errors import ApiError

        raise ApiError(422, "DASHBOARD_DATE_INVALID", "Future Dashboard date is unavailable")
    task_total = (
        await session.scalar(
            select(func.count())
            .select_from(tasks)
            .where(visible_task(actor), tasks.c.status.in_(ACTIVE), tasks.c.archived_at.is_(None))
        )
        or 0
    )
    unread = (
        await session.scalar(
            select(func.count())
            .select_from(notifications)
            .where(
                notifications.c.recipient_employee_id == actor.employee_id,
                notifications.c.suppressed_at.is_(None),
                notifications.c.read_at.is_(None),
                notifications.c.available_on <= datetime.now(DUBAI).date(),
            )
        )
        or 0
    )
    result: dict = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "scope": actor.designation,
        "openTaskCount": task_total,
        "unreadNotificationCount": unread,
    }
    perf_filters = PerformanceFilters(
        startDate=start,
        endDate=end,
        branchId=filters.branchId,
        departmentId=filters.departmentId,
        teamId=filters.teamId,
        productCode=filters.productCode,
        bankId=filters.bankId,
    )
    if actor.designation in REPORT_ROLES:
        await preload_visible_performance(session, actor, perf_filters)
    if actor.designation in REPORT_ROLES:
        report = await reports.read(
            session, actor, "sales-performance", filters, page=1, page_size=1
        )
        result["performance"] = report["summary"]
    elif actor.designation in {"Team Leader", "Sales Executive", "Coordinator"}:
        result["performance"] = await performance_reads.own(session, actor, perf_filters)
        if actor.designation == "Team Leader":
            scope = await resolve(session, actor, perf_filters)
            if scope.team_id is not None:
                team = await performance_reads.team_detail(
                    session, actor, scope.team_id, perf_filters, page=1, page_size=1
                )
                result["teamPerformance"] = team["summary"]
    elif actor.designation == "Admin Staff":
        from app.errors import ApiError

        if any((filters.departmentId, filters.teamId, filters.productCode, filters.bankId)):
            raise ApiError(422, "DASHBOARD_FILTER_UNSUPPORTED", "Unsupported Dashboard filter")
        scoped = filters.model_copy(update={"branchId": filters.branchId or actor.branch_id})
        if "attendance.write" in actor.grants:
            attendance = await reports.read(
                session, actor, "attendance", scoped, page=1, page_size=1
            )
            result["attendance"] = attendance["summary"]
        if "asset.write" in actor.grants:
            assets = await reports.read(session, actor, "assets", scoped, page=1, page_size=1)
            result["assets"] = assets["summary"]
    elif actor.designation == "HR":
        from app.errors import ApiError

        if any((filters.teamId, filters.productCode, filters.bankId)):
            raise ApiError(422, "DASHBOARD_FILTER_UNSUPPORTED", "Unsupported Dashboard filter")
        people = await reports.read(session, actor, "hr-employees", filters, page=1, page_size=1)
        result["employees"] = people["summary"]
    if actor.designation in MANAGEMENT:
        booked: dict[str, int] = {}
        leaders: dict[str, dict] = {}
        month_start: date = end.replace(day=1)
        branches: dict[str, list] = {}
        products = (filters.productCode,) if filters.productCode else ("CC", "PF")
        for product in products:
            scoped = filters.model_copy(update={"productCode": product})
            summary = await reports.read(
                session, actor, "sales-performance", scoped, page=1, page_size=1
            )
            booked[product] = summary["summary"]["bookedCases"]
            monthly = perf_filters.model_copy(
                update={"startDate": month_start, "endDate": end, "productCode": product}
            )
            selected = perf_filters.model_copy(update={"productCode": product})
            month_ranking = await performance_rankings.read(
                session, actor, monthly, page=1, page_size=1
            )
            period_ranking = (
                month_ranking
                if start == month_start
                else await performance_rankings.read(session, actor, selected, page=1, page_size=1)
            )
            leaders[product] = {
                "employeeOfMonth": month_ranking,
                "highestPerformer": period_ranking,
            }
            branches[product] = (
                await performance_reads.comparison(
                    session, actor, selected, group_by="branch", page=1, page_size=100
                )
            )["items"]
        result.update(
            bookedCases=booked,
            ranking=leaders,
            branchComparison=branches,
            charts={
                "caseActivity": {
                    key: result["performance"][key]
                    for key in ("createdCases", "bookedCases", "completedCases", "rejectedCases")
                },
                "branchPerformance": branches,
            },
        )
    return result
