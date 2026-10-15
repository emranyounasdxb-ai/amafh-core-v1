"""Paginated, server-scoped individual and Team Performance reads."""

from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import employees, team_leader_history, team_memberships, teams
from app.db.query_sets import uuid_set
from app.errors import ApiError
from app.policies import Actor
from app.schemas.performance import PerformanceFilters
from app.services import performance_budget
from app.services.performance_aggregate import summarize
from app.services.performance_math import DUBAI
from app.services.performance_metrics import derive, derive_with_denominator
from app.services.performance_records import preload
from app.services.performance_scope import (
    MANAGEMENT_ROLES,
    filtered_employee_ids,
    require_employee,
    resolve,
)
from app.services.public_row_sort import sort_rows

METRIC_SORTS = {
    "createdCaseCount",
    "bookedCaseCount",
    "completedCaseCount",
    "achievedCCPoints",
    "achievedPFAed",
    "targetProgress",
}


async def own(session: AsyncSession, actor: Actor, filters: PerformanceFilters) -> dict:
    return await detail(session, actor, actor.employee_id, filters)


@performance_budget.bounded
async def detail(
    session: AsyncSession,
    actor: Actor,
    employee_id: UUID,
    filters: PerformanceFilters,
) -> dict:
    scope = await resolve(session, actor, filters)
    employee = await require_employee(session, scope, employee_id)
    return await derive(session, scope, employee, filters)


def _month_start(day: date, back: int) -> date:
    index = day.year * 12 + day.month - 1 - back
    return date(index // 12, index % 12 + 1, 1)


@performance_budget.bounded
async def trend(
    session: AsyncSession,
    actor: Actor,
    employee_id: UUID,
    filters: PerformanceFilters,
) -> dict:
    end = filters.endDate or datetime.now(DUBAI).date()
    start = max(filters.startDate or _month_start(end, 5), _month_start(end, 11))
    scope = await resolve(session, actor, filters)
    employee = await require_employee(session, scope, employee_id)
    products = (filters.productCode,) if filters.productCode else ("CC", "PF")
    items = []
    cursor = start
    while cursor <= end:
        following = _month_start(cursor, -1)
        month_end = min(end, following - timedelta(days=1))
        entry: dict = {
            "start": cursor,
            "end": month_end,
            "label": cursor.strftime("%Y-%m"),
            "CC": None,
            "PF": None,
        }
        for product in products:
            metrics = await derive(
                session,
                scope,
                employee,
                filters.model_copy(
                    update={"startDate": cursor, "endDate": month_end, "productCode": product}
                ),
            )
            progress = metrics["targetProgress"][product]
            entry[product] = {
                "createdCaseCount": metrics["createdCaseCount"],
                "bookedCaseCount": metrics["bookedCaseCount"],
                "completedCaseCount": metrics["completedCaseCount"],
                "achieved": progress["achieved"],
                "achievementPercentage": progress["achievementPercentage"],
            }
        items.append(entry)
        cursor = following
    return {"employeeId": employee_id, "startDate": start, "endDate": end, "items": items}


@performance_budget.bounded
async def employees_page(
    session: AsyncSession,
    actor: Actor,
    filters: PerformanceFilters,
    *,
    page: int,
    page_size: int,
    sort: str | None = None,
    direction: str = "asc",
    search: str | None = None,
) -> dict:
    scope = await resolve(session, actor, filters)
    ids = await filtered_employee_ids(session, scope, filters)
    if search and search.strip() and ids:
        term = f"%{search.strip()}%"
        matched = set(
            (
                await session.scalars(
                    select(employees.c.id).where(
                        uuid_set(employees.c.id, ids),
                        or_(
                            employees.c.full_name.ilike(term),
                            employees.c.system_employee_code.ilike(term),
                            employees.c.company_employee_code.ilike(term),
                        ),
                    )
                )
            ).all()
        )
        ids = [employee_id for employee_id in ids if employee_id in matched]
    total = len(ids)
    if sort not in {None, "employeeName", *METRIC_SORTS} or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    owns_cache = "performance_metrics_cache" not in session.info
    if owns_cache:
        session.info["performance_metrics_cache"] = {}
    try:
        population = (
            (await session.execute(select(employees).where(uuid_set(employees.c.id, ids))))
            .mappings()
            .all()
        )
        performance_budget.preflight(population, filters, session=session, scope=scope)
        await preload(session, [dict(row) for row in population], filters)
        summary = summarize(
            [
                await derive_with_denominator(session, scope, dict(row), filters)
                for row in population
            ]
        )
        selected = ids[(page - 1) * page_size : page * page_size] if sort is None else ids
        order = employees.c.full_name if sort == "employeeName" else employees.c.id
        rows = (
            (
                await session.execute(
                    select(employees)
                    .where(employees.c.id.in_(selected))
                    .order_by(order.asc() if direction == "asc" else order.desc(), employees.c.id)
                    .limit(page_size if sort == "employeeName" else None)
                    .offset((page - 1) * page_size if sort == "employeeName" else 0)
                )
            )
            .mappings()
            .all()
        )
        items = [await derive(session, scope, dict(row), filters) for row in rows]
    finally:
        if owns_cache:
            session.info.pop("performance_metrics_cache", None)
    if sort in METRIC_SORTS:
        items = sort_rows(items, sort, direction)[(page - 1) * page_size : page * page_size]
    return {
        "items": items,
        "summary": summary,
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


@performance_budget.bounded
async def team_detail(
    session: AsyncSession,
    actor: Actor,
    team_id: UUID,
    filters: PerformanceFilters,
    *,
    page: int,
    page_size: int,
    sort: str | None = None,
    direction: str = "asc",
) -> dict:
    if sort not in {None, "employeeName", *METRIC_SORTS} or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    scoped = filters.model_copy(update={"teamId": team_id})
    scope = await resolve(session, actor, scoped)
    team = (
        (await session.execute(select(teams).where(teams.c.id == team_id))).mappings().one_or_none()
    )
    if team is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if actor.designation == "Sales Manager" and (
        team["branch_id"] != actor.branch_id or team["department_id"] != actor.department_id
    ):
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if actor.designation == "Team Leader" and scope.team_id != team_id:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if actor.designation not in MANAGEMENT_ROLES | {"Sales Manager", "Team Leader"}:
        raise ApiError(403, "FORBIDDEN", "Access denied")
    member_ids = set(
        (
            await session.scalars(
                select(team_memberships.c.employee_id).where(
                    team_memberships.c.team_id == team_id,
                )
            )
        ).all()
    )
    leader_ids = set(
        (
            await session.scalars(
                select(team_leader_history.c.leader_employee_id).where(
                    team_leader_history.c.team_id == team_id,
                )
            )
        ).all()
    )
    ids = sorted(member_ids | leader_ids, key=str)
    visible = set(await filtered_employee_ids(session, scope, scoped))
    ids = [employee_id for employee_id in ids if employee_id in visible]
    rows = (
        (
            await session.execute(
                select(employees)
                .where(uuid_set(employees.c.id, ids))
                .order_by(
                    (employees.c.full_name if sort else employees.c.id).asc()
                    if direction == "asc"
                    else (employees.c.full_name if sort else employees.c.id).desc(),
                    employees.c.id,
                )
            )
        )
        .mappings()
        .all()
    )
    performance_budget.preflight(rows, scoped, session=session, scope=scope)
    await preload(session, [dict(row) for row in rows], filters)
    all_metrics = [await derive_with_denominator(session, scope, dict(row), scoped) for row in rows]
    items = [item for item, _ in all_metrics]
    if sort in METRIC_SORTS:
        items = sort_rows(items, sort, direction)
    items = items[(page - 1) * page_size : page * page_size]
    return {
        "teamId": str(team_id),
        "items": items,
        "summary": summarize(all_metrics),
        "total": len(ids),
        "page": page,
        "pageSize": page_size,
    }


@performance_budget.bounded
async def comparison(
    session: AsyncSession,
    actor: Actor,
    filters: PerformanceFilters,
    *,
    group_by: str,
    page: int,
    page_size: int,
    sort: str | None = None,
    direction: str = "asc",
) -> dict:
    if sort not in {None, "name", *METRIC_SORTS} or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    scope = await resolve(session, actor, filters)
    if actor.designation not in MANAGEMENT_ROLES | {"Sales Manager"}:
        raise ApiError(403, "FORBIDDEN", "Access denied")
    if group_by not in {"branch", "department"}:
        raise ApiError(422, "INVALID_GROUP", "Comparison group is invalid")
    if filters.productCode is None:
        raise ApiError(422, "PRODUCT_REQUIRED", "Product context is required")
    from app.db.organization import branches, departments

    if group_by == "branch":
        query = select(branches.c.id, branches.c.name).order_by(branches.c.name, branches.c.id)
        if actor.designation == "Sales Manager":
            query = query.where(branches.c.id == actor.branch_id)
        if filters.branchId is not None:
            query = query.where(branches.c.id == filters.branchId)
    else:
        query = select(departments.c.id, departments.c.name).order_by(
            departments.c.name,
            departments.c.id,
        )
        if actor.designation == "Sales Manager":
            query = query.where(departments.c.id == actor.department_id)
        if filters.departmentId is not None:
            query = query.where(departments.c.id == filters.departmentId)
        if filters.branchId is not None:
            query = query.where(departments.c.branch_id == filters.branchId)
    # Product variants of one bounded read reuse the same group and row results;
    # the cache is dropped when that read ends.
    cache = session.info.get("performance_comparison_cache")
    groups_key = (
        group_by,
        actor.designation == "Sales Manager",
        actor.branch_id,
        actor.department_id,
        filters.branchId,
        filters.departmentId,
    )
    if cache is not None and groups_key in cache:
        groups = list(cache[groups_key])
    else:
        groups = list((await session.execute(query)).all())
        if cache is not None:
            cache[groups_key] = tuple(groups)
    if sort and direction == "desc":
        groups = list(reversed(groups))
    items = []
    plans = []
    for group_id, name in groups:
        group_filters = filters.model_copy(
            update={
                "branchId" if group_by == "branch" else "departmentId": group_id,
            }
        )
        employee_ids = await filtered_employee_ids(session, scope, group_filters)
        rows_key = ("rows", frozenset(employee_ids))
        if cache is not None and rows_key in cache:
            employee_rows = cache[rows_key]
        else:
            employee_rows = tuple(
                (
                    await session.execute(
                        select(employees).where(uuid_set(employees.c.id, employee_ids))
                    )
                )
                .mappings()
                .all()
            )
            if cache is not None:
                cache[rows_key] = employee_rows
        plans.append((group_id, name, group_filters, employee_rows))
    performance_budget.check(
        sum(
            performance_budget.planned_cost(rows, scoped, session=session, scope=scope)
            for _, _, scoped, rows in plans
        )
    )
    for group_id, name, group_filters, employee_rows in plans:
        await preload(session, [dict(row) for row in employee_rows], group_filters)
        metrics = [
            await derive_with_denominator(session, scope, dict(employee), group_filters)
            for employee in employee_rows
        ]
        items.append({"id": str(group_id), "name": name, **summarize(metrics)})
    if sort in METRIC_SORTS:
        items = sort_rows(items, sort, direction, identity="id")
    return {
        "groupBy": group_by,
        "items": items[(page - 1) * page_size : page * page_size],
        "total": len(groups),
        "page": page,
        "pageSize": page_size,
    }
