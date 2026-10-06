"""Approved Phase 6 report names, roles, columns, and filter contracts."""

from app.errors import ApiError
from app.policies import Actor

GENERAL = {"Owner", "Managing Director", "Finance", "Sales Manager"}
OPERATIONS = {"Owner", "Managing Director", "Admin Staff"}
HR = {"Owner", "Managing Director", "HR"}

CATALOG: dict[str, tuple[str, set[str], tuple[tuple[str, str], ...], set[str]]] = {
    "case-pipeline": (
        "Case Pipeline Report",
        GENERAL,
        (
            ("internalCaseId", "Case ID"),
            ("status", "Status"),
            ("currentStage", "Bank Stage"),
            ("branchId", "Branch ID"),
            ("departmentId", "Department ID"),
            ("bankId", "Bank ID"),
            ("productCode", "Product"),
            ("ownerEmployeeId", "Case Owner ID"),
            ("createdAt", "Created At"),
        ),
        {"branchId", "departmentId", "bankId", "productCode", "status"},
    ),
    "customers": (
        "Customer Report",
        GENERAL,
        (
            ("customerId", "Customer ID"),
            ("type", "Customer Type"),
            ("caseCount", "Case Count"),
            ("createdAt", "Created At"),
        ),
        {"branchId", "departmentId", "bankId", "productCode", "customerType"},
    ),
    "sales-performance": (
        "Sales Performance Report",
        GENERAL,
        (
            ("employeeId", "Employee ID"),
            ("employeeName", "Employee Name"),
            ("createdCaseCount", "Created Cases"),
            ("bookedCaseCount", "Booked Cases"),
            ("completedCaseCount", "Completed Cases"),
            ("rejectedCaseCount", "Rejected Cases"),
            ("delayedCaseCount", "Delayed Cases"),
            ("achievedCCPoints", "CC Points"),
            ("achievedPFAed", "PF AED"),
            ("achievementPercentage", "Achievement Percentage"),
        ),
        {
            "branchId",
            "departmentId",
            "teamId",
            "employeeId",
            "designationId",
            "productCode",
            "bankId",
        },
    ),
    "ranking": (
        "Ranking and Employee of the Month Report",
        GENERAL,
        (
            ("rank", "Rank"),
            ("employeeId", "Employee ID"),
            ("employeeName", "Employee Name"),
            ("achievementPercentage", "Achievement Percentage"),
            ("completedCaseCount", "Completed Cases"),
            ("achievedValue", "Achieved Value"),
        ),
        {"branchId", "departmentId", "teamId", "designationId", "productCode", "bankId"},
    ),
    "coordinator-workload": (
        "Coordinator Workload Report",
        GENERAL,
        (
            ("employeeId", "Employee ID"),
            ("handledCases", "Handled Cases"),
            ("submittedBookedCases", "Booked Submissions"),
            ("stageUpdatedCases", "Stage Updates"),
        ),
        {"branchId", "departmentId", "designationId", "productCode", "bankId"},
    ),
    "finance-completed": (
        "Completed Case Finance Report",
        GENERAL,
        (
            ("internalCaseId", "Case ID"),
            ("productCode", "Product"),
            ("ccPoints", "CC Points"),
            ("pfAmountAed", "PF AED"),
            ("commissionAmountAed", "Commission AED"),
            ("caseOwnerEmployeeId", "Case Owner ID"),
            ("branchId", "Branch ID"),
            ("departmentId", "Department ID"),
            ("completedAt", "Completed At"),
        ),
        {"branchId", "departmentId", "bankId", "employeeId", "productCode"},
    ),
    "finance-clawbacks": (
        "Clawback Report",
        GENERAL,
        (
            ("internalCaseId", "Case ID"),
            ("amountAed", "Amount AED"),
            ("clawbackDate", "Clawback Date"),
            ("caseOwnerEmployeeId", "Case Owner ID"),
            ("branchId", "Branch ID"),
            ("departmentId", "Department ID"),
        ),
        {"branchId", "departmentId", "bankId", "employeeId", "productCode"},
    ),
    "finance-payments": (
        "Payment Report",
        GENERAL,
        (
            ("employeeId", "Employee ID"),
            ("paymentType", "Payment Type"),
            ("amountAed", "Amount AED"),
            ("paymentDate", "Payment Date"),
            ("branchId", "Branch ID"),
            ("departmentId", "Department ID"),
        ),
        {"branchId", "departmentId", "employeeId"},
    ),
    "finance-paid-totals": (
        "Employee Paid Totals Report",
        GENERAL,
        (
            ("employeeId", "Employee ID"),
            ("systemEmployeeCode", "System Employee Code"),
            ("salaryPaidAed", "Lifetime Salary Paid AED"),
            ("commissionPaidAed", "Lifetime Commission Paid AED"),
            ("totalPaidAed", "Lifetime Total Paid AED"),
        ),
        {"branchId", "departmentId", "employeeId"},
    ),
    "attendance": (
        "Attendance Report",
        OPERATIONS,
        (
            ("systemEmployeeCode", "System Employee Code"),
            ("employeeName", "Employee Name"),
            ("branchId", "Branch ID"),
            ("attendanceDate", "Attendance Date"),
            ("checkInTime", "Check In"),
            ("checkOutTime", "Check Out"),
            ("status", "Status"),
            ("isLate", "Late"),
        ),
        {"branchId", "employeeId", "status"},
    ),
    "assets": (
        "Asset Report",
        OPERATIONS,
        (
            ("assetCode", "Asset Code"),
            ("branchId", "Branch ID"),
            ("category", "Category"),
            ("brand", "Brand"),
            ("model", "Model"),
            ("status", "Status"),
            ("currentEmployeeId", "Issued Employee ID"),
        ),
        {"branchId", "employeeId", "status", "category"},
    ),
    "hr-employees": (
        "HR Employee Report",
        HR,
        (
            ("systemEmployeeCode", "System Employee Code"),
            ("employeeName", "Employee Name"),
            ("status", "Employee Status"),
            ("accessStatus", "Access Status"),
            ("branchId", "Branch ID"),
            ("departmentId", "Department ID"),
            ("designation", "Designation"),
            ("joiningDate", "Joining Date"),
        ),
        {"branchId", "departmentId", "designationId", "status", "accessStatus"},
    ),
    "hr-assignments": (
        "Employee Assignment History Report",
        HR,
        (
            ("systemEmployeeCode", "System Employee Code"),
            ("employeeName", "Employee Name"),
            ("branchId", "Branch ID"),
            ("departmentId", "Department ID"),
            ("designation", "Designation"),
            ("startDate", "Assignment Start Date"),
            ("endDate", "Assignment End Date"),
        ),
        {"branchId", "departmentId", "designationId", "status"},
    ),
}


# Embedded module reports read their module's records, so they follow its configurable grant.
MODULE_GRANTS = {"attendance": "attendance.write", "assets": "asset.write"}


def available(actor: Actor, kind: str) -> bool:
    definition = CATALOG.get(kind)
    grant = MODULE_GRANTS.get(kind)
    return (
        definition is not None
        and actor.designation in definition[1]
        and (grant is None or grant in actor.grants)
    )


def authorize(actor: Actor, kind: str, active_filters: set[str]) -> tuple:
    definition = CATALOG.get(kind)
    if definition is None:
        raise ApiError(404, "NOT_FOUND", "Report unavailable")
    if not available(actor, kind):
        raise ApiError(403, "FORBIDDEN", "Access denied")
    if active_filters - definition[3]:
        raise ApiError(422, "REPORT_FILTER_UNSUPPORTED", "Filter is unavailable for this report")
    return definition
