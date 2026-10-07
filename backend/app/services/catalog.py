"""Controlled Bank, Product, mapping and Variant configuration."""

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app import audit
from app.db.cases import bank_product_mappings, banks, cases, product_types, product_variants
from app.errors import ApiError
from app.identifiers import new_bank_code
from app.policies import Actor, require
from app.repositories.case_scope import case_access
from app.schemas.catalog import VariantUpdate
from app.whole_numbers import whole_text

TABLES = {
    "banks": banks,
    "product-types": product_types,
    "bank-product-mappings": bank_product_mappings,
    "product-variants": product_variants,
}


def _historical_case(actor: Actor, kind: str, table):
    conditions: tuple
    if kind == "banks":
        conditions = (cases.c.bank_id == table.c.id,)
    elif kind == "product-types":
        conditions = (cases.c.product_type_id == table.c.id,)
    elif kind == "bank-product-mappings":
        conditions = (
            cases.c.bank_id == table.c.bank_id,
            cases.c.product_type_id == table.c.product_type_id,
        )
    else:
        conditions = (cases.c.product_variant_id == table.c.id,)
    return exists(select(cases.c.id).where(*conditions, case_access(actor)))


def _can_read(actor: Actor) -> bool:
    return bool({"pipeline.write", "case.create", "case.read"} & actor.grants)


def _may_read(actor: Actor) -> None:
    if not _can_read(actor):
        raise ApiError(403, "FORBIDDEN", "Access denied")


def _row(row) -> dict:
    return {
        key: str(value)
        if isinstance(value, UUID)
        else whole_text(value)
        if isinstance(value, Decimal)
        else value
        for key, value in dict(row).items()
    }


async def _active_context(session: AsyncSession, bank_id: UUID, product_id: UUID) -> None:
    bank = await session.scalar(
        select(banks.c.id).where(banks.c.id == bank_id, banks.c.active.is_(True)).with_for_update()
    )
    product = await session.scalar(
        select(product_types.c.id)
        .where(product_types.c.id == product_id, product_types.c.active.is_(True))
        .with_for_update()
    )
    if not bank or not product:
        raise ApiError(422, "INACTIVE_CONFIGURATION", "Bank or Product is unavailable")


async def _active_mapping(session: AsyncSession, bank_id: UUID, product_id: UUID) -> None:
    await _active_context(session, bank_id, product_id)
    mapping = await session.scalar(
        select(bank_product_mappings.c.id)
        .where(
            bank_product_mappings.c.bank_id == bank_id,
            bank_product_mappings.c.product_type_id == product_id,
            bank_product_mappings.c.active.is_(True),
        )
        .with_for_update()
    )
    if not mapping:
        raise ApiError(422, "INACTIVE_CONFIGURATION", "Bank and Product mapping is unavailable")


async def list_records(
    session: AsyncSession,
    actor: Actor,
    kind: str,
    *,
    page: int,
    page_size: int,
    active: bool | None = None,
    bank_id: UUID | None = None,
    product_id: UUID | None = None,
    sort: str = "name",
    direction: str = "asc",
) -> dict:
    _may_read(actor)
    table = TABLES[kind]
    predicate: list[ColumnElement[bool]] = []
    if actor.designation not in {"Owner", "Managing Director"}:
        predicate.append(or_(table.c.active.is_(True), _historical_case(actor, kind, table)))
    elif active is not None:
        predicate.append(table.c.active.is_(active))
    if bank_id is not None and "bank_id" in table.c:
        predicate.append(table.c.bank_id == bank_id)
    elif bank_id is not None and kind == "product-types":
        predicate.append(
            exists(
                select(bank_product_mappings.c.id).where(
                    bank_product_mappings.c.bank_id == bank_id,
                    bank_product_mappings.c.product_type_id == table.c.id,
                    bank_product_mappings.c.active.is_(True),
                )
            )
        )
    if product_id is not None and "product_type_id" in table.c:
        predicate.append(table.c.product_type_id == product_id)
    sort_fields = {
        "name": table.c.name if "name" in table.c else table.c.id,
        "code": table.c.bank_code
        if kind == "banks"
        else table.c.code
        if kind == "product-types"
        else table.c.id,
        "createdAt": table.c.created_at if "created_at" in table.c else table.c.id,
        "active": table.c.active,
    }
    if kind == "bank-product-mappings":
        sort_fields.update(
            bankId=table.c.bank_id,
            productTypeId=table.c.product_type_id,
            active=table.c.active,
        )
    if kind == "product-variants":
        sort_fields.update(
            minimum_salary_aed=table.c.minimum_salary_aed,
            maximum_salary_aed=table.c.maximum_salary_aed,
        )
    order = sort_fields.get(sort)
    if order is None or direction not in {"asc", "desc"}:
        raise ApiError(422, "INVALID_SORT", "Unsupported sort")
    total = await session.scalar(select(func.count()).select_from(table).where(*predicate))
    rows = (
        await session.execute(
            select(table)
            .where(*predicate)
            .order_by(
                (order.asc() if direction == "asc" else order.desc()).nulls_last(), table.c.id
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).mappings()
    return {
        "items": [_row(row) for row in rows],
        "page": page,
        "pageSize": page_size,
        "total": total or 0,
    }


async def get_record(session: AsyncSession, actor: Actor, kind: str, record_id: UUID) -> dict:
    table = TABLES[kind]
    row = (
        (await session.execute(select(table).where(table.c.id == record_id)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    # Without catalog access, only the configuration of the actor's own Cases is readable.
    if not _can_read(actor) or (
        actor.designation not in {"Owner", "Managing Director"} and not row["active"]
    ):
        authorized = await session.scalar(
            select(table.c.id).where(
                table.c.id == record_id,
                _historical_case(actor, table.name.replace("_", "-"), table),
            )
        )
        if authorized is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return _row(row)


async def create_record(session: AsyncSession, actor: Actor, kind: str, values: dict) -> dict:
    require(actor, "pipeline.write")
    table = TABLES[kind]
    record_id = uuid4()
    try:
        if kind == "banks":
            if "bank_code" in values:
                raise ApiError(422, "BANK_CODE_GENERATED", "Bank Code is generated by the server")
            values = {**values, "bank_code": await new_bank_code(session)}
        if kind in {"bank-product-mappings", "product-variants"}:
            if kind == "product-variants":
                await _active_mapping(session, values["bank_id"], values["product_type_id"])
            else:
                await _active_context(session, values["bank_id"], values["product_type_id"])
        await session.execute(table.insert().values(id=record_id, **values))
        await audit.record(
            session,
            actor=actor.employee_id,
            action=f"{table.name}.created",
            module="pipeline",
            entity_type=table.name,
            entity_id=record_id,
            after=_row(values),
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return {
        "id": str(record_id),
        **_row(values),
        "active": True,
    }


async def rename_record(
    session: AsyncSession, actor: Actor, kind: str, record_id: UUID, name: str
) -> None:
    require(actor, "pipeline.write")
    if kind not in {"banks", "product-types", "product-variants"}:
        raise ApiError(405, "METHOD_NOT_ALLOWED", "This record has no name")
    table = TABLES[kind]
    try:
        row = (
            (await session.execute(select(table).where(table.c.id == record_id).with_for_update()))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        await session.execute(update(table).where(table.c.id == record_id).values(name=name))
        await audit.record(
            session,
            actor=actor.employee_id,
            action=f"{table.name}.renamed",
            module="pipeline",
            entity_type=table.name,
            entity_id=record_id,
            before={"name": row["name"]},
            after={"name": name},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def update_variant(
    session: AsyncSession, actor: Actor, record_id: UUID, item: VariantUpdate
) -> None:
    require(actor, "pipeline.write")
    values: dict = {"name": item.name}
    if "minimumSalaryAed" in item.model_fields_set:
        values.update(
            minimum_salary_aed=item.minimumSalaryAed, maximum_salary_aed=item.maximumSalaryAed
        )
    try:
        row = (
            (
                await session.execute(
                    select(product_variants)
                    .where(product_variants.c.id == record_id)
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        await session.execute(
            update(product_variants).where(product_variants.c.id == record_id).values(**values)
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="product_variants.updated" if len(values) > 1 else "product_variants.renamed",
            module="pipeline",
            entity_type="product_variants",
            entity_id=record_id,
            before=_row({key: row[key] for key in values}),
            after=_row(values),
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def set_active(
    session: AsyncSession, actor: Actor, kind: str, record_id: UUID, active: bool
) -> None:
    require(actor, "pipeline.write")
    table = TABLES[kind]
    try:
        row = (
            (await session.execute(select(table).where(table.c.id == record_id).with_for_update()))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        if row["active"] == active:
            raise ApiError(409, "UNCHANGED", "Configuration already has that status")
        if active and kind in {"bank-product-mappings", "product-variants"}:
            if kind == "product-variants":
                await _active_mapping(session, row["bank_id"], row["product_type_id"])
            else:
                await _active_context(session, row["bank_id"], row["product_type_id"])
        await session.execute(update(table).where(table.c.id == record_id).values(active=active))
        await audit.record(
            session,
            actor=actor.employee_id,
            action=f"{table.name}.status_changed",
            module="pipeline",
            entity_type=table.name,
            entity_id=record_id,
            before={"active": row["active"]},
            after={"active": active},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
