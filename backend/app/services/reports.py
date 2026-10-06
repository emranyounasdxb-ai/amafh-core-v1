"""One authorized report result for on-screen pages and both export formats."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import employees
from app.errors import ApiError
from app.policies import Actor
from app.schemas.performance import PerformanceFilters
from app.schemas.reports import ReportFilters
from app.services import asset_reads, attendance_reads, coordinator_workload, performance_rankings
from app.services.performance_math import DUBAI
from app.services.performance_metrics import derive
from app.services.performance_records import preload
from app.services.performance_scope import filtered_employee_ids, resolve
from app.services.public_row_sort import sort_rows
from app.services.report_catalog import CATALOG, authorize
from app.services.report_finance import finance_report
from app.services.report_people import assignment_report, paid_totals
from app.services.report_queries import case_pipeline, customer_report, employee_report

REPORT_SORT_FIELDS = {
    kind: {key for key, _ in definition[2]} for kind, definition in CATALOG.items()
}


def interval(filters: ReportFilters) -> tuple[date, date]:
    today = datetime.now(DUBAI).date()
    if filters.period == "custom":
        assert filters.startDate and filters.endDate
        return filters.startDate, filters.endDate
    if filters.period == "today":
        return today, today
    if filters.period == "week":
        return today - timedelta(days=today.weekday()), today
    if filters.period == "month":
        return today.replace(day=1), today
    return today.replace(month=1, day=1), today


def _scalar(value) -> str | int | bool | None:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    raise ValueError("Report column is not scalar")


async def _performance(
    session: AsyncSession,
    actor: Actor,
    kind: str,
    filters: ReportFilters,
    start: date,
    end: date,
    page: int,
    size: int,
    max_rows: int | None = None,
    sort: str | None = None,
    direction: str = "asc",
) -> tuple[list[dict], int, dict]:
    current = PerformanceFilters(
        startDate=start,
        endDate=end,
        branchId=filters.branchId,
        departmentId=filters.departmentId,
        teamId=filters.teamId,
        designationId=filters.designationId,
        productCode=filters.productCode,
        bankId=filters.bankId,
    )
    finance_report = actor.designation == "Finance"
    if kind == "ranking":
        if filters.productCode is None:
            raise ApiError(422, "PRODUCT_REQUIRED", "Ranking requires a product")
        result = await performance_rankings.read(
            session,
            actor,
            current,
            page=page,
            page_size=size,
            finance_report=finance_report,
            max_rows=max_rows,
            sort=sort,
            direction=direction,
        )
        return (
            result["items"],
            result["total"],
            {
                "rankedEmployees": result["total"],
                "winnerEmployeeId": result["winnerEmployeeId"],
                "decisionState": result["decisionState"],
            },
        )
    if kind == "coordinator-workload":
        result = await coordinator_workload.list_workload(
            session,
            actor,
            current,
            page=page,
            page_size=size,
            finance_report=finance_report,
            max_rows=max_rows,
            sort=sort,
            direction=direction,
        )
        return result["items"], result["total"], {"coordinators": result["total"]}
    scope = await resolve(session, actor, current, finance_report=finance_report)
    ids = await filtered_employee_ids(session, scope, current)
    if filters.employeeId is not None:
        ids = [employee_id for employee_id in ids if employee_id == filters.employeeId]
    if max_rows is not None and len(ids) > max_rows:
        return [], len(ids), {}
    rows = (
        (
            await session.execute(
                select(employees)
                .where(employees.c.id.in_(ids))
                .order_by(
                    (
                        employees.c.full_name.asc()
                        if direction == "asc"
                        else employees.c.full_name.desc()
                    )
                    if sort == "employeeName"
                    else employees.c.id,
                    employees.c.id,
                )
            )
        )
        .mappings()
        .all()
    )
    owned_cache = "performance_records_cache" not in session.info
    if owned_cache:
        session.info["performance_records_cache"] = {}
    try:
        await preload(session, [dict(row) for row in rows])
        all_metrics = [await derive(session, scope, dict(row), current) for row in rows]
    finally:
        if owned_cache:
            session.info.pop("performance_records_cache", None)
    names = {str(row["id"]): row["full_name"] for row in rows}
    items = []
    for metric in all_metrics:
        progress = metric["targetProgress"]
        product = filters.productCode
        achievement = progress[product]["achievementPercentage"] if product else None
        items.append(
            {
                "employeeId": metric["employeeId"],
                "employeeName": names[metric["employeeId"]],
                "createdCaseCount": metric["createdCaseCount"],
                "bookedCaseCount": metric["bookedCaseCount"],
                "completedCaseCount": metric["completedCaseCount"],
                "rejectedCaseCount": metric["rejectedCaseCount"],
                "delayedCaseCount": metric["delayedCaseCount"],
                "achievedCCPoints": metric["achievedCCPoints"],
                "achievedPFAed": metric["achievedPFAed"],
                "achievementPercentage": achievement,
            }
        )
    if sort is not None:
        items = sort_rows(items, sort, direction)
    return (
        items[(page - 1) * size : page * size],
        len(ids),
        {
            "employees": len(ids),
            "createdCases": sum(item["createdCaseCount"] for item in all_metrics),
            "bookedCases": sum(item["bookedCaseCount"] for item in all_metrics),
            "completedCases": sum(item["completedCaseCount"] for item in all_metrics),
            "rejectedCases": sum(item["rejectedCaseCount"] for item in all_metrics),
            "delayedCases": sum(item["delayedCaseCount"] or 0 for item in all_metrics)
            if all(item["delayedCaseCount"] is not None for item in all_metrics)
            else None,
            "achievedCCPoints": sum(Decimal(item["achievedCCPoints"]) for item in all_metrics),
            "achievedPFAed": sum(Decimal(item["achievedPFAed"]) for item in all_metrics),
        },
    )


async def read(
    session: AsyncSession,
    actor: Actor,
    kind: str,
    filters: ReportFilters,
    *,
    page: int,
    page_size: int,
    export_limit: int | None = None,
    sort: str | None = None,
    direction: str = "asc",
) -> dict:
    active = {
        key
        for key, value in filters.model_dump(exclude={"period", "startDate", "endDate"}).items()
        if value is not None
    }
    title, _, columns, _ = authorize(actor, kind, active)
    if (sort is not None and sort not in REPORT_SORT_FIELDS[kind]) or direction not in {
        "asc",
        "desc",
    }:
        raise ApiError(422, "REPORT_SORT_UNSUPPORTED", "Unsupported report sort")
    start, end = interval(filters)
    if kind == "case-pipeline":
        items, total, summary = await case_pipeline(
            session, actor, filters, start, end, page, page_size, export_limit, sort, direction
        )
    elif kind == "customers":
        items, total, summary = await customer_report(
            session, actor, filters, start, end, page, page_size, export_limit, sort, direction
        )
    elif kind in {"sales-performance", "ranking", "coordinator-workload"}:
        items, total, summary = await _performance(
            session,
            actor,
            kind,
            filters,
            start,
            end,
            page,
            page_size,
            export_limit,
            sort,
            direction,
        )
    elif kind == "finance-paid-totals":
        items, total, summary = await paid_totals(
            session, actor, filters, start, end, page, page_size, export_limit, sort, direction
        )
    elif kind.startswith("finance-"):
        items, total, summary = await finance_report(
            session,
            actor,
            kind,
            filters,
            start,
            end,
            page,
            page_size,
            export_limit,
            sort,
            direction,
        )
    elif kind == "attendance":
        result = await attendance_reads.list_records(
            session,
            actor,
            branch_id=filters.branchId,
            employee_id=filters.employeeId,
            date_from=start,
            date_to=end,
            status=filters.status,
            is_late=None,
            search=None,
            page=page,
            page_size=page_size,
            sort=sort or "attendanceDate",
            direction=direction if sort else "desc",
        )
        items, total = result["items"], result["total"]
        summary = {key: result[key] for key in ("presentCount", "absentCount", "lateCount")}
    elif kind == "assets":
        result = await asset_reads.list_assets(
            session,
            actor,
            branch_id=filters.branchId,
            category=filters.category,
            status=filters.status,
            employee_id=filters.employeeId,
            date_from=start,
            date_to=end,
            page=page,
            page_size=page_size,
            sort=sort or "createdAt",
            direction=direction if sort else "desc",
        )
        items, total = result["items"], result["total"]
        summary = {
            key: result[key]
            for key in ("availableCount", "issuedCount", "maintenanceCount", "damagedCount")
        }
    elif kind == "hr-assignments":
        items, total, summary = await assignment_report(
            session, filters, start, end, page, page_size, export_limit, sort, direction
        )
    else:
        items, total, summary = await employee_report(
            session, filters, start, end, page, page_size, export_limit, sort, direction
        )
    approved = tuple(key for key, _ in columns)
    return {
        "report": kind,
        "title": title,
        "columns": [{"key": key, "heading": heading} for key, heading in columns],
        "items": [{key: _scalar(row.get(key)) for key in approved} for row in items],
        "summary": {key: _scalar(value) for key, value in summary.items()},
        "total": total,
        "page": page,
        "pageSize": page_size,
        "startDate": start,
        "endDate": end,
        "filters": {
            key: str(value)
            for key, value in filters.model_dump().items()
            if value is not None and key not in {"startDate", "endDate", "period"}
        },
    }
