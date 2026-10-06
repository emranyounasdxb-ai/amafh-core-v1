"""Explicit CSV projections for the connected table read surfaces."""

import re
from dataclasses import dataclass, replace
from typing import Literal
from urllib.parse import urlencode, urlsplit

from app.errors import ApiError
from app.services.report_catalog import CATALOG
from app.services.table_export_filters import validate_query

UUID_PATH = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


LookupKind = Literal[
    "employee",
    "employee_code",
    "branch",
    "department",
    "bank",
    "product",
    "variant",
    "present",
    "label",
    "dubai_time",
    "record",
    "business_unit",
    "designation",
    "team",
]


@dataclass(frozen=True)
class ExportColumn:
    heading: str
    source: str
    lookup: LookupKind | None = None


@dataclass(frozen=True)
class TableSpec:
    name: str
    pattern: re.Pattern[str]
    fields: tuple[str, ...]
    filters: frozenset[str] = frozenset()
    paged: bool = True
    columns: tuple[ExportColumn, ...] = ()


def _readable(
    name: str,
    path: str,
    columns: tuple[tuple[str, str] | tuple[str, str, LookupKind], ...],
    filters: str = "",
    paged: bool = True,
) -> TableSpec:
    """Exported headings resolve related identifiers to names; identifiers never appear."""
    resolved = tuple(ExportColumn(*column) for column in columns)
    return TableSpec(
        name,
        re.compile(path),
        tuple(dict.fromkeys(column.source for column in resolved)),
        frozenset(filters.split()),
        paged,
        resolved,
    )


REPORT_RELATIONS: dict[str, tuple[str, LookupKind]] = {
    "branchId": ("Branch", "branch"),
    "departmentId": ("Department", "department"),
    "bankId": ("Bank", "bank"),
}
REPORT_PEOPLE = {
    "employeeId": "Employee",
    "ownerEmployeeId": "Case Owner",
    "caseOwnerEmployeeId": "Case Owner",
    "currentEmployeeId": "Issued Employee",
}


ACHIEVED_VALUE_UNITS = {"CC": "Points", "PF": "AED"}


def achieved_value_heading(base: str, product_code: str | None) -> str:
    """Ranking values are CC points or PF AED, so the heading carries the selected unit."""
    unit = ACHIEVED_VALUE_UNITS.get(product_code or "")
    return f"{base} ({unit})" if unit else base


def report_columns(kind: str, product_code: str | None = None) -> tuple[ExportColumn, ...]:
    """Report exports show related names and business codes in place of identifiers."""
    approved = CATALOG[kind][2]
    keys = {key for key, _ in approved}
    columns: list[ExportColumn] = []
    for key, heading in approved:
        if key == "achievedValue":
            columns.append(ExportColumn(achieved_value_heading(heading, product_code), key))
        elif key in REPORT_RELATIONS:
            columns.append(ExportColumn(REPORT_RELATIONS[key][0], key, REPORT_RELATIONS[key][1]))
        elif key in REPORT_PEOPLE:
            label = "Coordinator" if kind == "coordinator-workload" else REPORT_PEOPLE[key]
            if "employeeName" not in keys:
                columns.append(ExportColumn(label, key, "employee"))
            if "systemEmployeeCode" not in keys:
                columns.append(ExportColumn(f"{label} Code", key, "employee_code"))
        else:
            columns.append(ExportColumn(heading, key))
    return tuple(columns)


CASE_COLUMNS: tuple[tuple[str, str] | tuple[str, str, LookupKind], ...] = (
    ("Case", "internalCaseId"),
    ("Customer", "customerId", "record"),
    ("Bank", "bankId", "bank"),
    ("Product", "productTypeId", "product"),
    ("CC variant", "productVariantId", "variant"),
    ("Requested PF amount (AED)", "requestedPfAmount"),
    ("Created by", "createdByEmployeeId", "employee"),
    ("Created by code", "createdByEmployeeId", "employee_code"),
    ("Case owner", "ownerEmployeeId", "employee"),
    ("Case owner code", "ownerEmployeeId", "employee_code"),
    ("Coordinator", "coordinatorEmployeeId", "employee"),
    ("Coordinator code", "coordinatorEmployeeId", "employee_code"),
    ("Branch", "branchId", "branch"),
    ("Department", "departmentId", "department"),
    ("Status", "status"),
    ("Current stage", "currentStage"),
    ("Bank case number", "bankCaseNumber"),
    ("Finalized at", "finalizedAt"),
    ("Voided at", "administrativelyVoidedAt"),
    ("Voided by", "administrativelyVoidedByEmployeeId", "employee"),
    ("Void reason", "administrativeVoidReason"),
    ("Created at", "createdAt"),
    ("Updated at", "updatedAt"),
)

PERFORMANCE_METRIC_COLUMNS: tuple[tuple[str, str] | tuple[str, str, LookupKind], ...] = (
    ("Created cases", "createdCaseCount"),
    ("Booked cases", "bookedCaseCount"),
    ("Completed cases", "completedCaseCount"),
    ("Rejected cases", "rejectedCaseCount"),
    ("In progress cases", "inProgressCaseCount"),
    ("Delayed cases", "delayedCaseCount"),
    ("Delayed metric", "delayedMetricState", "label"),
    ("CC points", "achievedCCPoints"),
    ("PF amount (AED)", "achievedPFAed"),
    ("CC target achievement (%)", "targetProgress.CC.achievementPercentage"),
    ("PF target achievement (%)", "targetProgress.PF.achievementPercentage"),
)

SPECS = (
    _readable(
        "cases",
        "/cases",
        CASE_COLUMNS,
        "status bankId productTypeId ownerEmployeeId createdFrom createdTo view q",
    ),
    _readable("case-approvals", "/cases/approval-queue", CASE_COLUMNS, "q"),
    _readable(
        "customers",
        "/customers",
        (
            ("Customer ID", "customerId"),
            ("Customer type", "type"),
            ("Customer", "name"),
            ("Emirates ID", "emiratesId"),
            ("Passport number", "passportNumber"),
            ("Employer", "employer"),
            ("Trade license", "tradeLicense"),
            ("Contact person", "contactPerson"),
            ("Mobile", "mobile"),
            ("Email", "email"),
            ("Created at", "createdAt"),
        ),
        "type q",
    ),
    _readable(
        "employees",
        "/employees",
        (
            ("Employee code", "employeeCode"),
            ("Employee", "fullName"),
            ("Status", "status"),
            ("Branch", "branchName"),
            ("Department", "departmentName"),
            ("Designation", "designation"),
        ),
        "status reportingManagerId",
    ),
    _readable(
        "teams",
        "/teams",
        (
            ("Team", "name"),
            ("Branch", "branch_id", "branch"),
            ("Department", "department_id", "department"),
            ("Team leader", "leader_employee_id", "employee"),
            ("Team leader code", "leader_employee_id", "employee_code"),
            ("Active", "active"),
        ),
    ),
    _readable(
        "finance-completed",
        "/finance/completed-cases",
        (
            ("Case", "internal_case_id"),
            ("Product", "product_code"),
            ("CC points", "cc_points"),
            ("PF amount (AED)", "pf_amount_aed"),
            ("Commission (AED)", "commission_aed"),
            ("Credited employee", "credited_owner_employee_id", "employee"),
            ("Credited employee code", "credited_owner_employee_id", "employee_code"),
            ("Rule effective date", "rule_effective_date"),
            ("Completed at", "completed_at"),
            ("Recorded at", "created_at"),
            ("Branch", "branch_id", "branch"),
            ("Department", "department_id", "department"),
            ("Current case owner", "current_owner_employee_id", "employee"),
            ("Current case owner code", "current_owner_employee_id", "employee_code"),
        ),
        "branchId productCode completedFrom completedTo",
    ),
    _readable(
        "finance-wallets",
        "/finance/wallets",
        (
            ("Employee", "employee_id", "employee"),
            ("Employee code", "employee_id", "employee_code"),
            ("Points balance", "balance_points"),
            ("Opened at", "created_at"),
        ),
        "employeeId",
    ),
    _readable(
        "finance-clawbacks",
        "/finance/clawbacks",
        (
            ("Case", "internal_case_id"),
            ("Amount (AED)", "amount_aed"),
            ("Clawback date", "clawback_date"),
            ("Reason", "reason"),
            ("Case owner", "case_owner_employee_id", "employee"),
            ("Case owner code", "case_owner_employee_id", "employee_code"),
            ("Recorded by", "created_by_employee_id", "employee"),
            ("Recorded by code", "created_by_employee_id", "employee_code"),
            ("Branch", "branch_id", "branch"),
            ("Department", "department_id", "department"),
            ("Recorded at", "created_at"),
        ),
        "branchId caseId",
    ),
    _readable(
        "finance-payments",
        "/finance/payments",
        (
            ("Employee", "employee_id", "employee"),
            ("Employee code", "employee_id", "employee_code"),
            ("Payment type", "payment_type"),
            ("Amount (AED)", "amount_aed"),
            ("Payment month", "payment_month"),
            ("Payment date", "payment_date"),
            ("Recorded by", "created_by_employee_id", "employee"),
            ("Recorded by code", "created_by_employee_id", "employee_code"),
            ("Branch", "branch_id", "branch"),
            ("Department", "department_id", "department"),
            ("Recorded at", "created_at"),
        ),
        "employeeId paymentType paymentFrom paymentTo",
    ),
    _readable(
        "finance-rules",
        "/finance/rules",
        (
            ("Bank", "bank_id", "bank"),
            ("Product", "product_type_id", "product"),
            ("CC variant", "product_variant_id", "variant"),
            ("PF amount min (AED)", "pf_amount_min"),
            ("PF amount max (AED)", "pf_amount_max"),
            ("CC points", "cc_points"),
            ("Commission (AED)", "commission_aed"),
            ("Effective date", "effective_date"),
            ("Active", "active"),
            ("Superseded", "superseded_by_rule_id", "present"),
            ("Created at", "created_at"),
        ),
        "bankId productTypeId active",
    ),
    _readable(
        "targets",
        "/targets",
        (
            ("Branch", "branchId", "branch"),
            ("Department", "departmentId", "department"),
            ("Designation", "designationId", "designation"),
            ("Effective date", "effectiveDate"),
            ("Target points", "targetPoints"),
            ("Target amount (AED)", "targetAmountAed"),
            ("Active", "active"),
            ("Inactive from date", "inactiveFromDate"),
            ("Superseded", "supersededByTargetId", "present"),
        ),
        "branchId departmentId designationId",
    ),
    _readable(
        "performance-employees",
        "/performance/employees",
        (
            ("Employee", "employeeId", "employee"),
            ("Employee code", "employeeId", "employee_code"),
            ("Start date", "startDate"),
            ("End date", "endDate"),
            *PERFORMANCE_METRIC_COLUMNS,
        ),
        "startDate endDate branchId departmentId teamId designationId productCode search",
    ),
    _readable(
        "performance-team",
        rf"/performance/teams/{UUID_PATH}",
        (
            ("Employee", "employeeId", "employee"),
            ("Employee code", "employeeId", "employee_code"),
            ("Start date", "startDate"),
            ("End date", "endDate"),
            *PERFORMANCE_METRIC_COLUMNS,
        ),
        "startDate endDate branchId departmentId teamId designationId productCode",
    ),
    _readable(
        "performance-comparisons",
        "/performance/comparisons",
        (("Group", "name"), *PERFORMANCE_METRIC_COLUMNS),
        "startDate endDate branchId departmentId teamId designationId productCode groupBy",
    ),
    _readable(
        "performance-rankings",
        "/performance/rankings",
        (
            ("Rank", "rank"),
            ("Employee", "employeeName"),
            ("Employee code", "employeeId", "employee_code"),
            ("Achievement percentage", "achievementPercentage"),
            ("Completed cases", "completedCaseCount"),
            ("Achieved value", "achievedValue"),
        ),
        "startDate endDate branchId departmentId teamId designationId productCode",
    ),
    _readable(
        "coordinator-workload",
        "/performance/coordinator-workload",
        (
            ("Coordinator", "employeeId", "employee"),
            ("Coordinator code", "employeeId", "employee_code"),
            ("Handled cases", "handledCases"),
            ("Booked submissions", "submittedBookedCases"),
            ("Stage updates", "stageUpdatedCases"),
        ),
        "startDate endDate branchId departmentId teamId designationId productCode",
    ),
    _readable(
        "attendance",
        "/attendance",
        (
            ("Employee", "employeeName"),
            ("Employee code", "systemEmployeeCode"),
            ("Branch", "branchId", "branch"),
            ("Attendance date", "attendanceDate"),
            ("Check-in time", "checkInTime"),
            ("Check-out time", "checkOutTime"),
            ("Status", "status"),
            ("Late", "isLate"),
            ("Imported from CSV", "csvImportBatchId", "present"),
        ),
        "branchId employeeId dateFrom dateTo status isLate search",
    ),
    _readable(
        "attendance-imports",
        "/attendance/imports",
        (
            ("Branch", "branchId", "branch"),
            ("Attendance date", "attendanceDate"),
            ("Status", "status"),
            ("Data rows", "dataRowCount"),
            ("Errors", "errorCount"),
            ("Uploaded at", "createdAt"),
        ),
        "branchId status",
    ),
    _readable(
        "attendance-import-rows",
        rf"/attendance/imports/{UUID_PATH}/rows",
        (
            ("Row", "rowNumber"),
            ("Status", "status"),
            ("Error", "errorCode", "label"),
            ("Column", "columnName"),
            ("Error detail", "errorDetail"),
        ),
    ),
    _readable(
        "assets",
        "/assets",
        (
            ("Asset code", "assetCode"),
            ("Branch", "branchId", "branch"),
            ("Category", "category"),
            ("Brand", "brand"),
            ("Model", "model"),
            ("Serial number", "serialNumber"),
            ("Mobile number", "mobileNumber"),
            ("Operator / provider", "operatorProvider"),
            ("Status", "status"),
            ("Assigned employee", "currentEmployeeId", "employee"),
            ("Assigned employee code", "currentEmployeeId", "employee_code"),
            ("Added at", "createdAt"),
        ),
        "branchId category status employeeId dateFrom dateTo search",
    ),
    _readable(
        "tasks",
        "/tasks",
        (
            ("Task", "title"),
            ("Description", "description"),
            ("Created by", "creatorEmployeeId", "employee"),
            ("Created by code", "creatorEmployeeId", "employee_code"),
            ("Assignee", "assigneeEmployeeId", "employee"),
            ("Assignee code", "assigneeEmployeeId", "employee_code"),
            ("Branch", "branchId", "branch"),
            ("Department", "departmentId", "department"),
            ("Team", "teamId", "team"),
            ("Priority", "priority"),
            ("Status", "status"),
            ("Due at", "dueAt"),
            ("Completed at", "completedAt"),
            ("Archived at", "archivedAt"),
            ("Overdue", "isOverdue"),
            ("Related type", "relatedType"),
            ("Related record", "relatedId", "record"),
            ("Created at", "createdAt"),
            ("Updated at", "updatedAt"),
        ),
        "view priority status assigneeId dueFrom dueTo q",
    ),
    _readable(
        "audit",
        "/audit-events",
        (
            ("Occurred At (Dubai)", "occurredAt", "dubai_time"),
            ("Event", "action", "label"),
            ("Module", "module", "label"),
            ("Record Type", "entityType", "label"),
            ("Record", "entityId", "record"),
            ("Actor", "actorEmployeeId", "employee"),
            ("Actor Code", "actorEmployeeId", "employee_code"),
        ),
        "actorId action module entityId fromTime toTime",
    ),
    _readable(
        "branches",
        "/branches",
        (
            ("Branch", "name"),
            ("Business Unit", "business_unit_id", "business_unit"),
            ("Operating city", "operating_city"),
            ("Active", "active"),
        ),
        paged=False,
    ),
    _readable(
        "departments",
        "/departments",
        (
            ("Department", "name"),
            ("Branch", "branch_id", "branch"),
            ("Target product", "product_type_id", "product"),
            ("Active", "active"),
        ),
        "branchId",
        paged=False,
    ),
    _readable(
        "business-units",
        "/business-units",
        (("Business Unit", "name"), ("Active", "active")),
        paged=False,
    ),
    _readable(
        "catalog-banks",
        "/catalog/banks",
        (
            ("Bank code", "bank_code"),
            ("Bank", "name"),
            ("Active", "active"),
            ("Created at", "created_at"),
            ("Updated at", "updated_at"),
        ),
        "active bankId productTypeId",
    ),
    _readable(
        "catalog-products",
        "/catalog/product-types",
        (
            ("Product code", "code"),
            ("Product", "name"),
            ("Active", "active"),
            ("Created at", "created_at"),
            ("Updated at", "updated_at"),
        ),
        "active bankId productTypeId",
    ),
    _readable(
        "catalog-mappings",
        "/catalog/bank-product-mappings",
        (
            ("Bank", "bank_id", "bank"),
            ("Product", "product_type_id", "product"),
            ("Active", "active"),
            ("Created at", "created_at"),
            ("Updated at", "updated_at"),
        ),
        "active bankId productTypeId",
    ),
    _readable(
        "catalog-variants",
        "/catalog/product-variants",
        (
            ("Variant", "name"),
            ("Bank", "bank_id", "bank"),
            ("Product", "product_type_id", "product"),
            ("Active", "active"),
            ("Created at", "created_at"),
            ("Updated at", "updated_at"),
        ),
        "active bankId productTypeId",
    ),
    _readable(
        "pipelines",
        "/pipelines",
        (
            ("Bank", "bank_id", "bank"),
            ("Product", "product_type_id", "product"),
            ("Version", "version"),
            ("Effective date", "effective_date"),
            ("Active", "active"),
            ("Created at", "created_at"),
        ),
        "bankId productTypeId active",
    ),
    _readable(
        "office-timings",
        "/office-timings",
        (
            ("Branch", "branchId", "branch"),
            ("Effective date", "effectiveDate"),
            ("Start time", "startTime"),
            ("End time", "endTime"),
            ("Created by", "createdByEmployeeId", "employee"),
            ("Created by code", "createdByEmployeeId", "employee_code"),
        ),
        "branchId",
    ),
    _readable(
        "uae-holidays",
        "/performance/uae-holidays",
        (
            ("Holiday date", "holidayDate"),
            ("Applicable year", "applicableYear"),
            ("Holiday", "name"),
            ("Source reference", "sourceReference"),
        ),
        "year",
    ),
    _readable(
        "dashboard-monthly",
        "/dashboard/monthly-activity",
        (
            ("Month", "label"),
            ("Start date", "start"),
            ("End date", "end"),
            ("CC cases", "cc"),
            ("PF cases", "pf"),
            ("PF amount (AED)", "pfAed"),
        ),
        "period startDate endDate branchId departmentId teamId productCode bankId",
        paged=False,
    ),
)


def resolve(source_path: str) -> tuple[TableSpec, str]:
    parsed = urlsplit(source_path)
    if parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path.startswith("/"):
        raise ApiError(422, "TABLE_EXPORT_SOURCE_INVALID", "Table source is unavailable")
    spec = next((item for item in SPECS if item.pattern.fullmatch(parsed.path)), None)
    if spec is None and parsed.path.startswith("/reports/"):
        kind = parsed.path.removeprefix("/reports/")
        if kind in CATALOG:
            columns = report_columns(kind)
            spec = TableSpec(
                f"report-{kind}",
                re.compile(re.escape(parsed.path)),
                tuple(dict.fromkeys(column.source for column in columns)),
                frozenset(CATALOG[kind][3]) | {"period", "startDate", "endDate"},
                True,
                columns,
            )
    if spec is None:
        raise ApiError(422, "TABLE_EXPORT_SOURCE_INVALID", "Table source is unavailable")
    pairs = validate_query(spec, parsed.query)
    product_code = dict(pairs).get("productCode")
    if any(column.source == "achievedValue" for column in spec.columns):
        spec = replace(
            spec,
            columns=tuple(
                replace(column, heading=achieved_value_heading(column.heading, product_code))
                if column.source == "achievedValue"
                else column
                for column in spec.columns
            ),
        )
    return spec, parsed.path + ("?" + urlencode(pairs) if pairs else "")
