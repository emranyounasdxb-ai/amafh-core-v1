"""Branch-scoped Attendance template, detail, lists and report totals."""

import csv
import io
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.attendance import (
    attendance_records,
    csv_import_batches,
    csv_import_row_results,
    office_timings,
)
from app.db.organization import designations, employees
from app.errors import ApiError
from app.policies import Actor, employee_visible
from app.services.attendance_csv import HEADERS
from app.services.attendance_scope import eligible_employees
from app.services.operations_scope import branch_scope, required_branch
from app.services.performance_math import DUBAI
from app.whole_numbers import round_whole


def _safe_cell(value: str) -> str:
    return f"'{value}" if value and value[0] in "=+-@\t\r\n" else value


async def template(
    session: AsyncSession, actor: Actor, branch_id: UUID | None, on_date: date
) -> str:
    branch = required_branch(actor, "attendance.write", branch_id)
    population = await eligible_employees(session, branch, on_date)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(HEADERS)
    for employee in population:
        writer.writerow(
            (
                employee["system_employee_code"],
                _safe_cell(employee["full_name"]),
                on_date.isoformat(),
                "",
                "",
            )
        )
    return output.getvalue()


def _query(
    actor: Actor,
    *,
    branch_id: UUID | None,
    employee_id: UUID | None,
    date_from: date | None,
    date_to: date | None,
    status: str | None,
    is_late: bool | None,
    search: str | None,
):
    scope = branch_scope(actor, "attendance.write", branch_id)
    query = (
        select(
            *attendance_records.c,
            employees.c.system_employee_code,
            employees.c.full_name,
            office_timings.c.start_time.label("office_start_time"),
            office_timings.c.end_time.label("office_end_time"),
            csv_import_batches.c.created_at.label("imported_at"),
        )
        .join(employees, employees.c.id == attendance_records.c.employee_id)
        .outerjoin(office_timings, office_timings.c.id == attendance_records.c.office_timing_id)
        .outerjoin(
            csv_import_batches,
            csv_import_batches.c.id == attendance_records.c.csv_import_batch_id,
        )
    )
    if scope is not None:
        query = query.where(attendance_records.c.branch_id == scope)
    if employee_id is not None:
        query = query.where(attendance_records.c.employee_id == employee_id)
    if date_from is not None:
        query = query.where(attendance_records.c.attendance_date >= date_from)
    if date_to is not None:
        query = query.where(attendance_records.c.attendance_date <= date_to)
    if status is not None:
        query = query.where(attendance_records.c.status == status)
    if is_late is not None:
        query = query.where(attendance_records.c.is_late == is_late)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(employees.c.system_employee_code.ilike(term), employees.c.full_name.ilike(term))
        )
    return query


def _minutes(start: time | None, end: time | None) -> int | None:
    if start is None or end is None or end <= start:
        return None
    day = date(2000, 1, 1)
    return int((datetime.combine(day, end) - datetime.combine(day, start)).total_seconds() // 60)


def _public(row) -> dict:
    office_start = row["office_start_time"]
    return {
        "id": row["id"],
        "employeeId": row["employee_id"],
        "systemEmployeeCode": row["system_employee_code"],
        "employeeName": row["full_name"],
        "branchId": row["branch_id"],
        "attendanceDate": row["attendance_date"],
        "checkInTime": row["check_in_time"],
        "checkOutTime": row["check_out_time"],
        "status": row["status"],
        "isLate": row["is_late"],
        "csvImportBatchId": row["csv_import_batch_id"],
        "importedAt": row["imported_at"],
        "officeStartTime": office_start,
        "officeEndTime": row["office_end_time"],
        "workedMinutes": _minutes(row["check_in_time"], row["check_out_time"]),
        "requiredMinutes": _minutes(office_start, row["office_end_time"]),
        "lateMinutes": _minutes(office_start, row["check_in_time"]) if row["is_late"] else None,
    }


def _sunday_off_count(start: date, end: date, recorded: set[date]) -> int:
    end = min(end, datetime.now(DUBAI).date())
    count = 0
    day = start
    while day <= end:
        if day.weekday() == 6 and day not in recorded:
            count += 1
        day += timedelta(days=1)
    return count


async def list_records(
    session: AsyncSession,
    actor: Actor,
    *,
    branch_id: UUID | None,
    employee_id: UUID | None,
    date_from: date | None,
    date_to: date | None,
    status: str | None,
    is_late: bool | None,
    search: str | None,
    page: int,
    page_size: int,
    sort: str,
    direction: str,
) -> dict:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ApiError(422, "DATE_RANGE_INVALID", "Start Date must not follow End Date")
    order = {
        "attendanceDate": attendance_records.c.attendance_date,
        "branchId": attendance_records.c.branch_id,
        "employeeCode": employees.c.system_employee_code,
        "systemEmployeeCode": employees.c.system_employee_code,
        "employeeName": employees.c.full_name,
        "checkInTime": attendance_records.c.check_in_time,
        "checkOutTime": attendance_records.c.check_out_time,
        "status": attendance_records.c.status,
        "isLate": attendance_records.c.is_late,
    }.get(sort)
    if order is None or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    query = _query(
        actor,
        branch_id=branch_id,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
        is_late=is_late,
        search=search,
    )
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    counts: dict[str, int | None] = {}
    for label, predicate in (
        ("presentCount", attendance_records.c.status == "Present"),
        ("absentCount", attendance_records.c.status == "Absent"),
        ("lateCount", attendance_records.c.is_late.is_(True)),
    ):
        counts[label] = (
            await session.scalar(
                select(func.count()).select_from(query.where(predicate).subquery())
            )
            or 0
        )
    filtered = query.subquery()
    worked_days, worked_seconds = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(
                    func.sum(
                        func.extract("epoch", filtered.c.check_out_time - filtered.c.check_in_time)
                    ),
                    0,
                ),
            ).where(
                filtered.c.check_in_time.is_not(None),
                filtered.c.check_out_time.is_not(None),
                filtered.c.check_out_time > filtered.c.check_in_time,
            )
        )
    ).one()
    worked_minutes = int(worked_seconds // 60)
    counts["workedMinutes"] = worked_minutes
    counts["averageWorkedMinutes"] = (
        int(round_whole(Decimal(worked_minutes) / worked_days)) if worked_days else None
    )
    counts["sundayOffCount"] = None
    if (
        employee_id is not None
        and date_from is not None
        and date_to is not None
        and status is None
        and is_late is None
    ):
        recorded = set((await session.scalars(select(filtered.c.attendance_date))).all())
        counts["sundayOffCount"] = _sunday_off_count(date_from, date_to, recorded)
    rows = (
        (
            await session.execute(
                query.order_by(
                    (order.asc() if direction == "asc" else order.desc()).nulls_last(),
                    attendance_records.c.id,
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    return {
        "items": [_public(row) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
        **counts,
    }


async def employee_choices(session: AsyncSession, actor: Actor, branch_id: UUID | None) -> dict:
    scope = branch_scope(actor, "attendance.write", branch_id)
    recorded = select(attendance_records.c.employee_id).distinct()
    if scope is not None:
        recorded = recorded.where(attendance_records.c.branch_id == scope)
    rows = (
        (
            await session.execute(
                select(
                    employees.c.id,
                    employees.c.full_name,
                    employees.c.system_employee_code,
                    employees.c.company_employee_code,
                    employees.c.branch_id,
                    employees.c.department_id,
                    employees.c.avatar_file_id,
                    designations.c.name.label("designation"),
                )
                .outerjoin(designations, designations.c.id == employees.c.designation_id)
                .where(employees.c.id.in_(recorded))
                .order_by(employees.c.full_name, employees.c.id)
            )
        )
        .mappings()
        .all()
    )
    return {
        "items": [
            {
                "id": row["id"],
                "fullName": row["full_name"],
                "systemEmployeeCode": row["system_employee_code"],
                "companyEmployeeCode": row["company_employee_code"],
                "designation": row["designation"],
                "avatarFileId": (
                    row["avatar_file_id"] if employee_visible(actor, dict(row)) else None
                ),
            }
            for row in rows
        ]
    }


async def detail(session: AsyncSession, actor: Actor, record_id: UUID) -> dict:
    query = _query(
        actor,
        branch_id=None,
        employee_id=None,
        date_from=None,
        date_to=None,
        status=None,
        is_late=None,
        search=None,
    )
    row = (
        (await session.execute(query.where(attendance_records.c.id == record_id)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return _public(row)


async def import_detail(session: AsyncSession, actor: Actor, batch_id: UUID) -> dict:
    branch = branch_scope(actor, "attendance.write")
    query = select(csv_import_batches).where(
        csv_import_batches.c.id == batch_id,
        csv_import_batches.c.kind == "attendance",
    )
    if branch is not None:
        query = query.where(csv_import_batches.c.branch_id == branch)
    row = (await session.execute(query)).mappings().one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return _import_public(row)


def _import_public(row) -> dict:
    return {
        "batchId": row["id"],
        "branchId": row["branch_id"],
        "attendanceDate": row["attendance_date"],
        "status": row["status"],
        "dataRowCount": row["data_row_count"],
        "appliedCount": row["applied_count"],
        "errorCount": row["error_count"],
        "createdAt": row["created_at"],
    }


async def list_imports(
    session: AsyncSession,
    actor: Actor,
    *,
    branch_id: UUID | None,
    status: str | None,
    page: int,
    page_size: int,
    sort: str = "createdAt",
    direction: str = "desc",
) -> dict:
    order = {
        "batchId": csv_import_batches.c.id,
        "attendanceDate": csv_import_batches.c.attendance_date,
        "status": csv_import_batches.c.status,
        "dataRowCount": csv_import_batches.c.data_row_count,
        "errorCount": csv_import_batches.c.error_count,
        "createdAt": csv_import_batches.c.created_at,
    }.get(sort)
    if order is None or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    branch = branch_scope(actor, "attendance.write", branch_id)
    conditions = [csv_import_batches.c.kind == "attendance"]
    if branch is not None:
        conditions.append(csv_import_batches.c.branch_id == branch)
    if status is not None:
        conditions.append(csv_import_batches.c.status == status)
    total = (
        await session.scalar(
            select(func.count()).select_from(csv_import_batches).where(*conditions)
        )
        or 0
    )
    rows = (
        (
            await session.execute(
                select(csv_import_batches)
                .where(*conditions)
                .order_by(
                    order.asc() if direction == "asc" else order.desc(),
                    csv_import_batches.c.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    return {
        "items": [_import_public(row) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


async def import_rows(
    session: AsyncSession,
    actor: Actor,
    batch_id: UUID,
    *,
    page: int,
    page_size: int,
    sort: str = "rowNumber",
    direction: str = "asc",
) -> dict:
    order = {
        "rowNumber": csv_import_row_results.c.row_number,
        "status": csv_import_row_results.c.status,
        "errorCode": csv_import_row_results.c.error_code,
        "columnName": csv_import_row_results.c.column_name,
        "errorDetail": csv_import_row_results.c.error_detail,
    }.get(sort)
    if order is None or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    await import_detail(session, actor, batch_id)
    condition = csv_import_row_results.c.batch_id == batch_id
    total = (
        await session.scalar(
            select(func.count()).select_from(csv_import_row_results).where(condition)
        )
        or 0
    )
    rows = (
        (
            await session.execute(
                select(csv_import_row_results)
                .where(condition)
                .order_by(
                    (order.asc() if direction == "asc" else order.desc()).nulls_last(),
                    csv_import_row_results.c.id,
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    return {
        "batchId": batch_id,
        "items": [
            {
                "rowNumber": row["row_number"],
                "status": row["status"],
                "errorCode": row["error_code"],
                "errorDetail": row["error_detail"],
                "columnName": row["column_name"],
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }
