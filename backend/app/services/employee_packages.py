"""Append-only, effective-dated employee salary packages."""

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.hr_records import employee_packages
from app.errors import ApiError
from app.policies import Actor
from app.schemas.hr_records import PackageInput
from app.services.hr_common import dubai_today, iso, names, scoped_employee
from app.services.idempotency import claim, complete
from app.whole_numbers import whole_text

AUDITED = (
    "effectiveDate",
    "basicSalaryAed",
    "housingAllowanceAed",
    "transportAllowanceAed",
    "otherAllowanceLabel",
    "otherAllowanceAed",
    "totalMonthlyAed",
    "changeReason",
)


def _out(row: dict, people: dict[UUID, str]) -> dict:
    return {
        "id": str(row["id"]),
        "effectiveDate": iso(row["effective_date"]),
        "basicSalaryAed": whole_text(row["basic_salary_aed"]),
        "housingAllowanceAed": whole_text(row["housing_allowance_aed"]),
        "transportAllowanceAed": whole_text(row["transport_allowance_aed"]),
        "otherAllowanceLabel": row["other_allowance_label"],
        "otherAllowanceAed": whole_text(row["other_allowance_aed"]),
        "totalMonthlyAed": whole_text(row["total_monthly_aed"]),
        "changeReason": row["change_reason"],
        "createdByName": people.get(row["created_by_employee_id"]),
        "createdAt": iso(row["created_at"]),
    }


async def _versions(session: AsyncSession, employee_id: UUID) -> list[dict]:
    rows = await session.execute(
        select(employee_packages)
        .where(employee_packages.c.employee_id == employee_id)
        .order_by(employee_packages.c.effective_date.desc())
    )
    return [dict(row) for row in rows.mappings()]


def applicable(versions: list[dict], on: date) -> dict | None:
    """The version in effect on a Dubai date: the latest effective on or before it."""
    return next((row for row in versions if row["effective_date"] <= on), None)


async def package_on(session: AsyncSession, employee_id: UUID, on: date) -> dict | None:
    return applicable(await _versions(session, employee_id), on)


async def list_packages(session: AsyncSession, actor: Actor, employee_id: UUID) -> dict:
    await scoped_employee(session, actor, employee_id, "package.read")
    versions = await _versions(session, employee_id)
    people = await names(session, {row["created_by_employee_id"] for row in versions})
    today = dubai_today()
    current = applicable(versions, today)
    return {
        "current": _out(current, people) if current else None,
        "upcoming": [
            _out(row, people) for row in reversed(versions) if row["effective_date"] > today
        ],
        "history": [
            _out(row, people)
            for row in versions
            if row["effective_date"] <= today and row is not current
        ],
        "canManage": "package.write" in actor.grants,
    }


async def applicable_package(
    session: AsyncSession, actor: Actor, employee_id: UUID, on: date
) -> dict | None:
    await scoped_employee(session, actor, employee_id, "package.read")
    row = await package_on(session, employee_id, on)
    if row is None:
        return None
    return _out(row, await names(session, {row["created_by_employee_id"]}))


async def add_package(
    session: AsyncSession, actor: Actor, employee_id: UUID, item: PackageInput, key: str
) -> dict:
    try:
        employee = await scoped_employee(session, actor, employee_id, "package.write", lock=True)
        token, replay = await claim(
            session,
            actor,
            "package.add",
            key,
            {"employeeId": str(employee_id), **item.model_dump(mode="json")},
        )
        if replay is not None:
            await session.rollback()
            return replay
        if employee["status"] == "Offboarded":
            raise ApiError(
                409, "EMPLOYEE_OFFBOARDED", "Packages cannot be added for an Offboarded employee"
            )
        prior = await session.scalar(
            select(employee_packages.c.id).where(
                employee_packages.c.employee_id == employee_id,
                employee_packages.c.effective_date == item.effectiveDate,
            )
        )
        if prior is not None:
            raise ApiError(
                409, "PACKAGE_DATE_EXISTS", "A package version already exists for this date"
            )
        total = (
            item.basicSalaryAed
            + (item.housingAllowanceAed or 0)
            + (item.transportAllowanceAed or 0)
            + (item.otherAllowanceAed or 0)
        )
        record_id = uuid4()
        values = {
            "id": record_id,
            "employee_id": employee_id,
            "effective_date": item.effectiveDate,
            "basic_salary_aed": item.basicSalaryAed,
            "housing_allowance_aed": item.housingAllowanceAed,
            "transport_allowance_aed": item.transportAllowanceAed,
            "other_allowance_label": item.otherAllowanceLabel,
            "other_allowance_aed": item.otherAllowanceAed,
            "total_monthly_aed": total,
            "change_reason": item.changeReason,
            "created_by_employee_id": actor.employee_id,
        }
        await session.execute(employee_packages.insert().values(**values))
        row = (
            (
                await session.execute(
                    select(employee_packages).where(employee_packages.c.id == record_id)
                )
            )
            .mappings()
            .one()
        )
        response = _out(dict(row), {actor.employee_id: actor.display_name})
        await audit.record(
            session,
            actor=actor.employee_id,
            action="package.version_added",
            module="hr_records",
            entity_type="employee_package",
            entity_id=record_id,
            after={"employeeId": str(employee_id), **{k: response[k] for k in AUDITED}},
        )
        await complete(session, token, 201, response)
        await session.commit()
        return response
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(
            409, "PACKAGE_DATE_EXISTS", "A package version already exists for this date"
        ) from exc
    except Exception:
        await session.rollback()
        raise
