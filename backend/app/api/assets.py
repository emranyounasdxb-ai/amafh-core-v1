"""Authorized Asset inventory, lifecycle, retained history, and reports."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Header, Query

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.schemas.assets import (
    AssetCreate,
    AssetDamage,
    AssetDetail,
    AssetIssue,
    AssetMaintenanceComplete,
    AssetMaintenanceStart,
    AssetPage,
    AssetReport,
    AssetResponse,
    AssetReturn,
    AssignmentPage,
    HistoryPage,
    MaintenancePage,
)
from app.services import asset_commands, asset_reads

router = APIRouter(tags=["assets"])


@router.get("/assets", response_model=AssetPage)
async def list_assets(
    db: Db,
    actor: ActorDep,
    branchId: UUID | None = None,
    category: str | None = Query(None, max_length=80),
    status: str | None = Query(None, max_length=30),
    employeeId: UUID | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    sort: str = "createdAt",
    direction: str = "desc",
):
    return await asset_reads.list_assets(
        db,
        actor,
        branch_id=branchId,
        category=category,
        status=status,
        employee_id=employeeId,
        date_from=dateFrom,
        date_to=dateTo,
        search=search,
        page=page,
        page_size=pageSize,
        sort=sort,
        direction=direction,
    )


@router.get("/assets/report", response_model=AssetReport)
async def asset_report(
    db: Db,
    actor: ActorDep,
    branchId: UUID | None = None,
    category: str | None = Query(None, max_length=80),
    status: str | None = Query(None, max_length=30),
    employeeId: UUID | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
):
    return await asset_reads.report(
        db,
        actor,
        branch_id=branchId,
        category=category,
        status=status,
        employee_id=employeeId,
        date_from=dateFrom,
        date_to=dateTo,
        page=page,
        page_size=pageSize,
    )


@router.get("/assets/assignments", response_model=AssignmentPage)
async def asset_assignment_report(
    db: Db,
    actor: ActorDep,
    branchId: UUID | None = None,
    employeeId: UUID | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
):
    return await asset_reads.assignments(
        db,
        actor,
        branch_id=branchId,
        employee_id=employeeId,
        date_from=dateFrom,
        date_to=dateTo,
        page=page,
        page_size=pageSize,
    )


@router.post("/assets", status_code=201, response_model=AssetResponse)
async def create_asset(
    item: AssetCreate,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await asset_commands.create(db, actor, item, idempotency_key)


@router.get("/assets/{asset_id}", response_model=AssetDetail)
async def asset_detail(asset_id: UUID, db: Db, actor: ActorDep):
    return await asset_reads.detail(db, actor, asset_id)


@router.get("/assets/{asset_id}/assignments", response_model=AssignmentPage)
async def asset_assignments_history(
    asset_id: UUID,
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
):
    return await asset_reads.assignments(
        db, actor, asset_id=asset_id, page=page, page_size=pageSize
    )


@router.get("/assets/{asset_id}/maintenance", response_model=MaintenancePage)
async def asset_maintenance_history(
    asset_id: UUID,
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
):
    return await asset_reads.maintenance(db, actor, asset_id, page, pageSize)


@router.get("/assets/{asset_id}/history", response_model=HistoryPage)
async def asset_history(
    asset_id: UUID,
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
):
    return await asset_reads.history(db, actor, asset_id, page, pageSize)


@router.post("/assets/{asset_id}/issue", response_model=AssetResponse)
async def issue_asset(
    asset_id: UUID,
    item: AssetIssue,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await asset_commands.issue(db, actor, asset_id, item, idempotency_key)


@router.post("/assets/{asset_id}/return", response_model=AssetResponse)
async def return_asset(
    asset_id: UUID,
    item: AssetReturn,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await asset_commands.return_asset(db, actor, asset_id, item, idempotency_key)


@router.post("/assets/{asset_id}/maintenance/start", response_model=AssetResponse)
async def start_asset_maintenance(
    asset_id: UUID,
    item: AssetMaintenanceStart,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await asset_commands.start_maintenance(db, actor, asset_id, item, idempotency_key)


@router.post("/assets/{asset_id}/maintenance/complete", response_model=AssetResponse)
async def complete_asset_maintenance(
    asset_id: UUID,
    item: AssetMaintenanceComplete,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await asset_commands.complete_maintenance(db, actor, asset_id, item, idempotency_key)


@router.post("/assets/{asset_id}/damage", response_model=AssetResponse)
async def mark_asset_damaged(
    asset_id: UUID,
    item: AssetDamage,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await asset_commands.mark_damaged(db, actor, asset_id, item, idempotency_key)
