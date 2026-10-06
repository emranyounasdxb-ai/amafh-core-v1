"""Scoped Case creation, queues, details and history."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Header, Query, UploadFile
from fastapi.responses import Response

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.policies import require
from app.schemas.cases import (
    ApprovalInput,
    BookingInput,
    CaseCreate,
    ConfirmedAction,
    OwnerCorrection,
)
from app.services import (
    case_corrections,
    case_creation,
    case_csv,
    case_import_reads,
    case_read,
    case_transitions,
    case_void,
)

router = APIRouter(tags=["cases"])


@router.post("/cases", status_code=201)
async def create_case(
    item: CaseCreate,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await case_creation.create_case(db, actor, item, idempotency_key)


@router.post("/my-cases", status_code=201)
async def create_own_case(
    item: CaseCreate,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await case_creation.create_case(db, actor, item, idempotency_key, personal=True)


@router.get("/my-cases")
async def list_own_cases(
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    q: str = Query("", max_length=128),
    status: str | None = None,
    bankId: UUID | None = None,
    productTypeId: UUID | None = None,
    ownerEmployeeId: UUID | None = None,
    createdFrom: date | None = None,
    createdTo: date | None = None,
    sort: str = "createdAt",
    direction: str = "desc",
    view: str = "active",
):
    return await case_read.list_cases(
        db,
        actor,
        page=page,
        page_size=pageSize,
        q=q,
        status=status,
        bank_id=bankId,
        product_id=productTypeId,
        owner_id=ownerEmployeeId,
        created_from=createdFrom,
        created_to=createdTo,
        sort=sort,
        direction=direction,
        view=view,
        own=True,
    )


@router.get("/cases")
async def list_cases(
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    q: str = Query("", max_length=128),
    status: str | None = None,
    bankId: UUID | None = None,
    productTypeId: UUID | None = None,
    ownerEmployeeId: UUID | None = None,
    createdFrom: date | None = None,
    createdTo: date | None = None,
    sort: str = "createdAt",
    direction: str = "desc",
    view: str = "active",
):
    return await case_read.list_cases(
        db,
        actor,
        page=page,
        page_size=pageSize,
        q=q,
        status=status,
        bank_id=bankId,
        product_id=productTypeId,
        owner_id=ownerEmployeeId,
        created_from=createdFrom,
        created_to=createdTo,
        sort=sort,
        direction=direction,
        view=view,
    )


@router.get("/cases/approval-queue")
async def approval_queue(
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    q: str = Query("", max_length=128),
    sort: str = "createdAt",
    direction: str = "desc",
):
    return await case_read.list_cases(
        db,
        actor,
        page=page,
        page_size=pageSize,
        q=q,
        approval_queue=True,
        sort=sort,
        direction=direction,
    )


@router.get("/cases/{case_id}")
async def get_case(case_id: UUID, db: Db, actor: ActorDep):
    return await case_read.get_case(db, actor, case_id)


@router.get("/cases/{case_id}/history")
async def get_history(case_id: UUID, db: Db, actor: ActorDep):
    return await case_read.get_history(db, actor, case_id)


@router.post("/cases/{case_id}/approval")
async def approve_case(
    case_id: UUID,
    item: ApprovalInput,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await case_transitions.approve(
        db, actor, case_id, item.coordinatorEmployeeId, idempotency_key
    )


@router.post("/cases/{case_id}/booking")
async def book_case(
    case_id: UUID,
    item: BookingInput,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await case_transitions.book(db, actor, case_id, item.bankCaseNumber, idempotency_key)


@router.get("/case-imports/bank-stage/template")
async def bank_stage_template(actor: ActorDep):
    require(actor, "case.csv")
    return Response(
        content=case_csv.TEMPLATE,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="bank-stage-template.csv"'},
    )


@router.post("/case-imports/bank-stage")
async def import_bank_stages(
    db: Db,
    actor: CsrfActor,
    file: UploadFile,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    require(actor, "case.csv")
    content, digest, too_large = await case_csv.read_upload(file)
    return await case_csv.import_stages(
        db,
        actor,
        content,
        idempotency_key,
        content_hash=digest,
        too_large=too_large,
        file_name=file.filename,
    )


@router.post("/case-imports/bank-stage/validations")
async def validate_bank_stages(
    db: Db,
    actor: CsrfActor,
    file: UploadFile,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    require(actor, "case.csv")
    content, digest, too_large = await case_csv.read_upload(file)
    return await case_csv.validate_stages(
        db,
        actor,
        content,
        idempotency_key,
        content_hash=digest,
        too_large=too_large,
        file_name=file.filename,
    )


@router.post("/case-imports/bank-stage/{batch_id}/apply")
async def apply_bank_stages(
    batch_id: UUID,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    require(actor, "case.csv")
    return await case_csv.apply_validated_batch(db, actor, batch_id, idempotency_key)


@router.get("/case-imports/bank-stage")
async def bank_stage_import_history(
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
):
    require(actor, "case.csv")
    return await case_import_reads.list_batches(db, actor, page=page, page_size=pageSize)


@router.get("/case-imports/bank-stage/{batch_id}")
async def bank_stage_import_result(batch_id: UUID, db: Db, actor: ActorDep):
    return await case_import_reads.detail(db, actor, batch_id)


@router.post("/cases/{case_id}/correction")
async def correct_case(case_id: UUID, item: OwnerCorrection, db: Db, actor: CsrfActor):
    return await case_corrections.correct(db, actor, case_id, item)


@router.post("/cases/{case_id}/reopen")
async def reopen_case(case_id: UUID, item: ConfirmedAction, db: Db, actor: CsrfActor):
    return await case_corrections.reopen(db, actor, case_id, item)


@router.post("/cases/{case_id}/administrative-void")
async def administratively_void_case(
    case_id: UUID, item: ConfirmedAction, db: Db, actor: CsrfActor
):
    return await case_void.administratively_void(db, actor, case_id, item)
