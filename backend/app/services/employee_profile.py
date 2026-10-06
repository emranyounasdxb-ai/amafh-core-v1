"""HR/Owner employee identity updates without changing protected identifiers."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.organization import designations, employees, user_accounts
from app.errors import ApiError
from app.policies import Actor, require
from app.schemas.organization import EmployeeProfileUpdate
from app.services import login_email
from app.services.privileged_access import require_owner_for_privileged_account

FIELD_MAP = {
    "fullName": "full_name",
    "mobile": "mobile",
    "personalEmail": "personal_email",
    "nationality": "nationality",
    "gender": "gender",
    "maritalStatus": "marital_status",
    "passportNumber": "passport_number",
    "emiratesIdNumber": "emirates_id_number",
}


async def update_profile(
    session: AsyncSession, actor: Actor, employee_id: UUID, item: EmployeeProfileUpdate
) -> None:
    require(actor, "employee.write")
    fields = item.model_fields_set
    if not fields:
        raise ApiError(422, "VALIDATION_ERROR", "No fields supplied")
    values = {FIELD_MAP[field]: getattr(item, field) for field in fields}
    required = set(FIELD_MAP.values()) - {"emirates_id_number"}
    if any(value is None for key, value in values.items() if key in required):
        raise ApiError(422, "VALIDATION_ERROR", "Required fields cannot be cleared")
    if values.get("gender", "Male") not in {"Male", "Female"}:
        raise ApiError(422, "VALIDATION_ERROR", "Invalid Gender")
    if values.get("marital_status", "Single") not in {"Single", "Married"}:
        raise ApiError(422, "VALIDATION_ERROR", "Invalid Marital Status")
    if "personal_email" in values:
        values["personal_email"] = str(values["personal_email"]).lower()
    row = (
        (
            await session.execute(
                select(employees).where(employees.c.id == employee_id).with_for_update()
            )
        )
        .mappings()
        .first()
    )
    if not row or row["status"] == "Offboarded":
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if "personal_email" in values:
        target_role = await session.scalar(
            select(designations.c.name).where(designations.c.id == row["designation_id"])
        )
        require_owner_for_privileged_account(actor, target_role)
    if "personal_email" in values and await session.scalar(
        select(user_accounts.c.id).where(
            user_accounts.c.employee_id == employee_id,
            user_accounts.c.access_status != "Disabled",
        )
    ):
        await login_email.guard_unique(session, values["personal_email"], employee_id)
    before = {field: row[FIELD_MAP[field]] for field in sorted(fields)}
    after = {field: values[FIELD_MAP[field]] for field in sorted(fields)}
    await session.execute(update(employees).where(employees.c.id == employee_id).values(**values))
    await audit.record(
        session,
        actor=actor.employee_id,
        action="employee.profile_updated",
        module="employees",
        entity_type="employee",
        entity_id=employee_id,
        context={"changedFields": sorted(fields)},
        before=before,
        after=after,
    )
    await session.commit()
