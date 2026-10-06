"""Immutable effective Bank and Product pipeline versions."""

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.cases import bank_product_mappings, cases, pipeline_configurations, pipeline_stages
from app.errors import ApiError
from app.normalization import identifier
from app.policies import Actor, require
from app.repositories.case_scope import case_access
from app.schemas.catalog import PipelineCreate
from app.services.catalog import _active_mapping


def validate_stages(item: PipelineCreate) -> None:
    stages = item.stages
    if sorted(stage.stageOrder for stage in stages) != list(range(1, len(stages) + 1)):
        raise ApiError(422, "INVALID_STAGES", "Stage order must be contiguous from one")
    if len({identifier(stage.name) for stage in stages}) != len(stages):
        raise ApiError(422, "INVALID_STAGES", "Stage names must be unique")
    if any(identifier(stage.name) == "CASE REOPENED BY OWNER" for stage in stages):
        raise ApiError(422, "INVALID_STAGES", "Reserved Owner reopen value")
    if not any(stage.isFinal for stage in stages):
        raise ApiError(422, "INVALID_STAGES", "At least one final stage is required")
    final_seen = False
    ordered = sorted(stages, key=lambda current: current.stageOrder)
    for stage in ordered:
        if not stage.isFinal and final_seen:
            raise ApiError(422, "INVALID_STAGES", "Final stages must follow processing stages")
        final_seen = final_seen or stage.isFinal
    if ordered[0].isFinal:
        raise ApiError(422, "INVALID_STAGES", "Initial stage cannot be final")
    for stage in stages:
        if stage.isFinal != (stage.finalStatus in {"Completed", "Rejected"}):
            raise ApiError(
                422, "INVALID_STAGES", "Final stages need a Completed or Rejected outcome"
            )
        if not stage.isFinal and stage.finalStatus is not None:
            raise ApiError(422, "INVALID_STAGES", "Non-final stages cannot set a final outcome")


def _historical_case(actor: Actor):
    return exists(
        select(cases.c.id).where(
            cases.c.pipeline_configuration_id == pipeline_configurations.c.id,
            case_access(actor),
        )
    )


async def create_version(session: AsyncSession, actor: Actor, item: PipelineCreate) -> dict:
    require(actor, "pipeline.write")
    validate_stages(item)
    try:
        # Lock the mapping so versions for this Bank/Product serialize.
        await _active_mapping(session, item.bankId, item.productTypeId)
        mapping = await session.scalar(
            select(bank_product_mappings.c.id)
            .where(
                bank_product_mappings.c.bank_id == item.bankId,
                bank_product_mappings.c.product_type_id == item.productTypeId,
            )
            .with_for_update()
        )
        assert mapping is not None
        latest = await session.scalar(
            select(func.max(pipeline_configurations.c.version)).where(
                pipeline_configurations.c.bank_id == item.bankId,
                pipeline_configurations.c.product_type_id == item.productTypeId,
            )
        )
        pipeline_id = uuid4()
        version = (latest or 0) + 1
        await session.execute(
            pipeline_configurations.insert().values(
                id=pipeline_id,
                bank_id=item.bankId,
                product_type_id=item.productTypeId,
                effective_date=item.effectiveDate,
                version=version,
                active=True,
            )
        )
        for stage in item.stages:
            await session.execute(
                pipeline_stages.insert().values(
                    id=uuid4(),
                    pipeline_configuration_id=pipeline_id,
                    name=stage.name,
                    stage_order=stage.stageOrder,
                    expected_business_days=stage.expectedBusinessDays,
                    is_final=stage.isFinal,
                    final_status=stage.finalStatus,
                )
            )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="pipeline.version_created",
            module="pipeline",
            entity_type="pipeline_configuration",
            entity_id=pipeline_id,
            after={
                "bankId": str(item.bankId),
                "productTypeId": str(item.productTypeId),
                "effectiveDate": item.effectiveDate.isoformat(),
                "version": version,
                "stages": [stage.model_dump() for stage in item.stages],
            },
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return {"id": str(pipeline_id), "version": version, "active": True}


async def list_versions(
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
    if not ({"pipeline.write", "case.create", "case.read"} & actor.grants):
        raise ApiError(403, "FORBIDDEN", "Access denied")
    order = (
        {
            "id": pipeline_configurations.c.id,
            "effectiveDate": pipeline_configurations.c.effective_date,
            "active": pipeline_configurations.c.active,
        }.get(sort)
        if sort is not None
        else None
    )
    if (sort is not None and order is None) or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    filters = []
    if bank_id is not None:
        filters.append(pipeline_configurations.c.bank_id == bank_id)
    if product_id is not None:
        filters.append(pipeline_configurations.c.product_type_id == product_id)
    if actor.designation not in {"Owner", "Managing Director"}:
        filters.append(or_(pipeline_configurations.c.active.is_(True), _historical_case(actor)))
    elif active is not None:
        filters.append(pipeline_configurations.c.active.is_(active))
    total = await session.scalar(
        select(func.count()).select_from(pipeline_configurations).where(*filters)
    )
    rows = (
        await session.execute(
            select(pipeline_configurations)
            .where(*filters)
            .order_by(
                (order.asc() if direction == "asc" else order.desc())
                if order is not None
                else pipeline_configurations.c.effective_date.desc(),
                pipeline_configurations.c.version.desc(),
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).mappings()
    return {
        "items": [_serialize(row) for row in rows],
        "page": page,
        "pageSize": page_size,
        "total": total or 0,
    }


def _serialize(row) -> dict:
    return {
        key: str(value) if isinstance(value, UUID) else value for key, value in dict(row).items()
    }


async def get_version(session: AsyncSession, actor: Actor, pipeline_id: UUID) -> dict:
    reader = bool({"pipeline.write", "case.create", "case.read"} & actor.grants)
    row = (
        (
            await session.execute(
                select(pipeline_configurations).where(pipeline_configurations.c.id == pipeline_id)
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    # Without Pipeline access, only the Pipeline of the actor's own Cases is readable.
    if not reader or (
        actor.designation not in {"Owner", "Managing Director"} and not row["active"]
    ):
        authorized = await session.scalar(
            select(pipeline_configurations.c.id).where(
                pipeline_configurations.c.id == pipeline_id, _historical_case(actor)
            )
        )
        if authorized is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
    stages = (
        await session.execute(
            select(pipeline_stages)
            .where(pipeline_stages.c.pipeline_configuration_id == pipeline_id)
            .order_by(pipeline_stages.c.stage_order)
        )
    ).mappings()
    return {**_serialize(row), "stages": [_serialize(stage) for stage in stages]}


async def set_active(session: AsyncSession, actor: Actor, pipeline_id: UUID, active: bool) -> None:
    require(actor, "pipeline.write")
    try:
        row = (
            (
                await session.execute(
                    select(pipeline_configurations)
                    .where(pipeline_configurations.c.id == pipeline_id)
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        if row["active"] == active:
            raise ApiError(409, "UNCHANGED", "Pipeline already has that status")
        if active:
            await _active_mapping(session, row["bank_id"], row["product_type_id"])
            await _valid_stage_set(session, pipeline_id)
        await session.execute(
            update(pipeline_configurations)
            .where(pipeline_configurations.c.id == pipeline_id)
            .values(active=active)
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="pipeline.status_changed",
            module="pipeline",
            entity_type="pipeline_configuration",
            entity_id=pipeline_id,
            before={"active": row["active"]},
            after={"active": active},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def _valid_stage_set(session: AsyncSession, pipeline_id: UUID) -> list[dict]:
    rows = (
        (
            await session.execute(
                select(pipeline_stages)
                .where(pipeline_stages.c.pipeline_configuration_id == pipeline_id)
                .order_by(pipeline_stages.c.stage_order)
            )
        )
        .mappings()
        .all()
    )
    if not rows or [row["stage_order"] for row in rows] != list(range(1, len(rows) + 1)):
        raise ApiError(422, "INVALID_PIPELINE", "Pipeline stages are unavailable")
    if not any(
        row["is_final"] and row["final_status"] in {"Completed", "Rejected"} for row in rows
    ):
        raise ApiError(422, "INVALID_PIPELINE", "Pipeline final stage is unavailable")
    if rows[0]["is_final"] or any(
        not row["is_final"] and any(previous["is_final"] for previous in rows[:index])
        for index, row in enumerate(rows)
    ):
        raise ApiError(422, "INVALID_PIPELINE", "Pipeline stage order is unavailable")
    if any(row["is_final"] != (row["final_status"] in {"Completed", "Rejected"}) for row in rows):
        raise ApiError(422, "INVALID_PIPELINE", "Pipeline final outcome is unavailable")
    return [dict(row) for row in rows]


async def effective_pipeline(
    session: AsyncSession, bank_id: UUID, product_id: UUID, on: date
) -> tuple[UUID, list[dict]]:
    row = (
        (
            await session.execute(
                select(pipeline_configurations)
                .where(
                    pipeline_configurations.c.bank_id == bank_id,
                    pipeline_configurations.c.product_type_id == product_id,
                    pipeline_configurations.c.effective_date <= on,
                    pipeline_configurations.c.active.is_(True),
                )
                .order_by(
                    pipeline_configurations.c.effective_date.desc(),
                    pipeline_configurations.c.version.desc(),
                )
                .limit(1)
                .with_for_update(read=True)
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(422, "NO_PIPELINE", "No effective Pipeline Configuration")
    return row["id"], await _valid_stage_set(session, row["id"])
