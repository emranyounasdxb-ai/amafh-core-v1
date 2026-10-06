"""Transactional, idempotent Asset lifecycle commands."""

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.assets import asset_assignments, asset_history, asset_maintenance_history, assets
from app.db.operations import notifications
from app.db.organization import branches, employees
from app.errors import ApiError
from app.identifiers import new_asset_code
from app.policies import Actor
from app.schemas.assets import (
    AssetCreate,
    AssetDamage,
    AssetIssue,
    AssetMaintenanceComplete,
    AssetMaintenanceStart,
    AssetResponse,
    AssetReturn,
)
from app.services.idempotency import claim, complete
from app.services.operations_scope import branch_scope, required_branch
from app.services.organization import dubai_today


async def _locked_asset(session: AsyncSession, actor: Actor, asset_id: UUID) -> dict:
    scope = branch_scope(actor, "asset.write")
    query = select(assets).where(assets.c.id == asset_id)
    if scope is not None:
        query = query.where(assets.c.branch_id == scope)
    row = (await session.execute(query.with_for_update())).mappings().one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return dict(row)


async def _current(session: AsyncSession, asset_id: UUID) -> dict:
    row = (await session.execute(select(assets).where(assets.c.id == asset_id))).mappings().one()
    employee_id = await session.scalar(
        select(asset_assignments.c.employee_id).where(
            asset_assignments.c.asset_id == asset_id,
            asset_assignments.c.return_date.is_(None),
        )
    )
    return AssetResponse.model_validate(
        {
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
            "currentEmployeeId": employee_id,
            "createdAt": row["created_at"],
        }
    ).model_dump(mode="json")


async def _event(
    session: AsyncSession,
    actor: Actor,
    asset: dict,
    *,
    action: str,
    previous: str | None,
    current: str,
    on_date: date,
    employee_id: UUID | None = None,
    assignment_id: UUID | None = None,
    maintenance_id: UUID | None = None,
    reason: str | None = None,
) -> None:
    event_id = uuid4()
    await session.execute(
        asset_history.insert().values(
            id=event_id,
            asset_id=asset["id"],
            branch_id=asset["branch_id"],
            action=action,
            previous_status=previous,
            new_status=current,
            effective_date=on_date,
            employee_id=employee_id,
            actor_employee_id=actor.employee_id,
            assignment_id=assignment_id,
            maintenance_id=maintenance_id,
            reason=reason,
        )
    )
    if employee_id is not None and action != "Created":
        await session.execute(
            notifications.insert().values(
                id=uuid4(),
                recipient_employee_id=employee_id,
                kind=f"asset.{action.lower().replace(' ', '_')}",
                message=f"Asset {asset['asset_code']}: {action}",
            )
        )
    await audit.record(
        session,
        actor=actor.employee_id,
        action=f"asset.{action.lower().replace(' ', '_')}",
        module="assets",
        entity_type="asset",
        entity_id=asset["id"],
        before={"status": previous} if previous else None,
        after={
            "status": current,
            "branchId": str(asset["branch_id"]),
            "employeeId": str(employee_id) if employee_id else None,
            "effectiveDate": on_date.isoformat(),
            "reason": reason,
        },
        context={"assetCode": asset["asset_code"], "historyId": str(event_id)},
    )


async def _last_employee(session: AsyncSession, asset_id: UUID) -> UUID | None:
    return await session.scalar(
        select(asset_assignments.c.employee_id)
        .where(asset_assignments.c.asset_id == asset_id)
        .order_by(asset_assignments.c.issue_date.desc(), asset_assignments.c.created_at.desc())
        .limit(1)
    )


async def create(session: AsyncSession, actor: Actor, item: AssetCreate, key: str) -> dict:
    if actor.designation == "Admin Staff" and item.branchId is not None:
        raise ApiError(422, "BRANCH_FIXED", "Admin Asset Branch is assigned by the server")
    branch_id = required_branch(actor, "asset.write", item.branchId)
    try:
        record_id, replay = await claim(
            session,
            actor,
            "asset.create",
            key,
            {"branchId": str(branch_id), **item.model_dump(mode="json")},
        )
        if replay is not None:
            await session.rollback()
            return replay
        branch = await session.scalar(
            select(branches.c.id).where(branches.c.id == branch_id, branches.c.active)
        )
        if branch is None:
            raise ApiError(422, "BRANCH_UNAVAILABLE", "Branch unavailable")
        asset_id = uuid4()
        code = await new_asset_code(session)
        await session.execute(
            assets.insert().values(
                id=asset_id,
                asset_code=code,
                branch_id=branch_id,
                category=item.category,
                brand=item.brand,
                model=item.model,
                serial_number=item.serialNumber,
                mobile_number=item.mobileNumber,
                operator_provider=item.operatorProvider,
                status="Available",
                created_by_employee_id=actor.employee_id,
            )
        )
        asset = (
            (await session.execute(select(assets).where(assets.c.id == asset_id))).mappings().one()
        )
        await _event(
            session,
            actor,
            dict(asset),
            action="Created",
            previous=None,
            current="Available",
            on_date=dubai_today(),
        )
        result = await _current(session, asset_id)
        await complete(session, record_id, 201, result)
        await session.commit()
        return result
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(409, "ASSET_CONFLICT", "Asset Code or Serial Number conflicts") from exc
    except Exception:
        await session.rollback()
        raise


async def issue(
    session: AsyncSession, actor: Actor, asset_id: UUID, item: AssetIssue, key: str
) -> dict:
    branch_scope(actor, "asset.write")
    try:
        record_id, replay = await claim(
            session,
            actor,
            "asset.issue",
            key,
            {"assetId": str(asset_id), **item.model_dump(mode="json")},
        )
        if replay is not None:
            await session.rollback()
            return replay
        asset = await _locked_asset(session, actor, asset_id)
        if asset["status"] != "Available":
            raise ApiError(409, "ASSET_UNAVAILABLE", "Asset is not Available")
        employee = (
            await session.execute(
                select(employees.c.id)
                .where(
                    employees.c.id == item.employeeId,
                    employees.c.branch_id == asset["branch_id"],
                    employees.c.status == "Active",
                )
                .with_for_update(read=True)
            )
        ).scalar_one_or_none()
        if employee is None:
            raise ApiError(404, "NOT_FOUND", "Employee unavailable")
        assignment_id = uuid4()
        await session.execute(
            asset_assignments.insert().values(
                id=assignment_id,
                asset_id=asset_id,
                employee_id=item.employeeId,
                issue_date=item.issueDate,
                issued_by_employee_id=actor.employee_id,
            )
        )
        await _event(
            session,
            actor,
            asset,
            action="Issued",
            previous="Available",
            current="Issued",
            on_date=item.issueDate,
            employee_id=item.employeeId,
            assignment_id=assignment_id,
        )
        result = await _current(session, asset_id)
        await complete(session, record_id, 200, result)
        await session.commit()
        return result
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(409, "ASSET_ISSUE_CONFLICT", "Asset issue conflicts") from exc
    except Exception:
        await session.rollback()
        raise


async def return_asset(
    session: AsyncSession, actor: Actor, asset_id: UUID, item: AssetReturn, key: str
) -> dict:
    branch_scope(actor, "asset.write")
    try:
        record_id, replay = await claim(
            session,
            actor,
            "asset.return",
            key,
            {"assetId": str(asset_id), **item.model_dump(mode="json")},
        )
        if replay is not None:
            await session.rollback()
            return replay
        asset = await _locked_asset(session, actor, asset_id)
        assignment = (
            (
                await session.execute(
                    select(asset_assignments)
                    .where(
                        asset_assignments.c.asset_id == asset_id,
                        asset_assignments.c.return_date.is_(None),
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if asset["status"] != "Issued" or assignment is None:
            raise ApiError(409, "ASSET_NOT_ISSUED", "Asset has no open assignment")
        if item.returnDate < assignment["issue_date"]:
            raise ApiError(422, "RETURN_DATE_INVALID", "Return Date precedes Issue Date")
        await session.execute(
            update(asset_assignments)
            .where(asset_assignments.c.id == assignment["id"])
            .values(
                return_date=item.returnDate,
                return_reason=item.reason,
                condition_on_return=item.condition,
                returned_by_employee_id=actor.employee_id,
            )
        )
        await _event(
            session,
            actor,
            asset,
            action="Returned",
            previous="Issued",
            current=item.condition,
            on_date=item.returnDate,
            employee_id=assignment["employee_id"],
            assignment_id=assignment["id"],
            reason=item.reason,
        )
        result = await _current(session, asset_id)
        await complete(session, record_id, 200, result)
        await session.commit()
        return result
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(409, "ASSET_RETURN_CONFLICT", "Asset return conflicts") from exc
    except Exception:
        await session.rollback()
        raise


async def start_maintenance(
    session: AsyncSession,
    actor: Actor,
    asset_id: UUID,
    item: AssetMaintenanceStart,
    key: str,
) -> dict:
    branch_scope(actor, "asset.write")
    try:
        record_id, replay = await claim(
            session,
            actor,
            "asset.maintenance.start",
            key,
            {"assetId": str(asset_id), **item.model_dump(mode="json")},
        )
        if replay is not None:
            await session.rollback()
            return replay
        asset = await _locked_asset(session, actor, asset_id)
        if asset["status"] not in {"Available", "Needs Maintenance"}:
            raise ApiError(409, "ASSET_UNAVAILABLE", "Asset cannot enter Maintenance")
        maintenance_id = uuid4()
        await session.execute(
            asset_maintenance_history.insert().values(
                id=maintenance_id,
                asset_id=asset_id,
                start_date=item.startDate,
                started_by_employee_id=actor.employee_id,
                notes=item.notes,
            )
        )
        await _event(
            session,
            actor,
            asset,
            action="Maintenance Started",
            previous=asset["status"],
            current="Maintenance",
            on_date=item.startDate,
            employee_id=await _last_employee(session, asset_id),
            maintenance_id=maintenance_id,
            reason=item.notes,
        )
        result = await _current(session, asset_id)
        await complete(session, record_id, 200, result)
        await session.commit()
        return result
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(409, "ASSET_MAINTENANCE_CONFLICT", "Maintenance conflicts") from exc
    except Exception:
        await session.rollback()
        raise


async def complete_maintenance(
    session: AsyncSession,
    actor: Actor,
    asset_id: UUID,
    item: AssetMaintenanceComplete,
    key: str,
) -> dict:
    branch_scope(actor, "asset.write")
    try:
        record_id, replay = await claim(
            session,
            actor,
            "asset.maintenance.complete",
            key,
            {"assetId": str(asset_id), **item.model_dump(mode="json")},
        )
        if replay is not None:
            await session.rollback()
            return replay
        asset = await _locked_asset(session, actor, asset_id)
        maintenance = (
            (
                await session.execute(
                    select(asset_maintenance_history)
                    .where(
                        asset_maintenance_history.c.asset_id == asset_id,
                        asset_maintenance_history.c.completion_date.is_(None),
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if asset["status"] != "Maintenance" or maintenance is None:
            raise ApiError(409, "ASSET_NOT_IN_MAINTENANCE", "No open Maintenance")
        if item.completionDate < maintenance["start_date"]:
            raise ApiError(422, "MAINTENANCE_DATE_INVALID", "Completion precedes start")
        await session.execute(
            update(asset_maintenance_history)
            .where(asset_maintenance_history.c.id == maintenance["id"])
            .values(
                completion_date=item.completionDate,
                completed_by_employee_id=actor.employee_id,
                resulting_status=item.resultingStatus,
                completion_notes=item.notes,
            )
        )
        await _event(
            session,
            actor,
            asset,
            action="Maintenance Completed",
            previous="Maintenance",
            current=item.resultingStatus,
            on_date=item.completionDate,
            employee_id=await _last_employee(session, asset_id),
            maintenance_id=maintenance["id"],
            reason=item.notes,
        )
        result = await _current(session, asset_id)
        await complete(session, record_id, 200, result)
        await session.commit()
        return result
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(409, "ASSET_MAINTENANCE_CONFLICT", "Maintenance conflicts") from exc
    except Exception:
        await session.rollback()
        raise


async def mark_damaged(
    session: AsyncSession, actor: Actor, asset_id: UUID, item: AssetDamage, key: str
) -> dict:
    branch_scope(actor, "asset.write")
    try:
        record_id, replay = await claim(
            session,
            actor,
            "asset.damage",
            key,
            {"assetId": str(asset_id), **item.model_dump(mode="json")},
        )
        if replay is not None:
            await session.rollback()
            return replay
        asset = await _locked_asset(session, actor, asset_id)
        if asset["status"] not in {"Available", "Needs Maintenance"}:
            raise ApiError(409, "ASSET_UNAVAILABLE", "Asset cannot be marked Damaged")
        await _event(
            session,
            actor,
            asset,
            action="Damaged",
            previous=asset["status"],
            current="Damaged",
            on_date=item.damageDate,
            employee_id=await _last_employee(session, asset_id),
            reason=item.reason,
        )
        await session.execute(
            update(assets).where(assets.c.id == asset_id).values(status="Damaged")
        )
        result = await _current(session, asset_id)
        await complete(session, record_id, 200, result)
        await session.commit()
        return result
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(409, "ASSET_DAMAGE_CONFLICT", "Asset damage conflicts") from exc
    except Exception:
        await session.rollback()
        raise
