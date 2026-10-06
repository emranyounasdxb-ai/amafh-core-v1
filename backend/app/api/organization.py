"""Organization and employee routes with server-side scopes."""

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import case, func, select

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.db.cases import product_types
from app.db.organization import (
    assignment_history,
    branches,
    business_units,
    departments,
    designations,
    employees,
    team_memberships,
    teams,
    user_accounts,
)
from app.errors import ApiError
from app.policies import Actor, require
from app.repositories.employee_scope import employee_query
from app.schemas.hr_records import LastWorkingDateRecord, OffboardInput
from app.schemas.organization import (
    AssignmentChange,
    BranchCreate,
    DepartmentCreate,
    EmployeeCreate,
    EmployeeProfileUpdate,
    NamedCreate,
    TeamCreate,
    TeamMemberChange,
    UserCreate,
)
from app.services import account_access, employee_profile, organization_hierarchy
from app.services import organization as service
from app.services import teams as team_service

router = APIRouter(tags=["organization"])


def page_response(rows, total: int, page: int, size: int):
    return {"items": rows, "total": total, "page": page, "pageSize": size}


@router.get("/business-units")
async def list_business_units(actor: ActorDep, db: Db):
    require(actor, "organization.read")
    result = await db.execute(
        select(business_units.c.id, business_units.c.name, business_units.c.active).order_by(
            business_units.c.name
        )
    )
    return [dict(row) for row in result.mappings()]


@router.post("/business-units", status_code=201)
async def create_business_unit(item: NamedCreate, actor: CsrfActor, db: Db):
    return await service.create_master(db, actor, business_units, {"name": item.name})


@router.get("/branches")
async def list_branches(actor: ActorDep, db: Db):
    query = select(
        branches.c.id,
        branches.c.name,
        branches.c.business_unit_id,
        branches.c.operating_city,
        branches.c.active,
    )
    if actor.designation not in {"Owner", "Managing Director", "HR", "Finance"}:
        query = query.where(branches.c.id == actor.branch_id)
    return [dict(row) for row in (await db.execute(query.order_by(branches.c.name))).mappings()]


@router.post("/branches", status_code=201)
async def create_branch(item: BranchCreate, actor: CsrfActor, db: Db):
    return await service.create_master(
        db,
        actor,
        branches,
        {
            "name": item.name,
            "business_unit_id": item.businessUnitId,
            "operating_city": item.operatingCity,
        },
    )


@router.get("/departments")
async def list_departments(actor: ActorDep, db: Db, branchId: UUID | None = None):
    query = select(
        departments.c.id,
        departments.c.name,
        departments.c.branch_id,
        departments.c.product_type_id,
        product_types.c.code.label("product_type_code"),
        departments.c.active,
    ).outerjoin(product_types, product_types.c.id == departments.c.product_type_id)
    if actor.designation not in {"Owner", "Managing Director", "HR", "Finance"}:
        query = query.where(departments.c.branch_id == actor.branch_id)
    if branchId:
        query = query.where(departments.c.branch_id == branchId)
    return [dict(row) for row in (await db.execute(query.order_by(departments.c.name))).mappings()]


@router.post("/departments", status_code=201)
async def create_department(item: DepartmentCreate, actor: CsrfActor, db: Db):
    return await service.create_master(
        db,
        actor,
        departments,
        {"name": item.name, "branch_id": item.branchId, "product_type_id": item.productTypeId},
    )


@router.get("/designations")
async def list_designations(_actor: ActorDep, db: Db):
    return [
        dict(row)
        for row in (
            await db.execute(
                select(designations.c.id, designations.c.name).order_by(designations.c.name)
            )
        ).mappings()
    ]


@router.get("/organization/hierarchy")
async def get_organization_hierarchy(actor: ActorDep, db: Db):
    return await organization_hierarchy.read(db, actor)


@router.get("/employees")
async def list_employees(
    actor: ActorDep,
    db: Db,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    status: str | None = None,
    reportingManagerId: UUID | None = None,
    sort: str = "fullName",
    direction: str = "asc",
):
    query = employee_query(actor)
    if status:
        query = query.where(employees.c.status == status)
    if reportingManagerId:
        query = query.where(employees.c.reporting_manager_id == reportingManagerId)
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    managers = employees.alias("reporting_manager")
    visible_ids = select(employee_query(actor).subquery().c.id)
    manager_visible = managers.c.id.in_(visible_ids)
    query = (
        query.outerjoin(branches, branches.c.id == employees.c.branch_id)
        .outerjoin(departments, departments.c.id == employees.c.department_id)
        .outerjoin(managers, managers.c.id == employees.c.reporting_manager_id)
        .add_columns(
            branches.c.name.label("branch_name"),
            departments.c.name.label("department_name"),
            case((manager_visible, managers.c.full_name), else_=None).label(
                "reporting_manager_name"
            ),
            case((manager_visible, managers.c.company_employee_code), else_=None).label(
                "reporting_manager_code"
            ),
        )
    )
    sort_col = {
        "fullName": employees.c.full_name,
        "companyEmployeeCode": employees.c.company_employee_code,
        "designation": designations.c.name,
        "status": employees.c.status,
    }.get(sort)
    if sort_col is None or direction not in {"asc", "desc"}:
        raise ApiError(422, "VALIDATION_ERROR", "Invalid sorting")
    query = (
        query.order_by(
            (sort_col.asc() if direction == "asc" else sort_col.desc()).nulls_last(),
            employees.c.id,
        )
        .offset((page - 1) * pageSize)
        .limit(pageSize)
    )
    rows = []
    for row in (await db.execute(query)).mappings():
        rows.append(
            {
                "id": str(row["id"]),
                "employeeCode": row["company_employee_code"],
                "companyEmployeeCode": row["company_employee_code"],
                "fullName": row["full_name"],
                "status": row["status"],
                "branchId": str(row["branch_id"]) if row["branch_id"] else None,
                "departmentId": str(row["department_id"]) if row["department_id"] else None,
                "branchName": row["branch_name"],
                "departmentName": row["department_name"],
                "designation": row["designation"],
                "dateOfJoining": row["date_of_joining"],
                "lastWorkingDate": row["last_working_date"],
                "avatarFileId": str(row["avatar_file_id"]) if row["avatar_file_id"] else None,
                "reportingManagerId": str(row["reporting_manager_id"])
                if row["reporting_manager_id"]
                else None,
                "reportingManagerName": row["reporting_manager_name"],
                "reportingManagerCode": row["reporting_manager_code"],
            }
        )
    return page_response(rows, total, page, pageSize)


def _reads_account_state(actor: Actor) -> bool:
    return "access.write" in actor.grants or "password.reset" in actor.grants


@router.get("/employees/{employee_id}")
async def get_employee(employee_id: UUID, actor: ActorDep, db: Db):
    row = (
        (await db.execute(employee_query(actor).where(employees.c.id == employee_id)))
        .mappings()
        .first()
    )
    if not row:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    detail = {
        "id": str(row["id"]),
        "employeeCode": row["company_employee_code"],
        "companyEmployeeCode": row["company_employee_code"],
        "fullName": row["full_name"],
        "status": row["status"],
        "designation": row["designation"],
        "branchId": str(row["branch_id"]) if row["branch_id"] else None,
        "departmentId": str(row["department_id"]) if row["department_id"] else None,
        "reportingManagerId": str(row["reporting_manager_id"])
        if row["reporting_manager_id"]
        else None,
        "dateOfJoining": row["date_of_joining"],
        "lastWorkingDate": row["last_working_date"],
        "mobile": row["mobile"],
        "personalEmail": row["personal_email"]
        if actor.designation in {"Owner", "Managing Director", "HR"}
        or actor.employee_id == employee_id
        else None,
        "nationality": row["nationality"],
        "gender": row["gender"],
        "maritalStatus": row["marital_status"],
        "passportNumber": row["passport_number"]
        if actor.designation in {"Owner", "Managing Director", "HR"}
        or actor.employee_id == employee_id
        else None,
        "emiratesIdNumber": row["emirates_id_number"]
        if actor.designation in {"Owner", "Managing Director", "HR"}
        or actor.employee_id == employee_id
        else None,
        "avatarFileId": str(row["avatar_file_id"]) if row["avatar_file_id"] else None,
        "coverFileId": str(row["cover_file_id"]) if row["cover_file_id"] else None,
    }
    if _reads_account_state(actor):
        account = (
            (
                await db.execute(
                    select(
                        user_accounts.c.id,
                        user_accounts.c.access_status,
                        user_accounts.c.locked_at,
                    ).where(user_accounts.c.employee_id == employee_id)
                )
            )
            .mappings()
            .first()
        )
        detail["account"] = (
            {
                "id": str(account["id"]),
                "accessStatus": account["access_status"],
                "locked": account["locked_at"] is not None,
            }
            if account
            else None
        )
    return detail


@router.get("/employees/{employee_id}/login-code")
async def get_login_code(employee_id: UUID, actor: ActorDep, db: Db):
    require(actor, "access.write")
    code = await db.scalar(
        select(employees.c.system_employee_code).where(employees.c.id == employee_id)
    )
    if code is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return {"systemEmployeeCode": code}


@router.post("/employees", status_code=201)
async def create_employee(item: EmployeeCreate, actor: CsrfActor, db: Db):
    return await service.create_employee(db, actor, item)


@router.patch("/employees/{employee_id}", status_code=204)
async def update_employee_profile(
    employee_id: UUID, item: EmployeeProfileUpdate, actor: CsrfActor, db: Db
):
    await employee_profile.update_profile(db, actor, employee_id, item)


@router.post("/employees/{employee_id}/assignments", status_code=204)
async def assign_employee(employee_id: UUID, item: AssignmentChange, actor: CsrfActor, db: Db):
    await service.change_assignment(db, actor, employee_id, item)


@router.get("/employees/{employee_id}/assignments")
async def list_assignments(employee_id: UUID, actor: ActorDep, db: Db):
    if not (await db.execute(employee_query(actor).where(employees.c.id == employee_id))).first():
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    result = await db.execute(
        select(assignment_history)
        .where(assignment_history.c.employee_id == employee_id)
        .order_by(assignment_history.c.assignment_start_date)
    )
    return [
        {key: str(value) if isinstance(value, UUID) else value for key, value in row.items()}
        for row in result.mappings()
    ]


@router.post("/employees/{employee_id}/activate", status_code=204)
async def activate_employee(employee_id: UUID, actor: CsrfActor, db: Db):
    await service.activate_employee(db, actor, employee_id)


@router.post("/employees/{employee_id}/offboard", status_code=204)
async def offboard_employee(employee_id: UUID, item: OffboardInput, actor: CsrfActor, db: Db):
    await service.offboard_employee(db, actor, employee_id, item.lastWorkingDate)


@router.post("/employees/{employee_id}/last-working-date", status_code=204)
async def record_last_working_date(
    employee_id: UUID, item: LastWorkingDateRecord, actor: CsrfActor, db: Db
):
    await service.record_last_working_date(
        db, actor, employee_id, item.lastWorkingDate, item.reason
    )


@router.get("/users")
async def list_users(
    actor: ActorDep, db: Db, page: int = Query(1, ge=1), pageSize: int = Query(25, ge=1, le=100)
):
    require(actor, "access.write")
    total = await db.scalar(select(func.count()).select_from(user_accounts)) or 0
    result = await db.execute(
        select(
            user_accounts.c.id,
            user_accounts.c.employee_id,
            user_accounts.c.access_status,
            user_accounts.c.locked_at,
        )
        .order_by(user_accounts.c.id)
        .offset((page - 1) * pageSize)
        .limit(pageSize)
    )
    items = [
        {
            "id": str(row["id"]),
            "employeeId": str(row["employee_id"]),
            "accessStatus": row["access_status"],
            "locked": row["locked_at"] is not None,
        }
        for row in result.mappings()
    ]
    return page_response(items, total, page, pageSize)


@router.get("/users/{account_id}")
async def get_user(account_id: UUID, actor: ActorDep, db: Db):
    require(actor, "access.write")
    row = (
        (
            await db.execute(
                select(
                    user_accounts.c.id,
                    user_accounts.c.employee_id,
                    user_accounts.c.access_status,
                    user_accounts.c.locked_at,
                ).where(user_accounts.c.id == account_id)
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return {
        "id": str(row["id"]),
        "employeeId": str(row["employee_id"]),
        "accessStatus": row["access_status"],
        "locked": row["locked_at"] is not None,
    }


@router.post("/users", status_code=201)
async def provision_user(item: UserCreate, actor: CsrfActor, db: Db):
    return {"id": str(await account_access.provision_account(db, actor, item.employeeId))}


@router.post("/users/{account_id}/disable", status_code=204)
async def disable_user(account_id: UUID, actor: CsrfActor, db: Db):
    await account_access.disable_account(db, actor, account_id)


@router.post("/users/{account_id}/enable", status_code=204)
async def enable_user(account_id: UUID, actor: CsrfActor, db: Db):
    await account_access.enable_account(db, actor, account_id)


@router.get("/teams")
async def list_teams(
    actor: ActorDep,
    db: Db,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    sort: str = "name",
    direction: str = "asc",
):
    if actor.designation == "Team Leader":
        scope = teams.c.leader_employee_id == actor.employee_id
    else:
        require(actor, "team.write")
        scope = None
    leaders = employees.alias("team_leader")
    member_counts = (
        select(
            team_memberships.c.team_id,
            func.count().label("member_count"),
        )
        .where(team_memberships.c.end_date.is_(None))
        .group_by(team_memberships.c.team_id)
        .subquery()
    )
    query = select(
        teams.c.id,
        teams.c.name,
        teams.c.branch_id,
        teams.c.department_id,
        teams.c.leader_employee_id,
        teams.c.active,
        teams.c.updated_at,
        branches.c.name.label("branch_name"),
        departments.c.name.label("department_name"),
        leaders.c.full_name.label("leader_name"),
        leaders.c.company_employee_code.label("leader_code"),
        leaders.c.avatar_file_id.label("leader_avatar_file_id"),
        func.coalesce(member_counts.c.member_count, 0).label("member_count"),
    ).select_from(
        teams.join(branches, branches.c.id == teams.c.branch_id)
        .join(departments, departments.c.id == teams.c.department_id)
        .join(leaders, leaders.c.id == teams.c.leader_employee_id)
        .outerjoin(member_counts, member_counts.c.team_id == teams.c.id)
    )
    if scope is not None:
        query = query.where(scope, teams.c.active.is_(True))
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = {
        "name": teams.c.name,
        "active": teams.c.active,
        "branchName": branches.c.name,
        "departmentName": departments.c.name,
    }.get(sort)
    if order is None or direction not in {"asc", "desc"}:
        raise ApiError(422, "VALIDATION_ERROR", "Invalid sorting")
    result = await db.execute(
        query.order_by(
            (order.asc() if direction == "asc" else order.desc()).nulls_last(), teams.c.id
        )
        .offset((page - 1) * pageSize)
        .limit(pageSize)
    )
    return page_response([dict(row) for row in result.mappings()], total, page, pageSize)


@router.get("/teams/{team_id}")
async def get_team(team_id: UUID, actor: ActorDep, db: Db):
    if actor.designation != "Team Leader":
        require(actor, "team.write")
    query = select(teams).where(teams.c.id == team_id)
    if actor.designation == "Team Leader":
        query = query.where(
            teams.c.leader_employee_id == actor.employee_id, teams.c.active.is_(True)
        )
    team = (await db.execute(query)).mappings().first()
    if not team:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    members = await db.execute(
        select(team_memberships.c.employee_id).where(
            team_memberships.c.team_id == team_id, team_memberships.c.end_date.is_(None)
        )
    )
    return {
        "id": str(team["id"]),
        "name": team["name"],
        "branchId": str(team["branch_id"]),
        "departmentId": str(team["department_id"]),
        "leaderEmployeeId": str(team["leader_employee_id"]),
        "active": team["active"],
        "memberEmployeeIds": [str(row.employee_id) for row in members],
    }


@router.post("/teams", status_code=201)
async def create_team(item: TeamCreate, actor: CsrfActor, db: Db):
    return {"id": str(await team_service.create_team(db, actor, item))}


@router.post("/teams/{team_id}/members", status_code=204)
async def add_team_member(team_id: UUID, item: TeamMemberChange, actor: CsrfActor, db: Db):
    await team_service.add_team_member(db, actor, team_id, item.employeeId, item.startDate)


@router.post("/teams/{team_id}/members/{employee_id}/end", status_code=204)
async def end_team_member(team_id: UUID, employee_id: UUID, actor: CsrfActor, db: Db):
    await team_service.end_team_member(db, actor, team_id, employee_id)
