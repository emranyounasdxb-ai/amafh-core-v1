"""Customer views derived only from the requester's Case scope."""

from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.cases import cases, company_customers, customers, individual_customers
from app.errors import ApiError
from app.policies import Actor, require
from app.repositories.case_scope import case_access, visible_case
from app.whole_numbers import whole_text


def _authorized_customer(actor: Actor, scope=visible_case):
    return exists(select(cases.c.id).where(cases.c.customer_id == customers.c.id, scope(actor)))


async def list_customers(
    session: AsyncSession,
    actor: Actor,
    *,
    page: int,
    page_size: int,
    customer_type: str | None = None,
    q: str = "",
    sort: str = "createdAt",
    direction: str = "desc",
    for_creation: bool = False,
) -> dict:
    require(actor, "case.create" if for_creation else "case.read")
    predicates = [_authorized_customer(actor, case_access if for_creation else visible_case)]
    if customer_type:
        if customer_type not in {"Individual", "Company"}:
            raise ApiError(422, "INVALID_FILTER", "Invalid Customer type")
        predicates.append(customers.c.customer_type == customer_type)
    individual = customers.outerjoin(
        individual_customers,
        and_(
            individual_customers.c.customer_id == customers.c.id,
            customers.c.customer_type == "Individual",
        ),
    )
    customer_details = individual.outerjoin(
        company_customers,
        and_(
            company_customers.c.customer_id == customers.c.id,
            customers.c.customer_type == "Company",
        ),
    )
    name = func.coalesce(individual_customers.c.full_name, company_customers.c.company_name)
    mobile = func.coalesce(individual_customers.c.mobile, company_customers.c.mobile)
    email = func.coalesce(individual_customers.c.email, company_customers.c.email)
    eid_or_tl = func.coalesce(individual_customers.c.emirates_id, company_customers.c.trade_license)
    term = q.strip()
    if term:
        pattern = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        predicates.append(
            or_(
                customers.c.customer_id.ilike(pattern, escape="\\"),
                customers.c.customer_type.ilike(pattern, escape="\\"),
                name.ilike(pattern, escape="\\"),
                mobile.ilike(pattern, escape="\\"),
                email.ilike(pattern, escape="\\"),
                eid_or_tl.ilike(pattern, escape="\\"),
                individual_customers.c.passport_number.ilike(pattern, escape="\\"),
                company_customers.c.contact_person.ilike(pattern, escape="\\"),
            )
        )
    order = {
        "createdAt": customers.c.created_at,
        "customerId": customers.c.customer_id,
        "type": customers.c.customer_type,
        "name": name,
        "nationality": individual_customers.c.nationality,
        "salaryAed": customers.c.salary_aed,
        "emiratesId": individual_customers.c.emirates_id,
        "passportNumber": individual_customers.c.passport_number,
        "employer": individual_customers.c.employer,
        "tradeLicense": company_customers.c.trade_license,
        "contactPerson": company_customers.c.contact_person,
        "mobile": mobile,
        "email": email,
        "eidOrTl": eid_or_tl,
    }.get(sort)
    if order is None or direction not in {"asc", "desc"}:
        raise ApiError(422, "INVALID_SORT", "Unsupported Customer sort")
    total = await session.scalar(
        select(func.count()).select_from(customer_details).where(*predicates)
    )
    rows = (
        await session.execute(
            select(
                customers.c.id,
                customers.c.customer_id,
                customers.c.customer_type,
                customers.c.created_at,
                customers.c.salary_aed,
                name.label("name"),
                individual_customers.c.nationality,
                individual_customers.c.emirates_id.label("emiratesId"),
                individual_customers.c.passport_number.label("passportNumber"),
                individual_customers.c.employer,
                company_customers.c.trade_license.label("tradeLicense"),
                company_customers.c.contact_person.label("contactPerson"),
                mobile.label("mobile"),
                email.label("email"),
            )
            .select_from(customer_details)
            .where(*predicates)
            .order_by(
                (order.asc() if direction == "asc" else order.desc()).nulls_last(),
                customers.c.id,
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).mappings()
    return {
        "items": [
            {
                "id": str(row["id"]),
                "customerId": row["customer_id"],
                "type": row["customer_type"],
                "name": row["name"],
                "nationality": row["nationality"],
                "salaryAed": whole_text(row["salary_aed"])
                if row["salary_aed"] is not None
                else None,
                "emiratesId": row["emiratesId"],
                "passportNumber": row["passportNumber"],
                "employer": row["employer"],
                "tradeLicense": row["tradeLicense"],
                "contactPerson": row["contactPerson"],
                "mobile": row["mobile"],
                "email": row["email"],
                "createdAt": row["created_at"].isoformat(),
            }
            for row in rows
        ],
        "page": page,
        "pageSize": page_size,
        "total": total or 0,
    }


async def get_customer(session: AsyncSession, actor: Actor, customer_id: UUID) -> dict:
    row = (
        (
            await session.execute(
                select(customers).where(
                    customers.c.id == customer_id, _authorized_customer(actor, case_access)
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    table = individual_customers if row["customer_type"] == "Individual" else company_customers
    detail = (
        (await session.execute(select(table).where(table.c.customer_id == customer_id)))
        .mappings()
        .one()
    )
    related = (
        await session.execute(
            select(cases.c.id, cases.c.internal_case_id)
            .where(cases.c.customer_id == customer_id, case_access(actor))
            .order_by(cases.c.created_at.desc())
        )
    ).mappings()
    return {
        "id": str(row["id"]),
        "customerId": row["customer_id"],
        "type": row["customer_type"],
        "salaryAed": whole_text(row["salary_aed"]) if row["salary_aed"] is not None else None,
        "identity": {
            key: str(value) if isinstance(value, UUID) else value
            for key, value in detail.items()
            if key not in {"id", "customer_id"}
        },
        "cases": [
            {"id": str(case["id"]), "internalCaseId": case["internal_case_id"]} for case in related
        ],
    }
