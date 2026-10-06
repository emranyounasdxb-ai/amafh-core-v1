"""Typed Office Timing and Attendance API contracts."""

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OfficeTimingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branchId: UUID
    effectiveDate: date
    startTime: time
    endTime: time

    @model_validator(mode="after")
    def ordered_times(self) -> OfficeTimingInput:
        if self.endTime <= self.startTime:
            raise ValueError("End time must be later than start time")
        return self


class OfficeTimingResponse(BaseModel):
    id: UUID
    branchId: UUID
    effectiveDate: date
    startTime: time
    endTime: time
    createdByEmployeeId: UUID | None


class OfficeTimingPage(BaseModel):
    items: list[OfficeTimingResponse]
    total: int
    page: int
    pageSize: int


class AttendanceError(BaseModel):
    rowNumber: int
    column: str | None = None
    code: str
    message: str


class AttendanceImportResponse(BaseModel):
    batchId: UUID
    branchId: UUID
    attendanceDate: date | None
    status: str
    presentCount: int
    absentCount: int
    lateCount: int
    appliedCount: int
    errors: list[AttendanceError]


class AttendanceImportDetail(BaseModel):
    batchId: UUID
    branchId: UUID | None
    attendanceDate: date | None
    status: str
    dataRowCount: int | None
    appliedCount: int | None
    errorCount: int | None
    createdAt: datetime


class AttendanceImportPage(BaseModel):
    items: list[AttendanceImportDetail]
    total: int
    page: int
    pageSize: int


class AttendanceImportRow(BaseModel):
    rowNumber: int
    status: str
    errorCode: str | None
    errorDetail: str | None
    columnName: str | None


class AttendanceImportRowPage(BaseModel):
    batchId: UUID
    items: list[AttendanceImportRow]
    total: int
    page: int
    pageSize: int


class AttendanceRecordResponse(BaseModel):
    id: UUID
    employeeId: UUID
    systemEmployeeCode: str
    employeeName: str
    branchId: UUID
    attendanceDate: date
    checkInTime: time | None
    checkOutTime: time | None
    status: str
    isLate: bool
    csvImportBatchId: UUID | None
    importedAt: datetime | None = None
    officeStartTime: time | None = None
    officeEndTime: time | None = None
    workedMinutes: int | None = None
    requiredMinutes: int | None = None
    lateMinutes: int | None = None


class AttendancePage(BaseModel):
    items: list[AttendanceRecordResponse]
    total: int
    page: int
    pageSize: int
    presentCount: int
    absentCount: int
    lateCount: int
    workedMinutes: int = 0
    averageWorkedMinutes: int | None = None
    sundayOffCount: int | None = None


class AttendanceEmployeeChoice(BaseModel):
    id: UUID
    fullName: str
    systemEmployeeCode: str
    companyEmployeeCode: str
    designation: str | None
    avatarFileId: UUID | None


class AttendanceEmployeeChoices(BaseModel):
    items: list[AttendanceEmployeeChoice]


class AttendanceReport(BaseModel):
    records: AttendancePage
    dateFrom: date | None
    dateTo: date | None


class AttendanceQuery(BaseModel):
    branchId: UUID | None = None
    employeeId: UUID | None = None
    dateFrom: date | None = None
    dateTo: date | None = None
    status: str | None = None
    search: str | None = Field(default=None, max_length=100)
