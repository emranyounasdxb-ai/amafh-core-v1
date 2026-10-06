"""Authorized Attendance template, atomic CSV upload, and report reads."""

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query, UploadFile
from fastapi.responses import Response

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.schemas.attendance import (
    AttendanceEmployeeChoices,
    AttendanceImportDetail,
    AttendanceImportPage,
    AttendanceImportResponse,
    AttendanceImportRowPage,
    AttendancePage,
    AttendanceRecordResponse,
    AttendanceReport,
)
from app.services import attendance_csv, attendance_import, attendance_reads
from app.services.operations_scope import required_branch

router = APIRouter(tags=["attendance"])


@router.get("/attendance/template")
async def attendance_template(
    db: Db,
    actor: ActorDep,
    attendanceDate: date,
    branchId: UUID | None = None,
):
    content = await attendance_reads.template(db, actor, branchId, attendanceDate)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="attendance-template.csv"'},
    )


@router.post("/attendance/imports", response_model=AttendanceImportResponse)
async def upload_attendance(
    db: Db,
    actor: CsrfActor,
    file: UploadFile,
    branchId: UUID | None = None,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    required_branch(actor, "attendance.write", branchId)
    content, digest, byte_size, too_large = await attendance_csv.read_upload(file)
    return await attendance_import.import_attendance(
        db,
        actor,
        branch_id=branchId,
        content=content,
        content_hash=digest,
        byte_size=byte_size,
        too_large=too_large,
        key=idempotency_key,
    )


@router.get("/attendance/imports/{batch_id}", response_model=AttendanceImportDetail)
async def attendance_import_detail(batch_id: UUID, db: Db, actor: ActorDep):
    return await attendance_reads.import_detail(db, actor, batch_id)


@router.get("/attendance/imports", response_model=AttendanceImportPage)
async def attendance_imports(
    db: Db,
    actor: ActorDep,
    branchId: UUID | None = None,
    status: Literal["Applied", "Rejected"] | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    sort: Literal[
        "batchId", "attendanceDate", "status", "dataRowCount", "errorCount", "createdAt"
    ] = "createdAt",
    direction: Literal["asc", "desc"] = "desc",
):
    return await attendance_reads.list_imports(
        db,
        actor,
        branch_id=branchId,
        status=status,
        page=page,
        page_size=pageSize,
        sort=sort,
        direction=direction,
    )


@router.get("/attendance/imports/{batch_id}/rows", response_model=AttendanceImportRowPage)
async def attendance_import_rows(
    batch_id: UUID,
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    sort: Literal["rowNumber", "status", "errorCode", "columnName", "errorDetail"] = "rowNumber",
    direction: Literal["asc", "desc"] = "asc",
):
    return await attendance_reads.import_rows(
        db, actor, batch_id, page=page, page_size=pageSize, sort=sort, direction=direction
    )


@router.get("/attendance", response_model=AttendancePage)
async def list_attendance(
    db: Db,
    actor: ActorDep,
    branchId: UUID | None = None,
    employeeId: UUID | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    status: Literal["Present", "Absent"] | None = None,
    isLate: bool | None = None,
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    sort: str = "attendanceDate",
    direction: str = "desc",
):
    return await attendance_reads.list_records(
        db,
        actor,
        branch_id=branchId,
        employee_id=employeeId,
        date_from=dateFrom,
        date_to=dateTo,
        status=status,
        is_late=isLate,
        search=search,
        page=page,
        page_size=pageSize,
        sort=sort,
        direction=direction,
    )


@router.get("/attendance/employees", response_model=AttendanceEmployeeChoices)
async def attendance_employees(db: Db, actor: ActorDep, branchId: UUID | None = None):
    return await attendance_reads.employee_choices(db, actor, branchId)


@router.get("/attendance/report", response_model=AttendanceReport)
async def attendance_report(
    db: Db,
    actor: ActorDep,
    branchId: UUID | None = None,
    employeeId: UUID | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
):
    records = await attendance_reads.list_records(
        db,
        actor,
        branch_id=branchId,
        employee_id=employeeId,
        date_from=dateFrom,
        date_to=dateTo,
        status=None,
        is_late=None,
        search=None,
        page=page,
        page_size=pageSize,
        sort="attendanceDate",
        direction="desc",
    )
    return {"records": records, "dateFrom": dateFrom, "dateTo": dateTo}


@router.get("/attendance/{record_id}", response_model=AttendanceRecordResponse)
async def attendance_detail(record_id: UUID, db: Db, actor: ActorDep):
    return await attendance_reads.detail(db, actor, record_id)
