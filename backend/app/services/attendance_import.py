"""Atomic, bounded Attendance import with retained outcomes and uploader notice."""

import hashlib
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.attendance import attendance_records, csv_import_batches, csv_import_row_results
from app.db.base import utcnow
from app.db.operations import notifications
from app.db.organization import branches
from app.errors import ApiError
from app.policies import Actor
from app.services import attendance_csv, attendance_scope, office_timings
from app.services.idempotency import claim, complete
from app.services.operations_scope import required_branch


async def _results(
    session: AsyncSession,
    batch_id: UUID,
    rows: list[attendance_csv.ParsedRow],
    errors: list[dict],
    applied: bool,
) -> None:
    failures: dict[int, dict] = {}
    for error in errors:
        failures.setdefault(error["rowNumber"], error)
    for number in sorted({row.number for row in rows} | set(failures)):
        failure = failures.get(number)
        await session.execute(
            csv_import_row_results.insert().values(
                id=uuid4(),
                batch_id=batch_id,
                row_number=number,
                status="Applied" if applied else ("Rejected" if failure else "Skipped"),
                error_code=failure["code"] if failure else None,
                error_detail=failure["message"] if failure else None,
                column_name=failure["column"] if failure else None,
            )
        )


async def import_attendance(
    session: AsyncSession,
    actor: Actor,
    *,
    branch_id: UUID | None,
    content: bytes,
    content_hash: str,
    byte_size: int,
    too_large: bool,
    key: str,
) -> dict:
    selected_branch = required_branch(actor, "attendance.write", branch_id)
    try:
        record_id, replay = await claim(
            session,
            actor,
            "attendance.csv",
            key,
            {"branchId": str(selected_branch), "sha256": content_hash},
        )
        if replay is not None:
            await session.rollback()
            return replay
        branch = await session.scalar(
            select(branches.c.id).where(branches.c.id == selected_branch, branches.c.active)
        )
        if branch is None:
            raise ApiError(422, "BRANCH_UNAVAILABLE", "Branch unavailable")
        if too_large or byte_size > attendance_csv.MAX_CSV_BYTES:
            rows: list[attendance_csv.ParsedRow] = []
            errors = [
                {
                    "rowNumber": 1,
                    "column": None,
                    "code": "CSV_SIZE_LIMIT",
                    "message": "CSV exceeds 5,000,000 bytes",
                }
            ]
            count = 0
            on_date = None
        else:
            rows, errors, count, on_date = attendance_csv.parse(content)
        timing = None
        population: list[dict] = []
        if on_date is not None:
            lock_key = int.from_bytes(
                hashlib.blake2b(
                    f"attendance:{selected_branch}:{on_date}".encode(), digest_size=8
                ).digest(),
                "big",
                signed=True,
            )
            await session.execute(select(func.pg_advisory_xact_lock(lock_key)))
            existing = await session.scalar(
                select(csv_import_batches.c.id).where(
                    csv_import_batches.c.kind == "attendance",
                    csv_import_batches.c.branch_id == selected_branch,
                    csv_import_batches.c.attendance_date == on_date,
                    csv_import_batches.c.status == "Applied",
                )
            )
            if existing is not None:
                errors.append(
                    {
                        "rowNumber": 1,
                        "column": "Attendance Date",
                        "code": "ATTENDANCE_DATE_ALREADY_APPLIED",
                        "message": "Attendance for this Branch and date is already applied",
                    }
                )
            timing = await office_timings.effective(session, selected_branch, on_date)
            if timing is None:
                errors.append(
                    {
                        "rowNumber": 1,
                        "column": "Attendance Date",
                        "code": "OFFICE_TIMING_MISSING",
                        "message": "No effective Office Timing for this Branch and date",
                    }
                )
            population = await attendance_scope.eligible_employees(
                session, selected_branch, on_date
            )
            by_code = {employee["system_employee_code"]: employee for employee in population}
            for row in rows:
                if row.code not in by_code:
                    errors.append(
                        {
                            "rowNumber": row.number,
                            "column": "System Employee Code",
                            "code": "EMPLOYEE_UNAVAILABLE",
                            "message": "Employee Code unavailable for this Branch and date",
                        }
                    )
        if any(error["code"] in {"CSV_SIZE_LIMIT", "CSV_ROW_LIMIT"} for error in errors):
            # Limits take priority and no business record can be applied.
            timing = None
        valid = not errors
        by_code = {employee["system_employee_code"]: employee for employee in population}
        submitted = {row.code for row in rows}
        present = len(rows) if valid else 0
        absent = len(population) - len(submitted) if valid else 0
        late = sum(row.check_in > timing["start_time"] for row in rows) if valid and timing else 0
        batch_id = uuid4()
        await session.execute(
            csv_import_batches.insert().values(
                id=batch_id,
                kind="attendance",
                uploaded_by_employee_id=actor.employee_id,
                branch_id=selected_branch,
                attendance_date=on_date,
                status="Applied" if valid else "Rejected",
                content_hash=content_hash,
                byte_size=byte_size,
                data_row_count=count,
                applied_count=present + absent if valid else 0,
                error_count=len(errors),
                created_at=utcnow(),
            )
        )
        await _results(session, batch_id, rows, errors, valid)
        if valid and on_date is not None and timing is not None:
            for row in rows:
                employee = by_code[row.code]
                await session.execute(
                    attendance_records.insert().values(
                        id=uuid4(),
                        employee_id=employee["id"],
                        branch_id=selected_branch,
                        attendance_date=on_date,
                        check_in_time=row.check_in,
                        check_out_time=row.check_out,
                        status="Present",
                        is_late=row.check_in > timing["start_time"],
                        office_timing_id=timing["id"],
                        csv_import_batch_id=batch_id,
                    )
                )
            for employee in population:
                if employee["system_employee_code"] not in submitted:
                    await session.execute(
                        attendance_records.insert().values(
                            id=uuid4(),
                            employee_id=employee["id"],
                            branch_id=selected_branch,
                            attendance_date=on_date,
                            status="Absent",
                            is_late=False,
                            office_timing_id=timing["id"],
                            csv_import_batch_id=batch_id,
                        )
                    )
        await session.execute(
            notifications.insert().values(
                id=uuid4(),
                recipient_employee_id=actor.employee_id,
                kind="attendance.upload_result",
                message=(
                    f"Attendance upload applied: {present} Present, {absent} Absent, {late} Late"
                    if valid
                    else f"Attendance upload rejected: {len(errors)} validation error(s)"
                ),
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="attendance.csv_imported",
            module="attendance",
            entity_type="csv_import_batch",
            entity_id=batch_id,
            after={
                "status": "Applied" if valid else "Rejected",
                "branchId": str(selected_branch),
                "attendanceDate": on_date.isoformat() if on_date else None,
                "contentHash": content_hash,
                "byteSize": byte_size,
                "rowCount": count,
                "presentCount": present,
                "absentCount": absent,
                "lateCount": late,
                "errorCount": len(errors),
                "errorCodes": sorted({error["code"] for error in errors}),
            },
        )
        result = {
            "batchId": str(batch_id),
            "branchId": str(selected_branch),
            "attendanceDate": on_date.isoformat() if on_date else None,
            "status": "Applied" if valid else "Rejected",
            "presentCount": present,
            "absentCount": absent,
            "lateCount": late,
            "appliedCount": present + absent if valid else 0,
            "errors": errors,
        }
        await complete(session, record_id, 200, result)
        await session.commit()
        return result
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(409, "ATTENDANCE_CONFLICT", "Attendance upload conflicts") from exc
    except Exception:
        await session.rollback()
        raise
