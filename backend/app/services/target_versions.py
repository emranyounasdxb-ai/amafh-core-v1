"""Audited, effective-dated Target commands and restricted version reads."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.operations import notifications, targets
from app.db.organization import branches, departments, designations
from app.errors import ApiError
from app.policies import Actor, require
from app.schemas.performance import TargetInput
from app.services.department_products import department_product
from app.services.organization import dubai_today
from app.services.performance_math import DUBAI
from app.services.target_notifications import dispatch_target


def _public(row) -> dict:
    return {
        "id": row["id"],
        "branchId": row["branch_id"],
        "departmentId": row["department_id"],
        "designationId": row["designation_id"],
        "effectiveDate": row["effective_date"],
        "targetPoints": row["target_points"],
        "targetAmountAed": row["target_amount_aed"],
        "active": row["active"],
        "inactiveFromDate": row["inactive_from_date"],
        "supersededByTargetId": row["superseded_by_target_id"],
    }


def _audit_values(row: dict) -> dict:
    return {
        "branchId": str(row["branch_id"]),
        "departmentId": str(row["department_id"]),
        "designationId": str(row["designation_id"]),
        "effectiveDate": row["effective_date"].isoformat(),
        "targetPoints": row["target_points"],
        "targetAmountAed": str(row["target_amount_aed"])
        if row["target_amount_aed"] is not None
        else None,
        "active": row["active"],
    }


async def _context(session: AsyncSession, item: TargetInput) -> None:
    branch = await session.scalar(
        select(branches.c.id)
        .where(branches.c.id == item.branchId, branches.c.active)
        .with_for_update(read=True)
    )
    department = (
        await session.execute(
            select(departments.c.id)
            .where(
                departments.c.id == item.departmentId,
                departments.c.branch_id == item.branchId,
                departments.c.active,
            )
            .with_for_update(read=True)
        )
    ).scalar_one_or_none()
    designation = await session.scalar(
        select(designations.c.id).where(
            designations.c.id == item.designationId, designations.c.locked
        )
    )
    if branch is None or department is None or designation is None:
        raise ApiError(422, "INACTIVE_TARGET_CONTEXT", "Target context is unavailable")
    product = await department_product(session, department)
    if product is None:
        raise ApiError(
            422,
            "DEPARTMENT_UNCLASSIFIED",
            "Assign a Target product to this Department in Settings first",
        )
    if (product == "CC" and item.targetPoints is None) or (
        product == "PF" and item.targetAmountAed is None
    ):
        raise ApiError(422, "TARGET_TYPE_MISMATCH", "Target value does not match Department")
    if item.effectiveDate < dubai_today():
        raise ApiError(422, "TARGET_DATE_INVALID", "Effective Date cannot be in the past")


async def _insert(session: AsyncSession, actor: Actor, item: TargetInput) -> tuple[dict, dict]:
    target_id = uuid4()
    row = {
        "id": target_id,
        "branch_id": item.branchId,
        "department_id": item.departmentId,
        "designation_id": item.designationId,
        "effective_date": item.effectiveDate,
        "target_points": item.targetPoints,
        "target_amount_aed": item.targetAmountAed,
        "active": True,
        "inactive_from_date": None,
        "superseded_by_target_id": None,
    }
    await session.execute(targets.insert().values(**row))
    await audit.record(
        session,
        actor=actor.employee_id,
        action="target.created",
        module="targets",
        entity_type="target",
        entity_id=target_id,
        after=_audit_values(row),
    )
    await dispatch_target(session, row, today=dubai_today())
    return row, _public(row)


async def create(session: AsyncSession, actor: Actor, item: TargetInput) -> dict:
    require(actor, "target.write")
    try:
        await _context(session, item)
        _, result = await _insert(session, actor, item)
        await session.commit()
        return result
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(409, "TARGET_CONFLICT", "Target version conflicts") from exc
    except Exception:
        await session.rollback()
        raise


async def _locked(session: AsyncSession, target_id: UUID) -> dict:
    row = (
        (await session.execute(select(targets).where(targets.c.id == target_id).with_for_update()))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return dict(row)


async def replace(session: AsyncSession, actor: Actor, target_id: UUID, item: TargetInput) -> dict:
    require(actor, "target.write")
    try:
        prior = await _locked(session, target_id)
        if (
            not prior["active"]
            or (prior["branch_id"], prior["department_id"], prior["designation_id"])
            != (item.branchId, item.departmentId, item.designationId)
            or item.effectiveDate <= prior["effective_date"]
        ):
            raise ApiError(409, "TARGET_REPLACEMENT_INVALID", "Invalid Target replacement")
        await _context(session, item)
        await session.execute(
            update(targets)
            .where(targets.c.id == target_id)
            .values(
                active=False,
                inactive_from_date=item.effectiveDate,
            )
        )
        row, result = await _insert(session, actor, item)
        await session.execute(
            update(targets)
            .where(targets.c.id == target_id)
            .values(
                superseded_by_target_id=row["id"],
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="target.replaced",
            module="targets",
            entity_type="target",
            entity_id=target_id,
            before={**_audit_values(prior), "inactiveFromDate": None},
            after={
                **_audit_values({**prior, "active": False}),
                "inactiveFromDate": item.effectiveDate.isoformat(),
                "supersededByTargetId": str(row["id"]),
            },
        )
        await session.commit()
        return result
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(409, "TARGET_CONFLICT", "Target version conflicts") from exc
    except Exception:
        await session.rollback()
        raise


async def deactivate(session: AsyncSession, actor: Actor, target_id: UUID) -> None:
    require(actor, "target.write")
    try:
        row = await _locked(session, target_id)
        if not row["active"]:
            raise ApiError(409, "TARGET_STATE_CONFLICT", "Target is already inactive")
        inactive_from = max(dubai_today(), row["effective_date"])
        await session.execute(
            update(targets)
            .where(targets.c.id == target_id)
            .values(
                active=False,
                inactive_from_date=inactive_from,
            )
        )
        if inactive_from <= row["effective_date"]:
            await session.execute(
                update(notifications)
                .where(
                    notifications.c.target_id == target_id,
                    notifications.c.suppressed_at.is_(None),
                )
                .values(suppressed_at=datetime.now(DUBAI))
            )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="target.deactivated",
            module="targets",
            entity_type="target",
            entity_id=target_id,
            before={"active": True, "inactiveFromDate": None},
            after={"active": False, "inactiveFromDate": inactive_from.isoformat()},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def activate(session: AsyncSession, actor: Actor, target_id: UUID) -> dict:
    require(actor, "target.write")
    try:
        prior = await _locked(session, target_id)
        if prior["active"] or prior["superseded_by_target_id"] is not None:
            raise ApiError(409, "TARGET_STATE_CONFLICT", "Target cannot be activated")
        effective_date = max(
            dubai_today(), prior["inactive_from_date"], prior["effective_date"] + timedelta(days=1)
        )
        item = TargetInput(
            branchId=prior["branch_id"],
            departmentId=prior["department_id"],
            designationId=prior["designation_id"],
            effectiveDate=effective_date,
            targetPoints=prior["target_points"],
            targetAmountAed=prior["target_amount_aed"],
        )
        await _context(session, item)
        row, result = await _insert(session, actor, item)
        await audit.record(
            session,
            actor=actor.employee_id,
            action="target.activated",
            module="targets",
            entity_type="target",
            entity_id=row["id"],
            before={"priorTargetId": str(target_id), "active": False},
            after={**_audit_values(row), "priorTargetId": str(target_id)},
        )
        await session.commit()
        return result
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(409, "TARGET_CONFLICT", "Target version conflicts") from exc
    except Exception:
        await session.rollback()
        raise


async def detail(session: AsyncSession, actor: Actor, target_id: UUID) -> dict:
    require(actor, "target.write")
    row = (
        (await session.execute(select(targets).where(targets.c.id == target_id)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return _public(row)


async def list_versions(
    session: AsyncSession,
    actor: Actor,
    *,
    page: int,
    page_size: int,
    branch_id: UUID | None,
    department_id: UUID | None,
    designation_id: UUID | None,
    sort: str | None = None,
    direction: str = "asc",
) -> dict:
    require(actor, "target.write")
    order = (
        {
            "effectiveDate": targets.c.effective_date,
            "targetPoints": targets.c.target_points,
            "targetAmountAed": targets.c.target_amount_aed,
            "active": targets.c.active,
        }.get(sort)
        if sort is not None
        else None
    )
    if (sort is not None and order is None) or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    conditions = []
    if branch_id is not None:
        conditions.append(targets.c.branch_id == branch_id)
    if department_id is not None:
        conditions.append(targets.c.department_id == department_id)
    if designation_id is not None:
        conditions.append(targets.c.designation_id == designation_id)
    total = await session.scalar(select(func.count()).select_from(targets).where(*conditions))
    rows = (
        (
            await session.execute(
                select(targets)
                .where(*conditions)
                .order_by(
                    (order.asc() if direction == "asc" else order.desc())
                    if order is not None
                    else targets.c.effective_date.desc(),
                    targets.c.created_at.desc(),
                    targets.c.id,
                )
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        )
        .mappings()
        .all()
    )
    return {
        "items": [_public(row) for row in rows],
        "total": total or 0,
        "page": page,
        "pageSize": page_size,
    }
