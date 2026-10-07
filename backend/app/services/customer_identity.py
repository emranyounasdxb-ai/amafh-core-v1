"""Case-transaction Customer matching and Owner identity correction."""

from uuid import UUID, uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.cases import company_customers, customers, individual_customers
from app.errors import ApiError
from app.normalization import identifier
from app.policies import Actor, require
from app.schemas.cases import CustomerInput, IdentityCorrection
from app.whole_numbers import whole_text


async def _identity_locks(session: AsyncSession, keys: list[str]) -> None:
    for key in sorted(set(keys)):
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
        )


def _canonical(column):
    return func.upper(func.regexp_replace(func.btrim(column), "[[:space:]]+", " ", "g"))


async def match_or_create(
    session: AsyncSession, item: CustomerInput, actor: Actor
) -> tuple[UUID, bool]:
    if item.type == "Individual":
        assert item.emiratesId and item.passportNumber and item.fullName and item.employer
        await _identity_locks(
            session, [f"customer:eid:{item.emiratesId}", f"customer:passport:{item.passportNumber}"]
        )
        by_eid = (
            (
                await session.execute(
                    select(individual_customers)
                    .where(_canonical(individual_customers.c.emirates_id) == item.emiratesId)
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        by_passport = (
            (
                await session.execute(
                    select(individual_customers)
                    .where(
                        _canonical(individual_customers.c.passport_number) == item.passportNumber
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if by_eid and by_passport and by_eid["customer_id"] != by_passport["customer_id"]:
            raise ApiError(
                409, "CUSTOMER_IDENTITY_CONFLICT", "Customer identity needs Owner review"
            )
        match = by_eid or by_passport
        if match:
            if (
                identifier(match["emirates_id"]) != item.emiratesId
                or identifier(match["passport_number"]) != item.passportNumber
            ):
                raise ApiError(
                    409, "CUSTOMER_IDENTITY_CONFLICT", "Customer identity needs Owner review"
                )
            current_salary = await session.scalar(
                select(customers.c.salary_aed)
                .where(customers.c.id == match["customer_id"])
                .with_for_update()
            )
            before = {
                "salaryAed": whole_text(current_salary) if current_salary is not None else None,
                "nationality": match["nationality"],
            }
            after = {
                "salaryAed": whole_text(item.salaryAed) if item.salaryAed is not None else None,
                "nationality": item.nationality,
            }
            if before != after:
                await session.execute(
                    update(customers)
                    .where(customers.c.id == match["customer_id"])
                    .values(salary_aed=item.salaryAed)
                )
                await session.execute(
                    update(individual_customers)
                    .where(individual_customers.c.customer_id == match["customer_id"])
                    .values(nationality=item.nationality)
                )
                await audit.record(
                    session,
                    actor=actor.employee_id,
                    action="customer.profile_updated",
                    module="customers",
                    entity_type="customer",
                    entity_id=match["customer_id"],
                    before=before,
                    after=after,
                    context={"source": "case_creation"},
                )
            return match["customer_id"], True
        customer_id = uuid4()
        await session.execute(
            customers.insert().values(
                id=customer_id,
                customer_id=f"CUS-{uuid4().hex.upper()}",
                customer_type="Individual",
                salary_aed=item.salaryAed,
            )
        )
        await session.execute(
            individual_customers.insert().values(
                id=uuid4(),
                customer_id=customer_id,
                emirates_id=item.emiratesId,
                passport_number=item.passportNumber,
                full_name=item.fullName,
                nationality=item.nationality,
                employer=item.employer,
                mobile=item.mobile,
                email=str(item.email).lower(),
            )
        )
        return customer_id, False
    assert item.tradeLicense and item.companyName and item.contactPerson
    await _identity_locks(session, [f"customer:license:{item.tradeLicense}"])
    match = (
        (
            await session.execute(
                select(company_customers)
                .where(_canonical(company_customers.c.trade_license) == item.tradeLicense)
                .with_for_update()
            )
        )
        .mappings()
        .one_or_none()
    )
    if match:
        return match["customer_id"], True
    customer_id = uuid4()
    await session.execute(
        customers.insert().values(
            id=customer_id,
            customer_id=f"CUS-{uuid4().hex.upper()}",
            customer_type="Company",
        )
    )
    await session.execute(
        company_customers.insert().values(
            id=uuid4(),
            customer_id=customer_id,
            company_name=item.companyName,
            contact_person=item.contactPerson,
            trade_license=item.tradeLicense,
            mobile=item.mobile,
            email=str(item.email).lower(),
        )
    )
    return customer_id, False


async def correct_identity(
    session: AsyncSession,
    actor: Actor,
    customer_id: UUID,
    item: IdentityCorrection,
) -> None:
    require(actor, "customer.correct")
    try:
        customer = (
            (
                await session.execute(
                    select(customers).where(customers.c.id == customer_id).with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if customer is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        if customer["customer_type"] == "Individual":
            if item.tradeLicense is not None or (
                item.emiratesId is None and item.passportNumber is None
            ):
                raise ApiError(422, "INVALID_CORRECTION", "Correct Individual identity fields only")
            table = individual_customers
            values = {
                k: v
                for k, v in {
                    "emirates_id": item.emiratesId,
                    "passport_number": item.passportNumber,
                }.items()
                if v is not None
            }
            keys = [
                f"customer:eid:{item.emiratesId}" if item.emiratesId else "",
                f"customer:passport:{item.passportNumber}" if item.passportNumber else "",
            ]
        else:
            if (
                item.tradeLicense is None
                or item.emiratesId is not None
                or item.passportNumber is not None
            ):
                raise ApiError(422, "INVALID_CORRECTION", "Correct Company Trade License only")
            table = company_customers
            values = {"trade_license": item.tradeLicense}
            keys = [f"customer:license:{item.tradeLicense}"]
        await _identity_locks(session, [key for key in keys if key])
        detail = (
            (
                await session.execute(
                    select(table).where(table.c.customer_id == customer_id).with_for_update()
                )
            )
            .mappings()
            .one()
        )
        before = {key: detail[key] for key in values}
        if before == values:
            raise ApiError(409, "UNCHANGED", "Identity is unchanged")
        await session.execute(
            update(table).where(table.c.customer_id == customer_id).values(**values)
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="customer.identity_corrected",
            module="customers",
            entity_type="customer",
            entity_id=customer_id,
            before=before,
            after=values,
            context={"reason": item.reason},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
