"""One-time local Owner enrollment; never persists a readable credential."""

from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.config import settings
from app.db.base import utcnow
from app.db.organization import (
    designations,
    employees,
    password_tokens,
    user_accounts,
)
from app.errors import ApiError
from app.identifiers import new_system_employee_code
from app.schemas.organization import EmployeeCreate
from app.security import new_token, token_digest
from app.services import login_email


async def enroll(session: AsyncSession, item: EmployeeCreate, email: str) -> tuple[UUID, str, str]:
    """Create the first Owner and its setup link in one guarded transaction."""
    if (
        item.branchId is not None
        or item.departmentId is not None
        or item.reportingManagerId is not None
    ):
        raise ApiError(422, "INVALID_OWNER", "The global Owner cannot have an assignment")
    try:
        # Serialize competing local bootstrap commands, including the empty-database case.
        await session.execute(text("SELECT pg_advisory_xact_lock(460973423019)"))
        owner_role_id = await session.scalar(
            select(designations.c.id).where(
                designations.c.name == "Owner", designations.c.locked.is_(True)
            )
        )
        if owner_role_id is None or item.designationId != owner_role_id:
            raise ApiError(422, "INVALID_OWNER", "Locked Owner designation required")
        existing = await session.scalar(
            select(func.count())
            .select_from(employees)
            .where(employees.c.designation_id == owner_role_id)
        )
        owner_accounts = await session.scalar(
            select(func.count())
            .select_from(user_accounts.join(employees))
            .where(employees.c.designation_id == owner_role_id)
        )
        if existing or owner_accounts:
            raise ApiError(409, "OWNER_EXISTS", "Owner enrollment is already complete")
        employee_id, account_id = uuid4(), uuid4()
        email = login_email.validate(email)
        await login_email.guard_unique(session, email, employee_id)
        code, raw_token, now = await new_system_employee_code(session), new_token(), utcnow()
        await session.execute(
            employees.insert().values(
                id=employee_id,
                system_employee_code=code,
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
                designation_id=owner_role_id,
                branch_id=None,
                department_id=None,
                status="Active",
            )
        )
        await session.execute(
            user_accounts.insert().values(
                id=account_id,
                employee_id=employee_id,
                access_status="Not Provisioned",
                login_email=email,
            )
        )
        await session.execute(
            password_tokens.insert().values(
                account_id=account_id,
                kind="setup",
                token_hash=token_digest(raw_token),
                generated_by_employee_id=employee_id,
                expires_at=now + timedelta(hours=24),
            )
        )
        await audit.record(
            session,
            actor=None,
            action="owner.bootstrap_enrolled",
            module="security",
            entity_type="employee",
            entity_id=employee_id,
            after={"accountStatus": "Not Provisioned"},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    link = f"{str(settings().public_origin).rstrip('/')}/setup-password?token={raw_token}"
    return employee_id, code, link
