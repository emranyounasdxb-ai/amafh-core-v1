"""Organization, employment, identity and access schema."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from .base import created_at, metadata, pk, updated_at

business_units = Table(
    "business_units",
    metadata,
    pk(),
    Column("name", String(150), nullable=False, unique=True),
    Column("active", Boolean, nullable=False, server_default="true"),
    created_at(),
    updated_at(),
)
branches = Table(
    "branches",
    metadata,
    pk(),
    Column(
        "business_unit_id", UUID(as_uuid=True), ForeignKey("business_units.id", ondelete="RESTRICT")
    ),
    Column("name", String(150), nullable=False, unique=True),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column("operating_city", String(20)),
    created_at(),
    updated_at(),
    CheckConstraint("operating_city IN ('Dubai', 'Abu Dhabi')", name="ck_branches_operating_city"),
)
departments = Table(
    "departments",
    metadata,
    pk(),
    Column(
        "branch_id",
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("name", String(150), nullable=False),
    Column(
        "product_type_id",
        UUID(as_uuid=True),
        ForeignKey(
            "product_types.id",
            ondelete="RESTRICT",
            use_alter=True,
            name="departments_product_type_id_fkey",
        ),
        index=True,
    ),
    Column("active", Boolean, nullable=False, server_default="true"),
    created_at(),
    updated_at(),
    UniqueConstraint("branch_id", "name"),
    UniqueConstraint("id", "branch_id", name="uq_department_id_branch"),
)
designations = Table(
    "designation_user_types",
    metadata,
    pk(),
    Column("name", String(80), nullable=False, unique=True),
    Column("locked", Boolean, nullable=False, server_default="true"),
    created_at(),
    CheckConstraint(
        "name IN ('Owner','Managing Director','Sales Manager','Coordinator',"
        "'Team Leader','Sales Executive','Admin Staff','HR','Finance') AND locked"
    ),
)
permissions = Table(
    "permissions",
    metadata,
    pk(),
    Column("key", String(120), nullable=False, unique=True),
    Column("description", String(255), nullable=False),
    created_at(),
)
role_permissions = Table(
    "role_permissions",
    metadata,
    pk(),
    Column(
        "designation_id",
        UUID(as_uuid=True),
        ForeignKey("designation_user_types.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "permission_id",
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("granted", Boolean, nullable=False, server_default="true"),
    Column("updated_at", DateTime(timezone=True)),
    Column(
        "updated_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
    ),
    created_at(),
    UniqueConstraint("designation_id", "permission_id"),
)
record_scope_config = Table(
    "record_scope_config",
    metadata,
    pk(),
    Column(
        "designation_id",
        UUID(as_uuid=True),
        ForeignKey("designation_user_types.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("resource", String(80), nullable=False),
    Column("scope", String(30), nullable=False),
    created_at(),
    UniqueConstraint("designation_id", "resource"),
    CheckConstraint("scope IN ('all','branch','department','team','own','assigned','none')"),
)
employees = Table(
    "employees",
    metadata,
    pk(),
    Column("system_employee_code", String(80), nullable=False, unique=True),
    Column("company_employee_code", String(80), nullable=False, unique=True),
    Column("full_name", String(200), nullable=False),
    Column("mobile", String(40), nullable=False),
    Column("personal_email", String(254), nullable=False),
    Column("nationality", String(2), nullable=False),
    Column("gender", String(10), nullable=False),
    Column("marital_status", String(10), nullable=False),
    Column("date_of_joining", Date, nullable=False),
    Column("passport_number", String(100), nullable=False, unique=True),
    Column("emirates_id_number", String(100), unique=True),
    Column(
        "designation_id",
        UUID(as_uuid=True),
        ForeignKey("designation_user_types.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("branch_id", UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT")),
    Column("department_id", UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT")),
    Column(
        "reporting_manager_id", UUID(as_uuid=True), ForeignKey("employees.id", ondelete="RESTRICT")
    ),
    Column("status", String(20), nullable=False, server_default="Pending Setup"),
    Column("last_working_date", Date),
    Column(
        "avatar_file_id",
        UUID(as_uuid=True),
        ForeignKey(
            "stored_files.id",
            ondelete="RESTRICT",
            use_alter=True,
            name="employees_avatar_file_id_fkey",
        ),
    ),
    Column(
        "cover_file_id",
        UUID(as_uuid=True),
        ForeignKey(
            "stored_files.id",
            ondelete="RESTRICT",
            use_alter=True,
            name="employees_cover_file_id_fkey",
        ),
    ),
    created_at(),
    updated_at(),
    CheckConstraint("gender IN ('Male','Female')"),
    CheckConstraint("marital_status IN ('Single','Married')"),
    CheckConstraint("status IN ('Pending Setup','Active','Offboarded')"),
    CheckConstraint(
        "last_working_date IS NULL OR (status = 'Offboarded' "
        "AND last_working_date >= date_of_joining)",
        name="ck_employee_last_working_date",
    ),
    CheckConstraint(
        "(branch_id IS NULL AND department_id IS NULL) OR "
        "(branch_id IS NOT NULL AND department_id IS NOT NULL)",
        name="ck_employee_assignment_pair",
    ),
    ForeignKeyConstraint(
        ["department_id", "branch_id"],
        ["departments.id", "departments.branch_id"],
        name="fk_employee_department_branch",
    ),
    Index("ix_employees_branch_department", "branch_id", "department_id"),
)
assignment_history = Table(
    "employee_assignment_history",
    metadata,
    pk(),
    Column(
        "employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("branch_id", UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT")),
    Column("department_id", UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT")),
    Column(
        "designation_id",
        UUID(as_uuid=True),
        ForeignKey("designation_user_types.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "reporting_manager_id", UUID(as_uuid=True), ForeignKey("employees.id", ondelete="RESTRICT")
    ),
    Column("assignment_start_date", Date, nullable=False),
    Column("assignment_end_date", Date),
    created_at(),
    ForeignKeyConstraint(
        ["department_id", "branch_id"],
        ["departments.id", "departments.branch_id"],
        name="fk_assignment_department_branch",
    ),
    Index("ix_assignment_employee_dates", "employee_id", "assignment_start_date"),
    Index(
        "uq_assignment_current",
        "employee_id",
        unique=True,
        postgresql_where=text("assignment_end_date IS NULL"),
    ),
)
teams = Table(
    "teams",
    metadata,
    pk(),
    Column("name", String(150), nullable=False),
    Column(
        "branch_id",
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "department_id",
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "leader_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("active", Boolean, nullable=False, server_default="true"),
    created_at(),
    updated_at(),
    UniqueConstraint("branch_id", "department_id", "name"),
    ForeignKeyConstraint(
        ["department_id", "branch_id"],
        ["departments.id", "departments.branch_id"],
        name="fk_team_department_branch",
    ),
    Index(
        "uq_active_team_leader", "leader_employee_id", unique=True, postgresql_where=text("active")
    ),
)
team_leader_history = Table(
    "team_leader_history",
    metadata,
    pk(),
    Column(
        "team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    ),
    Column(
        "leader_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date),
    created_at(),
    Index(
        "uq_current_team_leader_history",
        "team_id",
        unique=True,
        postgresql_where=text("end_date IS NULL"),
    ),
)
team_memberships = Table(
    "team_memberships",
    metadata,
    pk(),
    Column(
        "team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    ),
    Column(
        "employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date),
    created_at(),
    Index(
        "uq_active_team_member",
        "employee_id",
        unique=True,
        postgresql_where=text("end_date IS NULL"),
    ),
)
user_accounts = Table(
    "user_accounts",
    metadata,
    pk(),
    Column(
        "employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    ),
    Column("access_status", String(20), nullable=False, server_default="Not Provisioned"),
    Column("password_hash", Text),
    Column("failed_attempts", Integer, nullable=False, server_default="0"),
    Column("locked_at", DateTime(timezone=True)),
    created_at(),
    updated_at(),
    CheckConstraint("access_status IN ('Not Provisioned','Active','Disabled')"),
    CheckConstraint("failed_attempts >= 0"),
)
password_tokens = Table(
    "password_tokens",
    metadata,
    pk(),
    Column(
        "account_id",
        UUID(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("kind", String(10), nullable=False),
    Column("token_hash", String(64), nullable=False, unique=True),
    Column(
        "generated_by_employee_id",
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("used_at", DateTime(timezone=True)),
    Column("invalidated_at", DateTime(timezone=True)),
    created_at(),
    CheckConstraint("kind IN ('setup','reset')"),
    Index("ix_password_tokens_account_kind", "account_id", "kind"),
)
sessions = Table(
    "sessions",
    metadata,
    pk(),
    Column(
        "account_id",
        UUID(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("token_hash", String(64), nullable=False, unique=True),
    Column("csrf_hash", String(64), nullable=False),
    Column("last_active_at", DateTime(timezone=True), nullable=False),
    Column("invalidated_at", DateTime(timezone=True)),
    created_at(),
    Index("ix_sessions_account_active", "account_id", "invalidated_at"),
)
login_failures = Table(
    "login_failures",
    metadata,
    pk(),
    Column(
        "account_id",
        UUID(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    created_at(),
    Index("ix_login_failures_account", "account_id"),
)

# Database uniqueness uses the same normalized identity as the API boundary.


def _canonical(column, uppercase: bool = False):
    expression = func.regexp_replace(func.btrim(column), "[[:space:]]+", " ", "g")
    return func.upper(expression) if uppercase else func.lower(expression)


Index("uq_business_unit_name_canonical", _canonical(business_units.c.name), unique=True)
Index("uq_branch_name_canonical", _canonical(branches.c.name), unique=True)
Index(
    "uq_department_name_canonical",
    departments.c.branch_id,
    _canonical(departments.c.name),
    unique=True,
)
for column in ("company_employee_code", "passport_number", "emirates_id_number"):
    Index(
        f"uq_employee_{column}_canonical",
        _canonical(employees.c[column], uppercase=True),
        unique=True,
    )
Index(
    "uq_team_name_canonical",
    teams.c.branch_id,
    teams.c.department_id,
    _canonical(teams.c.name),
    unique=True,
)
