"""Self-service My Wallet API; always scoped to the signed-in employee."""

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import ActorDep, Db
from app.services import my_wallet

router = APIRouter(tags=["my-wallet"])

WalletKind = Literal["salary_payment", "commission_payment", "commission_earned", "clawback"]


@router.get("/my-wallet/summary")
async def summary(
    db: Db,
    actor: ActorDep,
    periodFrom: date | None = None,
    periodTo: date | None = None,
):
    return await my_wallet.summary(db, actor, start=periodFrom, end=periodTo)


@router.get("/my-wallet/transactions")
async def transactions(
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    periodFrom: date | None = None,
    periodTo: date | None = None,
    kind: WalletKind | None = None,
):
    return await my_wallet.transactions(
        db,
        actor,
        start=periodFrom,
        end=periodTo,
        kind=kind,
        page=page,
        page_size=pageSize,
    )


@router.get("/my-wallet/transactions/{kind}/{record_id}")
async def transaction_detail(kind: WalletKind, record_id: UUID, db: Db, actor: ActorDep):
    return await my_wallet.transaction_detail(db, actor, kind, record_id)
