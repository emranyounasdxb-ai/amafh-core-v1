"""Atomic completed-Case financial evidence and exactly-once CC credits."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.cases import product_types
from app.db.finance import case_financial_results
from app.db.operations import financial_rules, points_wallet_transactions, points_wallets
from app.errors import ApiError
from app.policies import Actor
from app.services.cc_salary_points import resolve_points
from app.services.pf_commission import calculate_commission

DUBAI = ZoneInfo("Asia/Dubai")


async def prepare(session: AsyncSession, case: dict, completed_at: datetime) -> dict | None:
    """Resolve the rule before CSV writes; None means a prior credit is retained."""
    existing = (
        (
            await session.execute(
                select(case_financial_results).where(case_financial_results.c.case_id == case["id"])
            )
        )
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        if existing["product_code"] == "PF" and case.get("_csv_final_pf_amount") is not None:
            if case["_csv_final_pf_amount"] != existing["pf_amount_aed"]:
                raise ApiError(
                    422, "PF_RESULT_LOCKED", "Completed PF financial amount is immutable"
                )
        return None
    code = await session.scalar(
        select(product_types.c.code).where(product_types.c.id == case["product_type_id"])
    )
    if code not in {"CC", "PF"}:
        raise ApiError(422, "INVALID_PRODUCT_CONTEXT", "Case has no approved Finance path")
    completion_date = completed_at.astimezone(DUBAI).date()
    conditions = [
        financial_rules.c.bank_id == case["bank_id"],
        financial_rules.c.product_type_id == case["product_type_id"],
        financial_rules.c.effective_date <= completion_date,
    ]
    amount: Decimal | None = None
    if code == "CC":
        conditions.append(financial_rules.c.product_variant_id == case["product_variant_id"])
    else:
        amount = case.get("_csv_final_pf_amount", case.get("final_pf_amount"))
        if amount is None or amount <= 0:
            raise ApiError(
                422, "PF_FINAL_AMOUNT_REQUIRED", "Final PF amount is required for completion"
            )
        conditions += [
            financial_rules.c.product_variant_id.is_(None),
            financial_rules.c.pf_amount_min <= amount,
            financial_rules.c.pf_amount_max >= amount,
        ]
    candidates = (
        (
            await session.execute(
                select(financial_rules)
                .where(*conditions)
                .order_by(
                    financial_rules.c.effective_date.desc(),
                    financial_rules.c.created_at.desc(),
                    financial_rules.c.id,
                )
                .with_for_update(read=True)
            )
        )
        .mappings()
        .all()
    )
    for rule in candidates:
        if not rule["active"]:
            successor_id = rule["superseded_by_rule_id"]
            if successor_id is None:
                continue
            successor_date = await session.scalar(
                select(financial_rules.c.effective_date).where(financial_rules.c.id == successor_id)
            )
            if successor_date is None or completion_date >= successor_date:
                continue
        rate = rule["pf_commission_per_1000"] if code == "PF" else None
        if code == "PF" and rate is None:
            raise ApiError(
                422,
                "PF_RATE_REQUIRED",
                "Replace the legacy PF rule with a commission rate per AED 1,000",
            )
        commission = rule["commission_aed"]
        if code == "PF":
            assert amount is not None and rate is not None
            commission = calculate_commission(amount, rate)
        return {
            "rule_id": rule["id"],
            "rule_effective_date": rule["effective_date"],
            "owner_id": case["owner_employee_id"],
            "product_code": code,
            "cc_points": resolve_points(rule, case["salary_aed"]) if code == "CC" else None,
            "commission_aed": commission,
            "pf_amount_aed": amount if code == "PF" else None,
            "pf_commission_per_1000": rate,
            "pf_amount_basis": "final_approved_disbursed" if code == "PF" else None,
        }
    raise ApiError(422, "FINANCIAL_RULE_MISSING", "No effective Financial Rule matches this Case")


async def apply(
    session: AsyncSession, actor: Actor, case: dict, result: dict | None, completed_at: datetime
) -> None:
    if result is None:
        return
    result_id = uuid4()
    await session.execute(
        case_financial_results.insert().values(
            id=result_id,
            case_id=case["id"],
            financial_rule_id=result["rule_id"],
            credited_owner_employee_id=result["owner_id"],
            product_code=result["product_code"],
            completed_at=completed_at,
            cc_points=result["cc_points"],
            commission_aed=result["commission_aed"],
            pf_amount_aed=result["pf_amount_aed"],
            pf_commission_per_1000=result["pf_commission_per_1000"],
            pf_amount_basis=result["pf_amount_basis"],
            rule_effective_date=result["rule_effective_date"],
        )
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="finance.case_completed",
        module="finance",
        entity_type="case_financial_result",
        entity_id=result_id,
        after={
            "caseId": str(case["id"]),
            "ruleId": str(result["rule_id"]),
            "creditedOwnerEmployeeId": str(result["owner_id"]),
            "productCode": result["product_code"],
            "pfCommissionPer1000": str(result["pf_commission_per_1000"])
            if result["pf_commission_per_1000"] is not None
            else None,
            "pfAmountBasis": result["pf_amount_basis"],
            "points": result["cc_points"],
            "commissionAed": str(result["commission_aed"])
            if result["commission_aed"] is not None
            else None,
            "pfAmountAed": str(result["pf_amount_aed"])
            if result["pf_amount_aed"] is not None
            else None,
            "completedAt": completed_at.isoformat(),
        },
    )
    if result["product_code"] != "CC" or result["cc_points"] is None:
        return
    await session.execute(
        insert(points_wallets)
        .values(id=uuid4(), employee_id=result["owner_id"])
        .on_conflict_do_nothing(index_elements=[points_wallets.c.employee_id])
    )
    wallet_id = await session.scalar(
        select(points_wallets.c.id)
        .where(points_wallets.c.employee_id == result["owner_id"])
        .with_for_update()
    )
    assert wallet_id is not None
    transaction_id = uuid4()
    await session.execute(
        points_wallet_transactions.insert().values(
            id=transaction_id,
            wallet_id=wallet_id,
            case_id=case["id"],
            points_credited=result["cc_points"],
            occurred_at=completed_at,
        )
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="finance.wallet_credited",
        module="finance",
        entity_type="points_wallet_transaction",
        entity_id=transaction_id,
        after={
            "walletId": str(wallet_id),
            "caseId": str(case["id"]),
            "pointsCredited": result["cc_points"],
            "ruleId": str(result["rule_id"]),
        },
    )
