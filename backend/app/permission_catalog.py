"""Readable names, data scopes and fixed-protection explanations for User Type permissions."""

from app.policies import (
    CASE_CREATORS,
    CASE_SCOPE,
    EMPLOYEE_SCOPE,
    OWNER,
    PERMISSION_MATRIX,
    is_configurable,
)

MODULES = (
    "Cases",
    "Customers",
    "Employees",
    "HR records",
    "Organization",
    "Teams",
    "Attendance",
    "Assets",
    "Finance",
    "Reports",
    "Settings",
    "Audit",
    "Account security",
)

PERMISSION_LABELS: dict[str, tuple[str, str]] = {
    "case.read": ("Cases", "View Cases"),
    "case.create": ("Cases", "Create Cases"),
    "case.approve": ("Cases", "Approve Cases and select the Coordinator"),
    "case.book": ("Cases", "Enter the initial Bank Case Number"),
    "case.csv": ("Cases", "Update bank stages through CSV"),
    "case.correct": ("Cases", "Correct or reopen Cases"),
    "case.void": ("Cases", "Administratively void or archive Cases"),
    "customer.read": ("Customers", "View Customers"),
    "customer.correct": ("Customers", "Correct Customer identity"),
    "employee.read": ("Employees", "View employee records"),
    "employee.write": ("Employees", "Add, update and offboard employees"),
    "package.read": ("HR records", "View employee salary packages"),
    "package.write": ("HR records", "Add employee salary package versions"),
    "employee_document.read": ("HR records", "View and download employee documents"),
    "employee_document.write": ("HR records", "Upload and replace employee documents"),
    "employee_document.withdraw": ("HR records", "Withdraw employee documents"),
    "visa.read": ("HR records", "View visa records"),
    "visa.write": ("HR records", "Manage visa records"),
    "hr_letter.read": ("HR records", "View employee letters and certificates"),
    "hr_letter.write": (
        "HR records",
        "Prepare letters and certificates and issue non-salary letters",
    ),
    "hr_letter.approve": (
        "HR records",
        "Approve letters with salary details and experience certificates",
    ),
    "hr_letter.void": ("HR records", "Void issued letters and certificates"),
    "organization.read": ("Organization", "View the organization structure"),
    "team.write": ("Teams", "View and manage Teams and membership"),
    "attendance.write": ("Attendance", "View and manage attendance"),
    "asset.write": ("Assets", "View and manage assets and inventory"),
    "finance.read": ("Finance", "View financial information"),
    "finance.write": ("Finance", "Manage financial rules, payments and clawbacks"),
    "report.read": ("Reports", "View reports and their exports"),
    "organization.write": ("Settings", "Manage business units, Branches and Departments"),
    "pipeline.write": ("Settings", "Manage Banks, Products and Pipelines"),
    "target.write": ("Settings", "Manage Targets and UAE holidays"),
    "office_timing.write": ("Settings", "Manage Office Timings"),
    "permissions.read": ("Settings", "View User Type permissions"),
    "permissions.write": ("Settings", "Manage User Type permissions"),
    "hr_settings.write": (
        "Settings",
        "Manage HR document requirements, templates and company details",
    ),
    "audit.read": ("Audit", "View and export the audit history"),
    "access.write": ("Account security", "Enable or disable system access"),
    "password.setup": ("Account security", "Generate initial password setup links"),
    "password.reset": ("Account security", "Generate password reset links"),
    "password.locked_reset": ("Account security", "Reset locked accounts"),
}

SCOPE_LABELS = {
    "all": "Company-wide",
    "branch": "Assigned Branch",
    "department": "Assigned Branch and Department",
    "team": "Own and direct Team",
    "own": "Own records",
    "assigned": "Assigned, then booked in Branch and Department",
}

_SALES_DEPARTMENT_SCOPED = {"finance.read", "report.read"}
_BRANCH_OPERATIONS = {"attendance.write", "asset.write"}
_OWNER_ONLY = {
    "case.correct",
    "case.void",
    "customer.correct",
    "password.locked_reset",
    "employee_document.withdraw",
    "hr_letter.approve",
    "hr_letter.void",
    "hr_settings.write",
}
_SECURITY = {"access.write", "password.setup", "password.reset"}
_VIEWING = {
    "organization.read",
    "employee.read",
    "case.read",
    "customer.read",
    "finance.read",
    "report.read",
    "package.read",
    "employee_document.read",
    "visa.read",
    "hr_letter.read",
}
_HR_RECORDS = {
    "package.read",
    "package.write",
    "employee_document.read",
    "employee_document.write",
    "visa.read",
    "visa.write",
    "hr_letter.read",
    "hr_letter.write",
}


def data_scope(designation: str, key: str) -> str:
    """The record scope the existing server rules apply to a granted action."""
    if key == "case.create":
        return "team" if designation == "Team Leader" else "own"
    if key == "case.csv" and designation == "Coordinator":
        return "department"
    if key.startswith("case."):
        return CASE_SCOPE.get(designation, "all")
    if key == "employee.read" or key in _HR_RECORDS:
        return EMPLOYEE_SCOPE.get(designation, "all")
    if key in _SALES_DEPARTMENT_SCOPED and designation == "Sales Manager":
        return "department"
    if key in _BRANCH_OPERATIONS and designation == "Admin Staff":
        return "branch"
    return "all"


def fixed_reason(designation: str, key: str) -> str | None:
    """Why an action cannot be changed for this User Type, or None when it is configurable."""
    if is_configurable(designation, key):
        return None
    if key == "case.create" and designation not in CASE_CREATORS:
        return (
            "Case creation is limited to Sales Executive, Team Leader, Sales Manager, "
            "Coordinator and Admin Staff."
        )
    if designation == OWNER and key in PERMISSION_MATRIX[OWNER]:
        return "The Owner's permissions are fixed. The Owner holds full system authority."
    if key not in PERMISSION_MATRIX.get(designation, frozenset()):
        return "Not permitted for this User Type. Fixed business-role and security boundary."
    if key in _VIEWING:
        return "Viewing access and its data scope are fixed by the User Type's business role."
    if key in _OWNER_ONLY:
        return "Owner-only control."
    if key in _SECURITY:
        return "Fixed account-security boundary."
    if key == "audit.read":
        return "Audit access is fixed to the Owner and Managing Director."
    return "Permission management access is fixed."


RESTRICTIONS = (
    {
        "title": "Owner authority",
        "description": "The Owner's permissions are fixed. Only the Owner manages permissions; "
        "the Managing Director may view them.",
    },
    {
        "title": "Business-role boundaries",
        "description": "An action can be granted only within the User Type's approved business "
        "role. Only Sales Executive, Team Leader, Sales Manager, Coordinator and Admin Staff "
        "may create Cases, each for themselves; only a Team Leader may also create Cases for "
        "their Team's Sales Executives. Owner, Managing Director, HR and Finance cannot create "
        "Cases. Creating a Case never widens viewing scope or other Case actions, and every "
        "new Case waits for Sales Manager approval.",
    },
    {
        "title": "Data scopes",
        "description": "Record scope (Own, Team, Branch, Branch and Department, or company-wide) "
        "is fixed by the User Type and cannot be widened.",
    },
    {
        "title": "Viewing access",
        "description": "Module viewing access for Cases, Customers, Employees, HR records, "
        "Organization, Finance and Reports is fixed by the User Type.",
    },
    {
        "title": "Audit and exports",
        "description": "Audit history and selected-row table exports are available only to the "
        "Owner and Managing Director.",
    },
    {
        "title": "Owner-only corrections",
        "description": "Case correction, reopen and Administrative Void/Archive, Customer "
        "identity correction, locked-account reset, employee document withdrawal, approval "
        "and voiding of letters and certificates, HR document settings, and recording a "
        "missing last working date remain Owner-only.",
    },
    {
        "title": "Account security",
        "description": "System access, setup links and password resets follow the fixed "
        "security boundary: HR and Owner set up access; Owner and Managing Director reset.",
    },
    {
        "title": "Workflow rules",
        "description": "Workflow guards, such as the locked Bank Case Number and final-stage "
        "locks, are business rules and not permissions.",
    },
)
