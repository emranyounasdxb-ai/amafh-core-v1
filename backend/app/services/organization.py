"""Phase 1 organization and employee commands."""

from datetime import date, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.organization import (
    assignment_history,
    branches,
    business_units,
    departments,
    designations,
    employees,
    user_accounts,
)
from app.errors import ApiError
from app.identifiers import new_system_employee_code
from app.policies import Actor, require
from app.schemas.organization import AssignmentChange, EmployeeCreate
from app.services.assignment_integrity import (
    guard_direct_reports,
    reconcile_teams,
    validate_manager,
)
from app.services.department_products import require_target_product
from app.services.notification_events import access_changed, notify
from app.services.privileged_access import require_owner_for_privileged_account


def dubai_today():
    return datetime.now(ZoneInfo("Asia/Dubai")).date()


async def _department_in_branch(
    session: AsyncSession, branch_id: UUID | None, department_id: UUID | None
) -> None:
    if department_id is None and branch_id is None:
        return
    if department_id is None or branch_id is None:
        raise ApiError(422, "INVALID_ASSIGNMENT", "Branch and Department must be assigned together")
    found = await session.scalar(
        select(departments.c.id)
        .where(
            departments.c.id == department_id,
            departments.c.branch_id == branch_id,
            departments.c.active.is_(True),
        )
        .with_for_update()
    )
    if not found:
        raise ApiError(422, "INVALID_ASSIGNMENT", "Invalid Branch and Department")


async def create_master(session: AsyncSession, actor: Actor, table, values: dict) -> dict:
    require(actor, "organization.write")
    if table is departments:
        branch = await session.scalar(
            select(branches.c.id)
            .where(branches.c.id == values["branch_id"], branches.c.active.is_(True))
            .with_for_update()
        )
        if not branch:
            raise ApiError(422, "INVALID_BRANCH", "Invalid Branch")
        if values.get("product_type_id") is not None:
            await require_target_product(session, values["product_type_id"])
    if table is branches and values.get("business_unit_id"):
        unit = await session.scalar(
            select(business_units.c.id)
            .where(
                business_units.c.id == values["business_unit_id"],
                business_units.c.active.is_(True),
            )
            .with_for_update()
        )
        if not unit:
            raise ApiError(422, "INVALID_BUSINESS_UNIT", "Invalid Business Unit")
    record_id = uuid4()
    try:
        await session.execute(table.insert().values(id=record_id, **values))
        await audit.record(
            session,
            actor=actor.employee_id,
            action=f"{table.name}.created",
            module="organization",
            entity_type=table.name,
            entity_id=record_id,
            after={
                "name": values["name"],
                **(
                    {"product_type_id": str(values["product_type_id"])}
                    if values.get("product_type_id") is not None
                    else {}
                ),
                **(
                    {"operating_city": values["operating_city"]}
                    if values.get("operating_city") is not None
                    else {}
                ),
            },
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return {
        "id": str(record_id),
        **{k: str(v) if isinstance(v, UUID) else v for k, v in values.items()},
    }


async def create_employee(session: AsyncSession, actor: Actor, item: EmployeeCreate) -> dict:
    require(actor, "employee.write")
    if item.gender not in {"Male", "Female"} or item.maritalStatus not in {"Single", "Married"}:
        raise ApiError(422, "INVALID_EMPLOYEE", "Invalid employee option")
    await _department_in_branch(session, item.branchId, item.departmentId)
    designation = await session.scalar(
        select(designations.c.name).where(
            designations.c.id == item.designationId, designations.c.locked.is_(True)
        )
    )
    if not designation:
        raise ApiError(422, "INVALID_DESIGNATION", "Invalid Designation")
    require_owner_for_privileged_account(actor, designation)
    if designation == "Owner":
        raise ApiError(403, "FORBIDDEN", "Owner enrollment requires the local command")
    employee_id = uuid4()
    await validate_manager(
        session,
        employee_id,
        item.reportingManagerId,
        item.branchId,
        item.departmentId,
        item.designationId,
    )
    values = dict(
        id=employee_id,
        system_employee_code=await new_system_employee_code(session),
        company_employee_code=item.companyEmployeeCode,
        full_name=item.fullName,
        mobile=item.mobile,
        personal_email=str(item.personalEmail).lower(),
        nationality=item.nationality,
        gender=item.gender,
        marital_status=item.maritalStatus,
        date_of_joining=item.dateOfJoining,
        passport_number=item.passportNumber,
        emirates_id_number=item.emiratesIdNumber,
        designation_id=item.designationId,
        branch_id=item.branchId,
        department_id=item.departmentId,
        reporting_manager_id=item.reportingManagerId,
        status="Pending Setup",
    )
    try:
        await session.execute(employees.insert().values(**values))
        await session.execute(
            assignment_history.insert().values(
                employee_id=employee_id,
                branch_id=item.branchId,
                department_id=item.departmentId,
                designation_id=item.designationId,
                reporting_manager_id=item.reportingManagerId,
                assignment_start_date=item.dateOfJoining,
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="employee.created",
            module="employees",
            entity_type="employee",
            entity_id=employee_id,
            after={"status": "Pending Setup", "designationId": str(item.designationId)},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return {
        "id": str(employee_id),
        "companyEmployeeCode": item.companyEmployeeCode,
        "status": "Pending Setup",
    }


async def change_assignment(
    session: AsyncSession, actor: Actor, employee_id: UUID, item: AssignmentChange
) -> None:
    require(actor, "employee.write")
    if item.effectiveDate != dubai_today():
        raise ApiError(422, "INVALID_EFFECTIVE_DATE", "Assignment changes must take effect today")
    await _department_in_branch(session, item.branchId, item.departmentId)
    new_role = await session.scalar(
        select(designations.c.name).where(designations.c.id == item.designationId)
    )
    if not new_role:
        raise ApiError(422, "INVALID_DESIGNATION", "Invalid Designation")
    result = await session.execute(
        select(employees).where(employees.c.id == employee_id).with_for_update()
    )
    old = result.mappings().first()
    if not old or old["status"] == "Offboarded":
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    old_role = await session.scalar(
        select(designations.c.name).where(designations.c.id == old["designation_id"])
    )
    if new_role == "Owner" and old_role != "Owner":
        raise ApiError(403, "FORBIDDEN", "Owner enrollment requires the local command")
    if old_role == "Owner" and new_role != "Owner":
        raise ApiError(403, "FORBIDDEN", "Owner designation cannot be reassigned")
    if old_role == "Owner":
        raise ApiError(403, "OWNER_PROTECTED", "The global Owner cannot have an assignment")
    require_owner_for_privileged_account(actor, old_role)
    require_owner_for_privileged_account(actor, new_role)
    if old_role == "HR" and new_role != "HR" and actor.designation != "Owner":
        raise ApiError(403, "FORBIDDEN", "Only the Owner can change an HR User Type")
    await guard_direct_reports(
        session, employee_id, new_role, item.branchId, item.departmentId, old["status"]
    )
    await validate_manager(
        session,
        employee_id,
        item.reportingManagerId,
        item.branchId,
        item.departmentId,
        item.designationId,
    )
    before = {
        "branchId": str(old["branch_id"]) if old["branch_id"] else None,
        "departmentId": str(old["department_id"]) if old["department_id"] else None,
        "designationId": str(old["designation_id"]),
        "reportingManagerId": str(old["reporting_manager_id"])
        if old["reporting_manager_id"]
        else None,
    }
    try:
        await reconcile_teams(
            session, actor, employee_id, item.branchId, item.departmentId, new_role, old["status"]
        )
        await session.execute(
            update(assignment_history)
            .where(
                and_(
                    assignment_history.c.employee_id == employee_id,
                    assignment_history.c.assignment_end_date.is_(None),
                )
            )
            .values(assignment_end_date=item.effectiveDate)
        )
        await session.execute(
            assignment_history.insert().values(
                employee_id=employee_id,
                branch_id=item.branchId,
                department_id=item.departmentId,
                designation_id=item.designationId,
                reporting_manager_id=item.reportingManagerId,
                assignment_start_date=item.effectiveDate,
            )
        )
        await session.execute(
            update(employees)
            .where(employees.c.id == employee_id)
            .values(
                branch_id=item.branchId,
                department_id=item.departmentId,
                designation_id=item.designationId,
                reporting_manager_id=item.reportingManagerId,
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="employee.assignment_changed",
            module="employees",
            entity_type="employee",
            entity_id=employee_id,
            before=before,
            after={
                "branchId": str(item.branchId),
                "departmentId": str(item.departmentId),
                "designationId": str(item.designationId),
                "reportingManagerId": str(item.reportingManagerId)
                if item.reportingManagerId
                else None,
            },
        )
        if old["status"] == "Active":
            await notify(
                session,
                {employee_id},
                "employee.assignment_changed",
                "Your employee assignment was updated",
                employee_id=employee_id,
            )
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def activate_employee(session: AsyncSession, actor: Actor, employee_id: UUID) -> None:
    require(actor, "employee.write")
    result = await session.execute(
        select(employees).where(employees.c.id == employee_id).with_for_update()
    )
    row = result.mappings().first()
    if not row or row["status"] == "Offboarded":
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    role = await session.scalar(
        select(designations.c.name).where(designations.c.id == row["designation_id"])
    )
    require_owner_for_privileged_account(actor, role)
    if row["status"] == "Active":
        raise ApiError(409, "CONFLICT", "Employee is already Active")
    if not row["branch_id"] or not row["department_id"]:
        raise ApiError(422, "INCOMPLETE_ASSIGNMENT", "Branch and Department are required")
    await session.execute(
        update(employees).where(employees.c.id == employee_id).values(status="Active")
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="employee.activated",
        module="employees",
        entity_type="employee",
        entity_id=employee_id,
        before={"status": row["status"]},
        after={"status": "Active"},
    )
    await session.commit()


async def offboard_employee(
    session: AsyncSession, actor: Actor, employee_id: UUID, last_working_date: date
) -> None:
    require(actor, "employee.write")
    from app.db.operations import asset_assignments

    row = (
        (
            await session.execute(
                select(employees).where(employees.c.id == employee_id).with_for_update()
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    role = await session.scalar(
        select(designations.c.name).where(designations.c.id == row["designation_id"])
    )
    if role == "Owner":
        raise ApiError(403, "OWNER_PROTECTED", "The Owner cannot be offboarded.")
    require_owner_for_privileged_account(actor, role)
    if row["status"] == "Offboarded":
        raise ApiError(409, "CONFLICT", "Employee is already Offboarded")
    if last_working_date > dubai_today():
        raise ApiError(
            422, "LAST_WORKING_DATE_INVALID", "The last working date cannot be in the future"
        )
    if last_working_date < row["date_of_joining"]:
        raise ApiError(
            422,
            "LAST_WORKING_DATE_INVALID",
            "The last working date cannot be before the date of joining",
        )
    issued = await session.scalar(
        select(asset_assignments.c.id).where(
            asset_assignments.c.employee_id == employee_id,
            asset_assignments.c.return_date.is_(None),
        )
    )
    if issued:
        raise ApiError(409, "ASSET_ISSUED", "Asset return required; contact Branch Admin.")
    await guard_direct_reports(
        session,
        employee_id,
        role or "",
        row["branch_id"],
        row["department_id"],
        "Offboarded",
    )
    await reconcile_teams(
        session,
        actor,
        employee_id,
        row["branch_id"],
        row["department_id"],
        role or "",
        "Offboarded",
    )
    await session.execute(
        update(assignment_history)
        .where(
            assignment_history.c.employee_id == employee_id,
            assignment_history.c.assignment_end_date.is_(None),
        )
        .values(assignment_end_date=dubai_today())
    )
    await session.execute(
        update(employees)
        .where(employees.c.id == employee_id)
        .values(status="Offboarded", last_working_date=last_working_date)
    )
    account_id = await session.scalar(
        select(user_accounts.c.id).where(user_accounts.c.employee_id == employee_id)
    )
    if account_id:
        await disable_account_in_transaction(session, account_id)
        await audit.record(
            session,
            actor=actor.employee_id,
            action="user.disabled",
            module="users",
            entity_type="user_account",
            entity_id=account_id,
            after={"accessStatus": "Disabled"},
        )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="employee.offboarded",
        module="employees",
        entity_type="employee",
        entity_id=employee_id,
        before={"status": row["status"]},
        after={"status": "Offboarded", "lastWorkingDate": last_working_date.isoformat()},
    )
    await access_changed(session, "employee.offboarded", employee_id)
    await session.commit()


async def record_last_working_date(
    session: AsyncSession, actor: Actor, employee_id: UUID, last_working_date: date, reason: str
) -> None:
    """Owner-only recording of a last working date missing from an already Offboarded employee."""
    require(actor, "employee.write")
    if actor.designation != "Owner":
        raise ApiError(403, "FORBIDDEN", "Only the Owner can record a missing last working date")
    row = (
        (
            await session.execute(
                select(employees).where(employees.c.id == employee_id).with_for_update()
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if row["status"] != "Offboarded":
        raise ApiError(
            409, "EMPLOYEE_NOT_OFFBOARDED", "A last working date is recorded only when Offboarded"
        )
    if row["last_working_date"] is not None:
        raise ApiError(
            409, "LAST_WORKING_DATE_RECORDED", "The last working date is already recorded"
        )
    if last_working_date > dubai_today():
        raise ApiError(
            422, "LAST_WORKING_DATE_INVALID", "The last working date cannot be in the future"
        )
    if last_working_date < row["date_of_joining"]:
        raise ApiError(
            422,
            "LAST_WORKING_DATE_INVALID",
            "The last working date cannot be before the date of joining",
        )
    await session.execute(
        update(employees)
        .where(employees.c.id == employee_id, employees.c.last_working_date.is_(None))
        .values(last_working_date=last_working_date)
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="employee.last_working_date_recorded",
        module="employees",
        entity_type="employee",
        entity_id=employee_id,
        before={"lastWorkingDate": None},
        after={"lastWorkingDate": last_working_date.isoformat(), "reason": reason},
    )
    await session.commit()


async def disable_account_in_transaction(session: AsyncSession, account_id: UUID) -> None:
    from app.db.organization import password_tokens, sessions

    now = utcnow()
    await session.execute(
        update(user_accounts)
        .where(user_accounts.c.id == account_id)
        .values(access_status="Disabled")
    )
    await session.execute(
        update(password_tokens)
        .where(password_tokens.c.account_id == account_id, password_tokens.c.used_at.is_(None))
        .values(invalidated_at=now)
    )
    await session.execute(
        update(sessions)
        .where(sessions.c.account_id == account_id, sessions.c.invalidated_at.is_(None))
        .values(invalidated_at=now)
    )
