"""Locked role and record scope policy, independent of frontend previews.

``PERMISSION_MATRIX`` is the approved business-role and security boundary of
each User Type and its default configuration. Fixed grants always apply. A
configurable grant applies only while its persisted role permission row is
granted, and nothing outside the boundary can ever be granted.
"""

from dataclasses import dataclass
from uuid import UUID

from app.errors import ApiError

OWNER = "Owner"
MD = "Managing Director"
HR = "HR"
FINANCE = "Finance"

PERMISSION_MATRIX: dict[str, frozenset[str]] = {
    OWNER: frozenset(
        {
            "organization.write",
            "organization.read",
            "team.write",
            "employee.write",
            "employee.read",
            "access.write",
            "password.setup",
            "password.reset",
            "password.locked_reset",
            "permissions.read",
            "permissions.write",
        }
    ),
    MD: frozenset(
        {
            "organization.write",
            "organization.read",
            "team.write",
            "employee.read",
            "password.reset",
            "permissions.read",
        }
    ),
    "Sales Manager": frozenset({"employee.read"}),
    "Coordinator": frozenset(),
    "Team Leader": frozenset({"employee.read"}),
    "Sales Executive": frozenset(),
    "Admin Staff": frozenset(),
    HR: frozenset({"employee.write", "employee.read", "access.write", "password.setup"}),
    FINANCE: frozenset({"employee.read"}),
}

# Locked V1 permissions are seeded now even when the corresponding service is in a later phase.
_ADDITIONAL_PERMISSIONS = {
    OWNER: {
        "case.read",
        "case.correct",
        "case.void",
        "case.approve",
        "case.book",
        "case.csv",
        "customer.read",
        "customer.correct",
        "attendance.write",
        "asset.write",
        "finance.write",
        "finance.read",
        "report.read",
        "audit.read",
        "pipeline.write",
        "target.write",
        "office_timing.write",
        "package.read",
        "package.write",
        "employee_document.read",
        "employee_document.write",
        "employee_document.withdraw",
        "visa.read",
        "visa.write",
        "hr_letter.read",
        "hr_letter.write",
        "hr_letter.approve",
        "hr_letter.void",
        "hr_settings.write",
    },
    MD: {
        "case.read",
        "case.approve",
        "case.book",
        "case.csv",
        "customer.read",
        "attendance.write",
        "asset.write",
        "finance.write",
        "finance.read",
        "report.read",
        "audit.read",
        "pipeline.write",
        "target.write",
        "office_timing.write",
        "package.read",
        "employee_document.read",
        "visa.read",
    },
    "Sales Manager": {"case.create", "case.read", "case.approve", "finance.read", "report.read"},
    "Coordinator": {"case.create", "case.read", "case.book", "case.csv"},
    "Team Leader": {"case.create", "case.read"},
    "Sales Executive": {"case.create", "case.read"},
    "Admin Staff": {"case.create", "attendance.write", "asset.write"},
    HR: {
        "package.read",
        "package.write",
        "employee_document.read",
        "employee_document.write",
        "visa.read",
        "visa.write",
        "hr_letter.read",
        "hr_letter.write",
    },
    FINANCE: {"case.read", "finance.write", "finance.read", "report.read", "package.read"},
}
PERMISSION_MATRIX = {
    role: grants | _ADDITIONAL_PERMISSIONS[role] for role, grants in PERMISSION_MATRIX.items()
}
CASE_CREATORS = frozenset(
    role for role, grants in PERMISSION_MATRIX.items() if "case.create" in grants
)

# Action grants the Owner may revoke and restore for a non-Owner User Type within its boundary.
CONFIGURABLE_PERMISSIONS = frozenset(
    {
        "case.create",
        "case.approve",
        "case.book",
        "case.csv",
        "team.write",
        "organization.write",
        "employee.write",
        "attendance.write",
        "asset.write",
        "finance.write",
        "pipeline.write",
        "target.write",
        "office_timing.write",
        "package.write",
        "employee_document.write",
        "visa.write",
        "hr_letter.write",
    }
)
# Viewing access with its data scope, Owner-only correction, account security, Audit and
# permission management are mandatory protections, never configuration.
FIXED_PERMISSIONS = frozenset(
    {
        "organization.read",
        "employee.read",
        "case.read",
        "customer.read",
        "finance.read",
        "report.read",
        "case.correct",
        "case.void",
        "customer.correct",
        "access.write",
        "password.setup",
        "password.reset",
        "password.locked_reset",
        "audit.read",
        "permissions.read",
        "permissions.write",
        "package.read",
        "employee_document.read",
        "visa.read",
        "hr_letter.read",
        "employee_document.withdraw",
        "hr_letter.approve",
        "hr_letter.void",
        "hr_settings.write",
    }
)
ALL_PERMISSIONS = frozenset().union(*PERMISSION_MATRIX.values())


def is_configurable(designation: str, permission: str) -> bool:
    return (
        designation != OWNER
        and permission in CONFIGURABLE_PERMISSIONS
        and permission in PERMISSION_MATRIX.get(designation, frozenset())
    )


def fixed_grants(designation: str) -> frozenset[str]:
    boundary = PERMISSION_MATRIX.get(designation, frozenset())
    return boundary if designation == OWNER else boundary & FIXED_PERMISSIONS


def effective_grants(designation: str, configured: set[str] | frozenset[str]) -> frozenset[str]:
    """Fixed grants plus persisted configurable grants; an absent row grants nothing."""
    return fixed_grants(designation) | frozenset(
        key for key in configured if is_configurable(designation, key)
    )


EMPLOYEE_SCOPE = {
    OWNER: "all",
    MD: "all",
    FINANCE: "all",
    HR: "all",
    "Sales Manager": "department",
    "Team Leader": "team",
    "Sales Executive": "own",
    "Coordinator": "own",
    "Admin Staff": "branch",
}

CASE_SCOPE = {
    OWNER: "all",
    MD: "all",
    FINANCE: "all",
    HR: "none",
    "Sales Manager": "department",
    "Coordinator": "assigned",
    "Team Leader": "team",
    "Sales Executive": "own",
    "Admin Staff": "none",
}


@dataclass(frozen=True)
class Actor:
    account_id: UUID
    employee_id: UUID
    designation: str
    display_name: str
    branch_id: UUID | None
    department_id: UUID | None
    session_id: UUID
    csrf_hash: str
    grants: frozenset[str] = frozenset()


def require(actor: Actor, permission: str) -> None:
    if permission not in actor.grants:
        raise ApiError(403, "FORBIDDEN", "Access denied")


def employee_visible(
    actor: Actor, employee: dict, team_member_ids: set[UUID] | None = None
) -> bool:
    scope = EMPLOYEE_SCOPE.get(actor.designation, "none")
    if scope == "all":
        return True
    if scope == "branch":
        return actor.branch_id is not None and employee["branch_id"] == actor.branch_id
    if scope == "department":
        return (
            actor.branch_id is not None
            and actor.department_id is not None
            and employee["branch_id"] == actor.branch_id
            and employee["department_id"] == actor.department_id
        )
    if scope == "team":
        return employee["id"] == actor.employee_id or employee["id"] in (team_member_ids or set())
    return employee["id"] == actor.employee_id


def case_visible(actor: Actor, case: dict, team_member_ids: set[UUID] | None = None) -> bool:
    scope = CASE_SCOPE.get(actor.designation, "none")
    if scope == "all":
        return True
    if scope == "department":
        return case["branch_id"] == actor.branch_id and case["department_id"] == actor.department_id
    if scope == "team":
        return case["owner_employee_id"] == actor.employee_id or case["owner_employee_id"] in (
            team_member_ids or set()
        )
    if scope == "own":
        return case["owner_employee_id"] == actor.employee_id
    if scope == "assigned":
        return case["coordinator_employee_id"] == actor.employee_id or (
            case["bank_case_number"] is not None
            and case.get("owner_transfer_previous_status") is None
            and case["branch_id"] == actor.branch_id
            and case["department_id"] == actor.department_id
        )
    return False
