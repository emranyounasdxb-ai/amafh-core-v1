"""Branch-scoped inventory, retained histories, and report aggregates."""

from datetime import date
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.assets import asset_assignments, asset_history, asset_maintenance_history, assets
from app.errors import ApiError
from app.policies import Actor
from app.services.asset_commands import _current
from app.services.operations_scope import branch_scope


def _base(
    actor: Actor,
    *,
    branch_id: UUID | None,
    category: str | None,
    status: str | None,
    employee_id: UUID | None,
    date_from: date | None,
    date_to: date | None,
    search: str | None,
):
    scope = branch_scope(actor, "asset.write", branch_id)
    query = select(assets.c.id)
    if scope is not None:
        query = query.where(assets.c.branch_id == scope)
    if category is not None:
        query = query.where(assets.c.category == category)
    if status is not None:
        query = query.where(assets.c.status == status)
    if employee_id:
        query = query.where(
            select(asset_assignments.c.id)
            .where(
                asset_assignments.c.asset_id == assets.c.id,
                asset_assignments.c.employee_id == employee_id,
            )
            .exists()
        )
    if date_from or date_to:
        activity = select(asset_history.c.id).where(asset_history.c.asset_id == assets.c.id)
        if date_from:
            activity = activity.where(asset_history.c.effective_date >= date_from)
        if date_to:
            activity = activity.where(asset_history.c.effective_date <= date_to)
        query = query.where(activity.exists())
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                assets.c.asset_code.ilike(term),
                assets.c.serial_number.ilike(term),
                assets.c.brand.ilike(term),
                assets.c.model.ilike(term),
            )
        )
    return query


def _open_employee():
    return (
        select(asset_assignments.c.employee_id)
        .where(
            asset_assignments.c.asset_id == assets.c.id, asset_assignments.c.return_date.is_(None)
        )
        .limit(1)
        .scalar_subquery()
    )


def _public(row) -> dict:
    return {
        "id": row["id"],
        "assetCode": row["asset_code"],
        "branchId": row["branch_id"],
        "category": row["category"],
        "brand": row["brand"],
        "model": row["model"],
        "serialNumber": row["serial_number"],
        "mobileNumber": row["mobile_number"],
        "operatorProvider": row["operator_provider"],
        "status": row["status"],
        "currentEmployeeId": row["current_employee_id"],
        "createdAt": row["created_at"],
    }


async def list_assets(
    session: AsyncSession,
    actor: Actor,
    *,
    branch_id: UUID | None = None,
    category: str | None = None,
    status: str | None = None,
    employee_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
    sort: str = "createdAt",
    direction: str = "desc",
) -> dict:
    if date_from and date_to and date_from > date_to:
        raise ApiError(422, "DATE_RANGE_INVALID", "Start Date must not follow End Date")
    order = {
        "createdAt": assets.c.created_at,
        "assetCode": assets.c.asset_code,
        "category": assets.c.category,
        "brand": assets.c.brand,
        "model": assets.c.model,
        "serialNumber": assets.c.serial_number,
        "branchId": assets.c.branch_id,
        "currentEmployeeId": _open_employee(),
        "status": assets.c.status,
    }.get(sort)
    if order is None or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    ids = _base(
        actor,
        branch_id=branch_id,
        category=category,
        status=status,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    total = await session.scalar(select(func.count()).select_from(ids.subquery())) or 0
    counts = {}
    for label, state in (
        ("availableCount", "Available"),
        ("issuedCount", "Issued"),
        ("maintenanceCount", "Maintenance"),
        ("damagedCount", "Damaged"),
    ):
        counts[label] = (
            await session.scalar(
                select(func.count()).select_from(ids.where(assets.c.status == state).subquery())
            )
            or 0
        )
    rows = (
        (
            await session.execute(
                select(*assets.c, _open_employee().label("current_employee_id"))
                .where(assets.c.id.in_(ids))
                .order_by(
                    (order.asc() if direction == "asc" else order.desc()).nulls_last(),
                    assets.c.id,
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    return {
        "items": [_public(row) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
        **counts,
    }


async def _scoped_asset(session: AsyncSession, actor: Actor, asset_id: UUID) -> None:
    scope = branch_scope(actor, "asset.write")
    query = select(assets.c.id).where(assets.c.id == asset_id)
    if scope is not None:
        query = query.where(assets.c.branch_id == scope)
    if await session.scalar(query) is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")


async def detail(session: AsyncSession, actor: Actor, asset_id: UUID) -> dict:
    await _scoped_asset(session, actor, asset_id)
    return {"asset": await _current(session, asset_id)}


def _assignment(row) -> dict:
    return {
        "id": row["id"],
        "assetId": row["asset_id"],
        "employeeId": row["employee_id"],
        "issueDate": row["issue_date"],
        "returnDate": row["return_date"],
        "returnReason": row["return_reason"],
        "conditionOnReturn": row["condition_on_return"],
        "durationDays": row["duration_days"],
        "issuedByEmployeeId": row["issued_by_employee_id"],
        "returnedByEmployeeId": row["returned_by_employee_id"],
    }


async def assignments(
    session: AsyncSession,
    actor: Actor,
    *,
    asset_id: UUID | None = None,
    branch_id: UUID | None = None,
    employee_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    asset_ids=None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    if asset_id:
        await _scoped_asset(session, actor, asset_id)
    scope = branch_scope(actor, "asset.write", branch_id)
    query = select(asset_assignments).join(assets, assets.c.id == asset_assignments.c.asset_id)
    if scope:
        query = query.where(assets.c.branch_id == scope)
    if asset_id:
        query = query.where(asset_assignments.c.asset_id == asset_id)
    if employee_id:
        query = query.where(asset_assignments.c.employee_id == employee_id)
    if asset_ids is not None:
        query = query.where(asset_assignments.c.asset_id.in_(asset_ids))
    if date_from:
        query = query.where(
            or_(
                asset_assignments.c.return_date.is_(None),
                asset_assignments.c.return_date >= date_from,
            )
        )
    if date_to:
        query = query.where(asset_assignments.c.issue_date <= date_to)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (
        (
            await session.execute(
                query.order_by(asset_assignments.c.issue_date.desc(), asset_assignments.c.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    return {
        "items": [_assignment(row) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


async def maintenance(
    session: AsyncSession, actor: Actor, asset_id: UUID, page: int, page_size: int
) -> dict:
    await _scoped_asset(session, actor, asset_id)
    query = select(asset_maintenance_history).where(
        asset_maintenance_history.c.asset_id == asset_id
    )
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (
        (
            await session.execute(
                query.order_by(
                    asset_maintenance_history.c.start_date.desc(), asset_maintenance_history.c.id
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    return {
        "items": [
            {
                "id": row["id"],
                "assetId": row["asset_id"],
                "startDate": row["start_date"],
                "completionDate": row["completion_date"],
                "resultingStatus": row["resulting_status"],
                "notes": row["notes"],
                "completionNotes": row["completion_notes"],
                "durationDays": row["duration_days"],
                "startedByEmployeeId": row["started_by_employee_id"],
                "completedByEmployeeId": row["completed_by_employee_id"],
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


async def history(
    session: AsyncSession, actor: Actor, asset_id: UUID, page: int, page_size: int
) -> dict:
    await _scoped_asset(session, actor, asset_id)
    query = select(asset_history).where(asset_history.c.asset_id == asset_id)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (
        (
            await session.execute(
                query.order_by(
                    asset_history.c.effective_date.desc(),
                    asset_history.c.created_at.desc(),
                    asset_history.c.id,
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    return {
        "items": [
            {
                "id": row["id"],
                "assetId": row["asset_id"],
                "branchId": row["branch_id"],
                "action": row["action"],
                "previousStatus": row["previous_status"],
                "newStatus": row["new_status"],
                "effectiveDate": row["effective_date"],
                "employeeId": row["employee_id"],
                "actorEmployeeId": row["actor_employee_id"],
                "reason": row["reason"],
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


async def report(
    session: AsyncSession,
    actor: Actor,
    *,
    branch_id: UUID | None,
    category: str | None,
    status: str | None,
    employee_id: UUID | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
) -> dict:
    inventory = await list_assets(
        session,
        actor,
        branch_id=branch_id,
        category=category,
        status=status,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    ids = _base(
        actor,
        branch_id=branch_id,
        category=category,
        status=status,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        search=None,
    )
    grouped = (
        select(
            asset_assignments.c.employee_id.label("employee_id"),
            func.count().label("issued_count"),
        )
        .where(asset_assignments.c.asset_id.in_(ids), asset_assignments.c.return_date.is_(None))
        .group_by(asset_assignments.c.employee_id)
    )
    group_total = await session.scalar(select(func.count()).select_from(grouped.subquery())) or 0
    groups = (
        await session.execute(
            grouped.order_by(func.count().desc(), asset_assignments.c.employee_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    issue_history = await assignments(
        session,
        actor,
        branch_id=branch_id,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        asset_ids=ids,
        page=page,
        page_size=page_size,
    )
    return {
        "inventory": inventory,
        "issuedByEmployee": {
            "items": [
                {"employeeId": row.employee_id, "issuedCount": row.issued_count} for row in groups
            ],
            "total": group_total,
            "page": page,
            "pageSize": page_size,
        },
        "issueReturnHistory": issue_history,
    }
