"""Request-local engineering bounds; reject work rather than truncate history."""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date, datetime
from functools import wraps

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.services.performance_math import DUBAI

MAX_SPAN_DAYS = 36_600
MAX_DAY_WORK = 1_000_000
MAX_MONTHLY_CALLS = 240


@dataclass
class Budget:
    days: int = 0


_current: ContextVar[Budget | None] = ContextVar("performance_work_budget", default=None)


def bounded[**P, T](function: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    @wraps(function)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        token = _current.set(Budget()) if _current.get() is None else None
        session = args[0] if args else kwargs.get("session")
        owned_caches = []
        if isinstance(session, AsyncSession):
            for name in (
                "performance_records_cache",
                "performance_metrics_cache",
                "holiday_calendar_cache",
                "performance_population_cache",
                "performance_employee_rows_cache",
                "performance_visible_ids_cache",
                "performance_comparison_cache",
            ):
                if name not in session.info:
                    session.info[name] = {}
                    owned_caches.append(name)
        try:
            return await function(*args, **kwargs)
        finally:
            if isinstance(session, AsyncSession):
                for name in owned_caches:
                    session.info.pop(name, None)
            if token is not None:
                _current.reset(token)

    return wrapped


def reject() -> None:
    raise ApiError(
        422,
        "PERFORMANCE_WORK_LIMIT",
        "Requested history exceeds the calculation limit. Select a smaller period or scope.",
    )


def span(start: date, end: date) -> int:
    days = (end - start).days + 1
    if days < 1:
        raise ApiError(422, "PERFORMANCE_DATE_INVALID", "Date range is unavailable")
    if days > MAX_SPAN_DAYS:
        reject()
    return days


def cost(employee, filters) -> int:
    start = filters.startDate or employee["date_of_joining"]
    end = filters.endDate or datetime.now(DUBAI).date()
    return span(start, end) * (1 if filters.productCode else 2)


def check(units: int) -> None:
    budget = _current.get()
    if units + (budget.days if budget else 0) > MAX_DAY_WORK:
        reject()


def metric_key(scope, employee_id, filters) -> tuple:
    return (
        scope.actor.employee_id,
        scope.actor.designation,
        scope.actor.branch_id,
        scope.actor.department_id,
        scope.team_id,
        scope.finance_report,
        employee_id,
        type(filters),
        tuple(filters.__dict__.items()),
    )


def planned_cost(rows, filters, *, session=None, scope=None) -> int:
    cache = session.info.get("performance_metrics_cache", {}) if session is not None else {}
    return sum(
        cost(row, filters)
        for row in rows
        if scope is None or metric_key(scope, row["id"], filters) not in cache
    )


def preflight(rows, filters, *, multiplier: int = 1, session=None, scope=None) -> None:
    check(planned_cost(rows, filters, session=session, scope=scope) * multiplier)


def charge(units: int) -> None:
    check(units)
    budget = _current.get()
    if budget is not None:
        budget.days += units


def monthly(start: date, end: date, product_count: int, population: int = 1) -> None:
    days = span(start, end)
    months = (end.year - start.year) * 12 + end.month - start.month + 1
    if months * product_count * max(1, population) > MAX_MONTHLY_CALLS:
        reject()
    check(days * product_count * population)
