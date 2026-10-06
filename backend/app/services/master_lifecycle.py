"""Audited lifecycle for organization masters; referenced history stays intact."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.attendance import office_timings
from app.db.organization import branches, business_units, departments, employees, teams
from app.errors import ApiError
from app.policies import Actor, require
from app.services.department_products import require_target_product, require_unreferenced


async def _row(session: AsyncSession, table, record_id: UUID):
    return (
        (await session.execute(select(table).where(table.c.id == record_id).with_for_update()))
        .mappings()
        .first()
    )


async def update_master(
    session: AsyncSession, actor: Actor, table, record_id: UUID, values: dict
) -> None:
    require(actor, "organization.write")
    if table not in (business_units, branches, departments) or not values:
        raise ApiError(422, "VALIDATION_ERROR", "No approved master fields supplied")
    row = await _row(session, table, record_id)
    if not row or not row["active"]:
        raise ApiError(404, "NOT_FOUND", "Active master unavailable")
    if "business_unit_id" in values and values["business_unit_id"] is not None:
        unit = await session.scalar(
            select(business_units.c.id).where(
                business_units.c.id == values["business_unit_id"],
                business_units.c.active.is_(True),
            )
        )
        if not unit:
            raise ApiError(422, "INVALID_BUSINESS_UNIT", "Active Business Unit required")
    if "product_type_id" in values:
        if table is not departments:
            raise ApiError(422, "VALIDATION_ERROR", "No approved master fields supplied")
        if values["product_type_id"] == row["product_type_id"]:
            del values["product_type_id"]
        else:
            if values["product_type_id"] is not None:
                await require_target_product(session, values["product_type_id"])
            await require_unreferenced(session, record_id)
    if "operating_city" in values:
        if table is not branches:
            raise ApiError(422, "VALIDATION_ERROR", "No approved master fields supplied")
        if values["operating_city"] == row["operating_city"]:
            del values["operating_city"]
        elif await session.scalar(
            select(office_timings.c.id).where(office_timings.c.branch_id == record_id)
        ):
            raise ApiError(
                409,
                "BRANCH_CITY_LOCKED",
                "This Branch has Office Timings, so its operating city cannot change",
            )
    before = {key: str(row[key]) if isinstance(row[key], UUID) else row[key] for key in values}
    after = {key: str(value) if isinstance(value, UUID) else value for key, value in values.items()}
    try:
        await session.execute(update(table).where(table.c.id == record_id).values(**values))
        await audit.record(
            session,
            actor=actor.employee_id,
            action=f"{table.name}.updated",
            module="organization",
            entity_type=table.name,
            entity_id=record_id,
            before=before,
            after=after,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def activate_master(session: AsyncSession, actor: Actor, table, record_id: UUID) -> None:
    require(actor, "organization.write")
    if table not in (business_units, branches, departments):
        raise ApiError(422, "VALIDATION_ERROR", "Invalid master")
    row = await _row(session, table, record_id)
    if not row or row["active"]:
        raise ApiError(404, "NOT_FOUND", "Inactive master unavailable")
    if table is branches and row["business_unit_id"] is not None:
        parent = await session.scalar(
            select(business_units.c.active).where(business_units.c.id == row["business_unit_id"])
        )
        if not parent:
            raise ApiError(409, "PARENT_INACTIVE", "Activate the Business Unit first")
    if table is departments:
        parent = await session.scalar(
            select(branches.c.active).where(branches.c.id == row["branch_id"])
        )
        if not parent:
            raise ApiError(409, "PARENT_INACTIVE", "Activate the Branch first")
    try:
        await session.execute(update(table).where(table.c.id == record_id).values(active=True))
        await audit.record(
            session,
            actor=actor.employee_id,
            action=f"{table.name}.activated",
            module="organization",
            entity_type=table.name,
            entity_id=record_id,
            before={"active": False},
            after={"active": True},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def deactivate_master(session: AsyncSession, actor: Actor, table, record_id: UUID) -> None:
    require(actor, "organization.write")
    if table not in (business_units, branches, departments):
        raise ApiError(422, "VALIDATION_ERROR", "Invalid master")
    row = await _row(session, table, record_id)
    if not row or not row["active"]:
        raise ApiError(404, "NOT_FOUND", "Active master unavailable")
    if table is business_units:
        in_use = await session.scalar(
            select(branches.c.id).where(
                branches.c.business_unit_id == record_id, branches.c.active.is_(True)
            )
        )
    elif table is branches:
        in_use = await session.scalar(
            select(departments.c.id).where(
                departments.c.branch_id == record_id, departments.c.active.is_(True)
            )
        ) or await session.scalar(
            select(employees.c.id).where(
                employees.c.branch_id == record_id, employees.c.status == "Active"
            )
        )
    else:
        in_use = await session.scalar(
            select(employees.c.id).where(
                employees.c.department_id == record_id, employees.c.status == "Active"
            )
        ) or await session.scalar(
            select(teams.c.id).where(teams.c.department_id == record_id, teams.c.active.is_(True))
        )
    if in_use:
        raise ApiError(409, "MASTER_IN_USE", "Active records must be reassigned first")
    try:
        await session.execute(update(table).where(table.c.id == record_id).values(active=False))
        await audit.record(
            session,
            actor=actor.employee_id,
            action=f"{table.name}.deactivated",
            module="organization",
            entity_type=table.name,
            entity_id=record_id,
            before={"active": True},
            after={"active": False},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
