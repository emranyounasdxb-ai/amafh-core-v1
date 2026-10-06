"""Effective-dated, immutable Financial Rule versions."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.cases import bank_product_mappings, banks, product_types, product_variants
from app.db.operations import financial_rules
from app.errors import ApiError
from app.policies import Actor, require
from app.schemas.finance import FinancialRuleInput


def _public(row) -> dict:
    result = {}
    for key, value in dict(row).items():
        if isinstance(value, (UUID, Decimal)):
            value = str(value)
        elif isinstance(value, date):
            value = value.isoformat()
        result[key] = value
    return result


async def _validate_context(session: AsyncSession, item: FinancialRuleInput) -> None:
    bank = await session.scalar(
        select(banks.c.id)
        .where(banks.c.id == item.bankId, banks.c.active.is_(True))
        .with_for_update(read=True)
    )
    product = (
        (
            await session.execute(
                select(product_types)
                .where(
                    product_types.c.id == item.productTypeId,
                    product_types.c.active.is_(True),
                )
                .with_for_update(read=True)
            )
        )
        .mappings()
        .one_or_none()
    )
    mapping = await session.scalar(
        select(bank_product_mappings.c.id)
        .where(
            bank_product_mappings.c.bank_id == item.bankId,
            bank_product_mappings.c.product_type_id == item.productTypeId,
            bank_product_mappings.c.active.is_(True),
        )
        .with_for_update()
    )
    if bank is None or product is None or mapping is None:
        raise ApiError(422, "INACTIVE_CONFIGURATION", "Bank and Product mapping are unavailable")
    if item.productVariantId is not None:
        if product["code"] != "CC":
            raise ApiError(422, "INVALID_RULE_CONTEXT", "CC Variant requires the CC Product")
        variant = await session.scalar(
            select(product_variants.c.id)
            .where(
                product_variants.c.id == item.productVariantId,
                product_variants.c.bank_id == item.bankId,
                product_variants.c.product_type_id == item.productTypeId,
                product_variants.c.active.is_(True),
            )
            .with_for_update(read=True)
        )
        if variant is None:
            raise ApiError(422, "INACTIVE_CONFIGURATION", "CC Variant is unavailable")
    elif product["code"] != "PF":
        raise ApiError(422, "INVALID_RULE_CONTEXT", "PF slab requires the PF Product")


async def _active_conflict(session: AsyncSession, item: FinancialRuleInput) -> bool:
    conditions = [
        financial_rules.c.bank_id == item.bankId,
        financial_rules.c.product_type_id == item.productTypeId,
        financial_rules.c.active.is_(True),
    ]
    if item.productVariantId is not None:
        conditions.append(financial_rules.c.product_variant_id == item.productVariantId)
    else:
        conditions += [
            financial_rules.c.product_variant_id.is_(None),
            financial_rules.c.pf_amount_min <= item.pfAmountMax,
            financial_rules.c.pf_amount_max >= item.pfAmountMin,
        ]
    return await session.scalar(select(financial_rules.c.id).where(*conditions)) is not None


async def _insert(session: AsyncSession, actor: Actor, item: FinancialRuleInput, rule_id: UUID):
    values = dict(
        id=rule_id,
        bank_id=item.bankId,
        product_type_id=item.productTypeId,
        product_variant_id=item.productVariantId,
        pf_amount_min=item.pfAmountMin,
        pf_amount_max=item.pfAmountMax,
        cc_points=item.ccPoints,
        commission_aed=item.commissionAed,
        effective_date=item.effectiveDate,
        active=True,
    )
    await session.execute(financial_rules.insert().values(**values))
    await audit.record(
        session,
        actor=actor.employee_id,
        action="finance.rule_created",
        module="finance",
        entity_type="financial_rule",
        entity_id=rule_id,
        after={key: str(value) if value is not None else None for key, value in values.items()},
    )
    return {"id": str(rule_id), "active": True, "effectiveDate": item.effectiveDate.isoformat()}


async def create(session: AsyncSession, actor: Actor, item: FinancialRuleInput) -> dict:
    require(actor, "finance.write")
    try:
        await _validate_context(session, item)
        if await _active_conflict(session, item):
            raise ApiError(409, "RULE_CONFLICT", "An active Financial Rule conflicts")
        result = await _insert(session, actor, item, uuid4())
        await session.commit()
        return result
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(
            409, "RULE_CONFLICT", "Financial Rule conflicts with an existing version"
        ) from exc
    except Exception:
        await session.rollback()
        raise


async def replace(
    session: AsyncSession, actor: Actor, prior_id: UUID, item: FinancialRuleInput
) -> dict:
    require(actor, "finance.write")
    try:
        await _validate_context(session, item)
        prior = (
            (
                await session.execute(
                    select(financial_rules)
                    .where(financial_rules.c.id == prior_id)
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if prior is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        if (
            not prior["active"]
            or prior["superseded_by_rule_id"] is not None
            or prior["bank_id"] != item.bankId
            or prior["product_type_id"] != item.productTypeId
            or (prior["product_variant_id"] is not None) != (item.productVariantId is not None)
            or (
                item.productVariantId is not None
                and prior["product_variant_id"] != item.productVariantId
            )
            or item.effectiveDate <= prior["effective_date"]
        ):
            raise ApiError(409, "RULE_REPLACEMENT_INVALID", "Invalid Financial Rule replacement")
        new_id = uuid4()
        await session.execute(
            update(financial_rules).where(financial_rules.c.id == prior_id).values(active=False)
        )
        if await _active_conflict(session, item):
            raise ApiError(409, "RULE_CONFLICT", "An active Financial Rule conflicts")
        result = await _insert(session, actor, item, new_id)
        await session.execute(
            update(financial_rules)
            .where(financial_rules.c.id == prior_id)
            .values(superseded_by_rule_id=new_id)
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="finance.rule_replaced",
            module="finance",
            entity_type="financial_rule",
            entity_id=prior_id,
            before={"active": True, "supersededByRuleId": None},
            after={"active": False, "supersededByRuleId": str(new_id)},
            context={"replacementRuleId": str(new_id)},
        )
        await session.commit()
        return result
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(
            409, "RULE_CONFLICT", "Financial Rule conflicts with an existing version"
        ) from exc
    except Exception:
        await session.rollback()
        raise


async def set_active(session: AsyncSession, actor: Actor, rule_id: UUID, active: bool) -> None:
    require(actor, "finance.write")
    try:
        # Use the same mapping-then-rule lock order as create/replace.
        if active:
            context = (
                (
                    await session.execute(
                        select(financial_rules).where(financial_rules.c.id == rule_id)
                    )
                )
                .mappings()
                .one_or_none()
            )
            if context is None:
                raise ApiError(404, "NOT_FOUND", "Record unavailable")
            context_item = FinancialRuleInput(
                bankId=context["bank_id"],
                productTypeId=context["product_type_id"],
                productVariantId=context["product_variant_id"],
                pfAmountMin=context["pf_amount_min"],
                pfAmountMax=context["pf_amount_max"],
                ccPoints=context["cc_points"],
                commissionAed=context["commission_aed"],
                effectiveDate=context["effective_date"],
            )
            await _validate_context(session, context_item)
        row = (
            (
                await session.execute(
                    select(financial_rules).where(financial_rules.c.id == rule_id).with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        if row["active"] == active or (active and row["superseded_by_rule_id"] is not None):
            raise ApiError(409, "RULE_STATE_CONFLICT", "Financial Rule state cannot change")
        if active:
            if await _active_conflict(session, context_item):
                raise ApiError(409, "RULE_CONFLICT", "An active Financial Rule conflicts")
        await session.execute(
            update(financial_rules).where(financial_rules.c.id == rule_id).values(active=active)
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="finance.rule_activated" if active else "finance.rule_deactivated",
            module="finance",
            entity_type="financial_rule",
            entity_id=rule_id,
            before={"active": not active},
            after={"active": active},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def list_rules(
    session: AsyncSession,
    actor: Actor,
    *,
    page: int,
    page_size: int,
    bank_id: UUID | None,
    product_id: UUID | None,
    active: bool | None,
    sort: str | None = None,
    direction: str = "asc",
) -> dict:
    if actor.designation not in {"Owner", "Managing Director", "Finance"}:
        raise ApiError(403, "FORBIDDEN", "Access denied")
    conditions = []
    if bank_id is not None:
        conditions.append(financial_rules.c.bank_id == bank_id)
    if product_id is not None:
        conditions.append(financial_rules.c.product_type_id == product_id)
    if active is not None:
        conditions.append(financial_rules.c.active.is_(active))
    order = (
        {
            "id": financial_rules.c.id,
            "effectiveDate": financial_rules.c.effective_date,
            "ccPoints": financial_rules.c.cc_points,
            "commissionAed": financial_rules.c.commission_aed,
            "active": financial_rules.c.active,
        }.get(sort)
        if sort is not None
        else None
    )
    if (sort is not None and order is None) or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    total = await session.scalar(
        select(func.count()).select_from(financial_rules).where(*conditions)
    )
    rows = (
        await session.execute(
            select(financial_rules)
            .where(*conditions)
            .order_by(
                (order.asc() if direction == "asc" else order.desc())
                if order is not None
                else financial_rules.c.effective_date.desc(),
                financial_rules.c.created_at.desc(),
                financial_rules.c.id,
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).mappings()
    return {
        "items": [_public(row) for row in rows],
        "total": total or 0,
        "page": page,
        "pageSize": page_size,
    }


async def get_rule(session: AsyncSession, actor: Actor, rule_id: UUID) -> dict:
    if actor.designation not in {"Owner", "Managing Director", "Finance"}:
        raise ApiError(403, "FORBIDDEN", "Access denied")
    row = (
        (await session.execute(select(financial_rules).where(financial_rules.c.id == rule_id)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return _public(row)
