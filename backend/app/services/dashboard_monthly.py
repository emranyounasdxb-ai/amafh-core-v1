"""One request for Dashboard monthly values from existing authorized calculations."""

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.policies import Actor
from app.schemas.performance import PerformanceFilters
from app.schemas.reports import ReportFilters
from app.services import coordinator_workload, dashboard, performance_reads, reports
from app.services.performance_math import DUBAI
from app.services.performance_scope import resolve


def _months(start: date, end: date) -> list[tuple[date, date]]:
    months = []
    cursor = start
    while cursor <= end:
        next_month = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
        last = min(end, next_month - timedelta(days=1))
        months.append((cursor, last))
        cursor = next_month
    return months


async def read(session: AsyncSession, actor: Actor, filters: ReportFilters) -> dict:
    start, end = reports.interval(filters)
    if end > datetime.now(DUBAI).date():
        raise ApiError(422, "DASHBOARD_DATE_INVALID", "Future Dashboard date is unavailable")
    if actor.designation not in dashboard.PERFORMANCE_ROLES:
        raise ApiError(403, "FORBIDDEN", "Access denied")
    session.info["performance_records_cache"] = {}
    session.info["performance_metrics_cache"] = {}
    session.info["holiday_calendar_cache"] = {}
    try:
        base = PerformanceFilters(
            startDate=start,
            endDate=end,
            branchId=filters.branchId,
            departmentId=filters.departmentId,
            teamId=filters.teamId,
            productCode=filters.productCode,
            bankId=filters.bankId,
        )
        if actor.designation in dashboard.REPORT_ROLES:
            await dashboard.preload_visible_performance(session, actor, base)
        team_id = None
        if actor.designation == "Team Leader":
            team_id = (await resolve(session, actor, base)).team_id
        items = []
        for month_start, month_end in _months(start, end):
            values: dict[str, dict] = {}
            for product in (filters.productCode,) if filters.productCode else ("CC", "PF"):
                scoped = base.model_copy(
                    update={
                        "startDate": month_start,
                        "endDate": month_end,
                        "productCode": product,
                    }
                )
                if actor.designation in dashboard.REPORT_ROLES:
                    report_filters = filters.model_copy(
                        update={
                            "period": "custom",
                            "startDate": month_start,
                            "endDate": month_end,
                            "productCode": product,
                        }
                    )
                    values[product] = (
                        await reports.read(
                            session, actor, "sales-performance", report_filters, page=1, page_size=1
                        )
                    )["summary"]
                elif actor.designation == "Team Leader" and team_id is not None:
                    values[product] = (
                        await performance_reads.team_detail(
                            session, actor, team_id, scoped, page=1, page_size=1
                        )
                    )["summary"]
                elif actor.designation == "Coordinator":
                    values[product] = await coordinator_workload.own_monthly_metric(
                        session, actor, scoped
                    )
                else:
                    values[product] = await performance_reads.own(session, actor, scoped)
            count_key = (
                "createdCases"
                if actor.designation in dashboard.REPORT_ROLES
                else "handledCases"
                if actor.designation == "Coordinator"
                else "createdCaseCount"
            )
            pf = values.get("PF")
            items.append(
                {
                    "start": month_start.isoformat(),
                    "end": month_end.isoformat(),
                    "label": month_start.strftime("%Y-%m"),
                    "cc": values["CC"][count_key] if "CC" in values else None,
                    "pf": pf[count_key] if pf is not None else None,
                    "pfAed": (
                        str(Decimal(pf["achievedPFAed"]))
                        if pf is not None and actor.designation != "Coordinator"
                        else None
                    ),
                }
            )
        return {"startDate": start.isoformat(), "endDate": end.isoformat(), "items": items}
    finally:
        session.info.pop("performance_records_cache", None)
        session.info.pop("performance_metrics_cache", None)
        session.info.pop("holiday_calendar_cache", None)
