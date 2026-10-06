"""Case-scoped Customer read and Owner identity-correction routes."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.schemas.cases import IdentityCorrection
from app.services import customer_identity, customer_read

router = APIRouter(tags=["customers"])


@router.get("/customers")
async def list_customers(
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    type: str | None = None,
    q: str = Query("", max_length=128),
    sort: str = "createdAt",
    direction: str = "desc",
):
    return await customer_read.list_customers(
        db,
        actor,
        page=page,
        page_size=pageSize,
        customer_type=type,
        q=q,
        sort=sort,
        direction=direction,
    )


@router.get("/customers/{customer_id}")
async def get_customer(customer_id: UUID, db: Db, actor: ActorDep):
    return await customer_read.get_customer(db, actor, customer_id)


@router.post("/customers/{customer_id}/correct-identity", status_code=204)
async def correct_identity(customer_id: UUID, item: IdentityCorrection, db: Db, actor: CsrfActor):
    await customer_identity.correct_identity(db, actor, customer_id, item)
