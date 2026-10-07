"""Salary-filtered Variant choices and authoritative creation checks."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.cases import bank_product_mappings, banks, product_types, product_variants
from app.errors import ApiError
from app.policies import Actor, require
from app.whole_numbers import whole_text


def validate_salary_criteria(variant, salary: Decimal | None) -> None:
    if salary is None:
        raise ApiError(
            422,
            "SALARY_REQUIRED",
            "Enter the Customer salary before selecting a Variant",
            {"customer.salaryAed": ["Customer salary is required"]},
        )
    minimum, maximum = variant["minimum_salary_aed"], variant["maximum_salary_aed"]
    if minimum is None or maximum is None:
        raise ApiError(
            422,
            "VARIANT_SALARY_UNCONFIGURED",
            "Configure this Variant's salary range in Settings",
            {"productVariantId": ["This Variant has no configured salary range"]},
        )
    if not minimum <= salary <= maximum:
        raise ApiError(
            422,
            "VARIANT_SALARY_INELIGIBLE",
            "Selected Variant does not match the Customer salary",
            {"productVariantId": ["Select a Variant eligible for this salary"]},
        )


async def eligible_variants(
    session: AsyncSession,
    actor: Actor,
    bank_id: UUID,
    product_id: UUID,
    salary: Decimal | None,
    customer_type: str,
) -> dict:
    require(actor, "case.create")
    if customer_type == "Individual" and salary is None:
        raise ApiError(
            422,
            "SALARY_REQUIRED",
            "Enter salary before determining eligibility",
            {"salaryAed": ["Salary is required"]},
        )
    if customer_type == "Company" and salary is not None:
        raise ApiError(
            422,
            "SALARY_NOT_APPLICABLE",
            "Company Cases do not use salary eligibility",
            {"salaryAed": ["Salary is not applicable to Company customers"]},
        )
    context = await session.scalar(
        select(product_types.c.code)
        .select_from(
            bank_product_mappings.join(banks, bank_product_mappings.c.bank_id == banks.c.id).join(
                product_types, bank_product_mappings.c.product_type_id == product_types.c.id
            )
        )
        .where(
            banks.c.id == bank_id,
            product_types.c.id == product_id,
            banks.c.active.is_(True),
            product_types.c.active.is_(True),
            bank_product_mappings.c.active.is_(True),
        )
    )
    if context != "CC":
        raise ApiError(
            422,
            "INVALID_PRODUCT_CONTEXT",
            "Choose an active Credit Card Bank/Product relationship",
            {"bankId": ["Bank/Product relationship is unavailable"]},
        )
    rows = (
        (
            await session.execute(
                select(product_variants)
                .where(
                    product_variants.c.bank_id == bank_id,
                    product_variants.c.product_type_id == product_id,
                    product_variants.c.active.is_(True),
                )
                .order_by(product_variants.c.name, product_variants.c.id)
            )
        )
        .mappings()
        .all()
    )
    applicable = customer_type == "Individual"
    if applicable:
        assert salary is not None
    configured = [
        row
        for row in rows
        if row["minimum_salary_aed"] is not None and row["maximum_salary_aed"] is not None
    ]
    eligible = (
        [
            row
            for row in configured
            if row["minimum_salary_aed"] <= salary <= row["maximum_salary_aed"]
        ]
        if applicable
        else rows
    )
    return {
        "items": [
            {
                key: str(value)
                if isinstance(value, UUID)
                else whole_text(value)
                if isinstance(value, Decimal)
                else value
                for key, value in row.items()
            }
            for row in eligible
        ],
        "salaryCriteriaApplicable": applicable,
        "missingCriteriaCount": len(rows) - len(configured),
        "configuredCount": len(configured),
        "totalVariantsCount": len(rows),
    }
