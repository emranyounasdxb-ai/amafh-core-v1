"""Private Phase 3 Finance API with server-owned scope and CSRF."""

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.schemas.finance import ClawbackInput, FinancialRuleInput, PaymentInput
from app.services import finance_reads, finance_records, finance_rules

router = APIRouter(tags=["finance"])


@router.get("/finance/rules")
async def rules(
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    bankId: UUID | None = None,
    productTypeId: UUID | None = None,
    active: bool | None = None,
    sort: Literal["id", "effectiveDate", "ccPoints", "commissionAed", "active"] | None = None,
    direction: Literal["asc", "desc"] = "asc",
):
    return await finance_rules.list_rules(
        db,
        actor,
        page=page,
        page_size=pageSize,
        bank_id=bankId,
        product_id=productTypeId,
        active=active,
        sort=sort,
        direction=direction,
    )


@router.get("/finance/rules/{rule_id}")
async def rule_detail(rule_id: UUID, db: Db, actor: ActorDep):
    return await finance_rules.get_rule(db, actor, rule_id)


@router.post("/finance/rules", status_code=201)
async def create_rule(item: FinancialRuleInput, db: Db, actor: CsrfActor):
    return await finance_rules.create(db, actor, item)


@router.post("/finance/rules/{rule_id}/replace", status_code=201)
async def replace_rule(rule_id: UUID, item: FinancialRuleInput, db: Db, actor: CsrfActor):
    return await finance_rules.replace(db, actor, rule_id, item)


@router.post("/finance/rules/{rule_id}/activate", status_code=204)
async def activate_rule(rule_id: UUID, db: Db, actor: CsrfActor):
    await finance_rules.set_active(db, actor, rule_id, True)


@router.post("/finance/rules/{rule_id}/deactivate", status_code=204)
async def deactivate_rule(rule_id: UUID, db: Db, actor: CsrfActor):
    await finance_rules.set_active(db, actor, rule_id, False)


@router.get("/finance/completed-cases")
async def completed_cases(
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    branchId: UUID | None = None,
    productCode: Literal["CC", "PF"] | None = None,
    completedFrom: date | None = None,
    completedTo: date | None = None,
    sort: Literal["internalCaseId", "productCode", "completedAt", "ccPoints", "commissionAed"]
    | None = None,
    direction: Literal["asc", "desc"] = "asc",
):
    return await finance_reads.completed_cases(
        db,
        actor,
        page=page,
        page_size=pageSize,
        branch_id=branchId,
        product_code=productCode,
        completed_from=completedFrom,
        completed_to=completedTo,
        sort=sort,
        direction=direction,
    )


@router.get("/finance/completed-cases/{case_id}")
async def completed_case_detail(case_id: UUID, db: Db, actor: ActorDep):
    return await finance_reads.completed_case_detail(db, actor, case_id)


@router.get("/finance/wallets")
async def wallets(
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    employeeId: UUID | None = None,
    sort: Literal["employeeName", "balancePoints"] | None = None,
    direction: Literal["asc", "desc"] = "asc",
):
    return await finance_reads.list_wallets(
        db,
        actor,
        page=page,
        page_size=pageSize,
        employee_id=employeeId,
        sort=sort,
        direction=direction,
    )


@router.get("/finance/wallets/{employee_id}")
async def wallet_detail(
    employee_id: UUID,
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
):
    return await finance_reads.wallet_detail(db, actor, employee_id, page=page, page_size=pageSize)


@router.get("/finance/clawbacks")
async def clawbacks(
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    branchId: UUID | None = None,
    caseId: UUID | None = None,
    sort: Literal["internalCaseId", "amountAed", "clawbackDate", "reason"] | None = None,
    direction: Literal["asc", "desc"] = "asc",
):
    return await finance_reads.list_clawbacks(
        db,
        actor,
        page=page,
        page_size=pageSize,
        branch_id=branchId,
        case_id=caseId,
        sort=sort,
        direction=direction,
    )


@router.get("/finance/clawbacks/{record_id}")
async def clawback_detail(record_id: UUID, db: Db, actor: ActorDep):
    return await finance_reads.clawback_detail(db, actor, record_id)


@router.post("/finance/clawbacks", status_code=201)
async def create_clawback(
    item: ClawbackInput,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await finance_records.create_clawback(db, actor, item, idempotency_key)


@router.get("/finance/payments")
async def payments(
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    employeeId: UUID | None = None,
    paymentType: Literal["Salary", "Commission"] | None = None,
    paymentFrom: date | None = None,
    paymentTo: date | None = None,
    sort: Literal["employeeName", "paymentType", "amountAed", "paymentMonth", "paymentDate"]
    | None = None,
    direction: Literal["asc", "desc"] = "asc",
):
    return await finance_reads.list_payments(
        db,
        actor,
        page=page,
        page_size=pageSize,
        employee_id=employeeId,
        payment_type=paymentType,
        payment_from=paymentFrom,
        payment_to=paymentTo,
        sort=sort,
        direction=direction,
    )


@router.get("/finance/payments/{record_id}")
async def payment_detail(record_id: UUID, db: Db, actor: ActorDep):
    return await finance_reads.payment_detail(db, actor, record_id)


@router.get("/finance/payments/employee/{employee_id}")
async def payment_history(
    employee_id: UUID,
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    paymentType: Literal["Salary", "Commission"] | None = None,
    paymentFrom: date | None = None,
    paymentTo: date | None = None,
):
    return await finance_reads.employee_payment_history(
        db,
        actor,
        employee_id,
        page=page,
        page_size=pageSize,
        payment_type=paymentType,
        payment_from=paymentFrom,
        payment_to=paymentTo,
    )


@router.post("/finance/payments", status_code=201)
async def create_payment(
    item: PaymentInput,
    db: Db,
    actor: CsrfActor,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await finance_records.create_payment(db, actor, item, idempotency_key)


@router.get("/employees/me/clawback-mentions")
async def my_clawback_mentions(
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
):
    return await finance_reads.own_clawback_mentions(db, actor, page=page, page_size=pageSize)
