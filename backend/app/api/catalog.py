"""Authenticated Bank, Product and Pipeline configuration routes."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.schemas.catalog import (
    BankCreate,
    BankUpdate,
    MappingCreate,
    PipelineCreate,
    ProductCreate,
    ProductUpdate,
    VariantCreate,
    VariantUpdate,
)
from app.services import catalog, pipelines

router = APIRouter(tags=["catalog"])
Kind = Literal["banks", "product-types", "bank-product-mappings", "product-variants"]


@router.get("/catalog/{kind}")
async def list_catalog(
    kind: Kind,
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    active: bool | None = None,
    bankId: UUID | None = None,
    productTypeId: UUID | None = None,
    sort: str = "name",
    direction: str = "asc",
):
    return await catalog.list_records(
        db,
        actor,
        kind,
        page=page,
        page_size=pageSize,
        active=active,
        bank_id=bankId,
        product_id=productTypeId,
        sort=sort,
        direction=direction,
    )


@router.get("/catalog/{kind}/{record_id}")
async def get_catalog(kind: Kind, record_id: UUID, db: Db, actor: ActorDep):
    return await catalog.get_record(db, actor, kind, record_id)


@router.post("/catalog/banks", status_code=201)
async def create_bank(item: BankCreate, db: Db, actor: CsrfActor):
    return await catalog.create_record(db, actor, "banks", {"name": item.name})


@router.patch("/catalog/banks/{record_id}", status_code=204)
async def rename_bank(record_id: UUID, item: BankUpdate, db: Db, actor: CsrfActor):
    await catalog.rename_record(db, actor, "banks", record_id, item.name)


@router.post("/catalog/product-types", status_code=201)
async def create_product(item: ProductCreate, db: Db, actor: CsrfActor):
    return await catalog.create_record(
        db, actor, "product-types", {"code": item.code, "name": item.name}
    )


@router.patch("/catalog/product-types/{record_id}", status_code=204)
async def rename_product(record_id: UUID, item: ProductUpdate, db: Db, actor: CsrfActor):
    await catalog.rename_record(db, actor, "product-types", record_id, item.name)


@router.post("/catalog/bank-product-mappings", status_code=201)
async def create_mapping(item: MappingCreate, db: Db, actor: CsrfActor):
    return await catalog.create_record(
        db,
        actor,
        "bank-product-mappings",
        {
            "bank_id": item.bankId,
            "product_type_id": item.productTypeId,
        },
    )


@router.post("/catalog/product-variants", status_code=201)
async def create_variant(item: VariantCreate, db: Db, actor: CsrfActor):
    return await catalog.create_record(
        db,
        actor,
        "product-variants",
        {
            "bank_id": item.bankId,
            "product_type_id": item.productTypeId,
            "name": item.name,
        },
    )


@router.patch("/catalog/product-variants/{record_id}", status_code=204)
async def rename_variant(record_id: UUID, item: VariantUpdate, db: Db, actor: CsrfActor):
    await catalog.rename_record(db, actor, "product-variants", record_id, item.name)


@router.post("/catalog/{kind}/{record_id}/activate", status_code=204)
async def activate_catalog(kind: Kind, record_id: UUID, db: Db, actor: CsrfActor):
    await catalog.set_active(db, actor, kind, record_id, True)


@router.post("/catalog/{kind}/{record_id}/deactivate", status_code=204)
async def deactivate_catalog(kind: Kind, record_id: UUID, db: Db, actor: CsrfActor):
    await catalog.set_active(db, actor, kind, record_id, False)


@router.get("/pipelines")
async def list_pipelines(
    db: Db,
    actor: ActorDep,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    bankId: UUID | None = None,
    productTypeId: UUID | None = None,
    active: bool | None = None,
    sort: Literal["id", "effectiveDate", "active"] | None = None,
    direction: Literal["asc", "desc"] = "asc",
):
    return await pipelines.list_versions(
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


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: UUID, db: Db, actor: ActorDep):
    return await pipelines.get_version(db, actor, pipeline_id)


@router.post("/pipelines", status_code=201)
async def create_pipeline(item: PipelineCreate, db: Db, actor: CsrfActor):
    return await pipelines.create_version(db, actor, item)


@router.post("/pipelines/{pipeline_id}/activate", status_code=204)
async def activate_pipeline(pipeline_id: UUID, db: Db, actor: CsrfActor):
    await pipelines.set_active(db, actor, pipeline_id, True)


@router.post("/pipelines/{pipeline_id}/deactivate", status_code=204)
async def deactivate_pipeline(pipeline_id: UUID, db: Db, actor: CsrfActor):
    await pipelines.set_active(db, actor, pipeline_id, False)
