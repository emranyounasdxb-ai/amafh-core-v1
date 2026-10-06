"""Allowlisted source paths, filters, and sorts for table CSV reads."""

import re
from datetime import date, datetime
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl
from uuid import UUID

from app.errors import ApiError

if TYPE_CHECKING:
    from app.services.table_export_spec import TableSpec

UUID_KEYS = frozenset(
    "branchId departmentId teamId bankId productTypeId ownerEmployeeId employeeId "
    "assigneeId actorId caseId designationId entityId reportingManagerId".split()
)
DATE_KEYS = frozenset(
    "startDate endDate createdFrom createdTo completedFrom completedTo dateFrom dateTo "
    "paymentFrom paymentTo".split()
)
DATETIME_KEYS = frozenset("dueFrom dueTo fromTime toTime".split())
ENUMS = {
    "period": frozenset("today week month year custom".split()),
    "productCode": frozenset({"CC", "PF"}),
    "groupBy": frozenset({"branch", "department"}),
    "paymentType": frozenset({"Salary", "Commission"}),
    "priority": frozenset({"Low", "Normal", "High", "Urgent"}),
    "type": frozenset({"Individual", "Company"}),
    "customerType": frozenset({"Individual", "Company"}),
    "accessStatus": frozenset({"Not Provisioned", "Active", "Disabled"}),
    "active": frozenset({"true", "false"}),
    "isLate": frozenset({"true", "false"}),
}
STATUS = {
    "cases": frozenset(
        {
            "Pending for Approval",
            "Approved",
            "Booked",
            "Completed",
            "Rejected",
            "Case Reopened by Owner",
        }
    ),
    "customers": frozenset({"Individual", "Company"}),
    "employees": frozenset({"Pending Setup", "Active", "Offboarded"}),
    "attendance": frozenset({"Present", "Absent"}),
    "attendance-imports": frozenset({"Applied", "Rejected"}),
    "assets": frozenset({"Available", "Issued", "Needs Maintenance", "Maintenance", "Damaged"}),
    "tasks": frozenset({"Open", "In Progress", "Completed", "Cancelled"}),
    "report-case-pipeline": frozenset(
        {
            "Pending for Approval",
            "Approved",
            "Booked",
            "Completed",
            "Rejected",
            "Case Reopened by Owner",
        }
    ),
    "report-attendance": frozenset({"Present", "Absent"}),
    "report-assets": frozenset(
        {"Available", "Issued", "Needs Maintenance", "Maintenance", "Damaged"}
    ),
    "report-hr-employees": frozenset({"Pending Setup", "Active", "Offboarded"}),
    "report-hr-assignments": frozenset({"Pending Setup", "Active", "Offboarded"}),
}
VIEWS = {
    "cases": frozenset({"active", "archived", "all"}),
    "tasks": frozenset(
        {"active", "assigned", "created", "management", "overdue", "history", "archived"}
    ),
}
SORTS = {
    "cases": frozenset(
        "createdAt updatedAt internalCaseId customerName productName bankName "
        "variantOrPfAmount createdByName ownerName branchName status "
        "bankCaseNumber currentStage".split()
    ),
    "case-approvals": frozenset(
        "createdAt updatedAt internalCaseId customerName productName bankName "
        "variantOrPfAmount createdByName ownerName branchName status "
        "bankCaseNumber currentStage".split()
    ),
    "customers": frozenset(
        "customerId type name nationality contactPerson mobile email "
        "passportNumber eidOrTl createdAt".split()
    ),
    "employees": frozenset("fullName companyEmployeeCode designation status".split()),
    "teams": frozenset("name active branchName departmentName".split()),
    "finance-completed": frozenset(
        "internalCaseId productCode completedAt ccPoints commissionAed".split()
    ),
    "finance-wallets": frozenset("employeeName balancePoints".split()),
    "finance-clawbacks": frozenset("internalCaseId amountAed clawbackDate reason".split()),
    "finance-payments": frozenset(
        "employeeName paymentType amountAed paymentMonth paymentDate".split()
    ),
    "finance-rules": frozenset("id effectiveDate ccPoints commissionAed active".split()),
    "targets": frozenset("effectiveDate targetPoints targetAmountAed active".split()),
    "performance-employees": frozenset(
        "employeeName createdCaseCount bookedCaseCount completedCaseCount "
        "achievedCCPoints achievedPFAed targetProgress".split()
    ),
    "performance-team": frozenset(
        "employeeName createdCaseCount bookedCaseCount completedCaseCount "
        "achievedCCPoints achievedPFAed targetProgress".split()
    ),
    "performance-comparisons": frozenset(
        "name createdCaseCount bookedCaseCount completedCaseCount "
        "achievedCCPoints achievedPFAed targetProgress".split()
    ),
    "performance-rankings": frozenset(
        "rank employeeName achievementPercentage completedCaseCount".split()
    ),
    "coordinator-workload": frozenset(
        "employeeName handledCases submittedBookedCases stageUpdatedCases".split()
    ),
    "attendance": frozenset(
        "attendanceDate employeeCode systemEmployeeCode employeeName checkInTime "
        "checkOutTime status isLate branchId".split()
    ),
    "attendance-imports": frozenset(
        "batchId attendanceDate status dataRowCount errorCount createdAt".split()
    ),
    "attendance-import-rows": frozenset(
        "rowNumber status errorCode columnName errorDetail".split()
    ),
    "assets": frozenset(
        "createdAt assetCode category brand model serialNumber branchId "
        "currentEmployeeId status".split()
    ),
    "tasks": frozenset("title dueAt createdAt status priority isOverdue".split()),
    "audit": frozenset("occurredAt action module entityType actorEmployeeId".split()),
    "catalog-banks": frozenset("name code createdAt active".split()),
    "catalog-products": frozenset("name code createdAt active".split()),
    "catalog-mappings": frozenset("name code createdAt active bankId productTypeId".split()),
    "catalog-variants": frozenset("name code createdAt active".split()),
    "pipelines": frozenset("id effectiveDate active".split()),
    "office-timings": frozenset("effectiveDate branchId startTime endTime".split()),
    "uae-holidays": frozenset("holidayDate name sourceReference".split()),
}


def _invalid() -> ApiError:
    return ApiError(422, "TABLE_EXPORT_FILTER_INVALID", "Table filters are unavailable")


def _valid_value(spec: TableSpec, key: str, value: str) -> bool:
    if not value:
        return key not in {"period", "groupBy", "sort", "direction"}
    if key in UUID_KEYS:
        try:
            return str(UUID(value)) == value
        except ValueError:
            return False
    if key in DATE_KEYS:
        try:
            return bool(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value)) and bool(
                date.fromisoformat(value)
            )
        except ValueError:
            return False
    if key in DATETIME_KEYS:
        try:
            return (
                len(value) <= 40
                and datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
            )
        except ValueError:
            return False
    if key == "status":
        return value in STATUS.get(spec.name, frozenset())
    if key == "view":
        return value in VIEWS.get(spec.name, frozenset())
    if key == "sort":
        permitted = spec.fields if spec.name.startswith("report-") else SORTS.get(spec.name, ())
        return value in permitted
    if key == "direction":
        return value in {"asc", "desc"}
    if key == "year":
        return bool(re.fullmatch(r"[0-9]{1,4}", value)) and 1 <= int(value) <= 9999
    if key in ENUMS:
        return value in ENUMS[key]
    limit = 100 if key == "search" else 80 if key == "category" else 128
    return len(value) <= limit and not any(ord(char) < 32 for char in value)


def validate_query(spec: TableSpec, query: str) -> list[tuple[str, str]]:
    if re.search(r"%(?![0-9a-fA-F]{2})", query):
        raise _invalid()
    try:
        pairs = parse_qsl(query, keep_blank_values=True, max_num_fields=16, errors="strict")
    except (ValueError, UnicodeDecodeError) as error:
        raise _invalid() from error
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)) or set(keys) - (spec.filters | {"sort", "direction"}):
        raise _invalid()
    if any(
        len(key) > 32 or len(value) > 128 or not _valid_value(spec, key, value)
        for key, value in pairs
    ):
        raise _invalid()
    return pairs
