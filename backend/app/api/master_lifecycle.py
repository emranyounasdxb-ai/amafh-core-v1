"""Organization master rename/reparent and controlled activation routes."""

from uuid import UUID

from fastapi import APIRouter

from app.api.dependencies import CsrfActor, Db
from app.db.organization import branches, business_units, departments
from app.schemas.organization import BranchUpdate, DepartmentUpdate, NamedUpdate
from app.services.master_lifecycle import activate_master, deactivate_master, update_master

router = APIRouter(tags=["organization"])


@router.patch("/business-units/{record_id}", status_code=204)
async def update_business_unit(record_id: UUID, item: NamedUpdate, actor: CsrfActor, db: Db):
    await update_master(db, actor, business_units, record_id, {"name": item.name})


@router.post("/business-units/{record_id}/deactivate", status_code=204)
async def deactivate_business_unit(record_id: UUID, actor: CsrfActor, db: Db):
    await deactivate_master(db, actor, business_units, record_id)


@router.post("/business-units/{record_id}/activate", status_code=204)
async def activate_business_unit(record_id: UUID, actor: CsrfActor, db: Db):
    await activate_master(db, actor, business_units, record_id)


@router.patch("/branches/{record_id}", status_code=204)
async def update_branch(record_id: UUID, item: BranchUpdate, actor: CsrfActor, db: Db):
    values: dict = {"name": item.name}
    if "businessUnitId" in item.model_fields_set:
        values["business_unit_id"] = item.businessUnitId
    if "operatingCity" in item.model_fields_set:
        values["operating_city"] = item.operatingCity
    await update_master(db, actor, branches, record_id, values)


@router.post("/branches/{record_id}/deactivate", status_code=204)
async def deactivate_branch(record_id: UUID, actor: CsrfActor, db: Db):
    await deactivate_master(db, actor, branches, record_id)


@router.post("/branches/{record_id}/activate", status_code=204)
async def activate_branch(record_id: UUID, actor: CsrfActor, db: Db):
    await activate_master(db, actor, branches, record_id)


@router.patch("/departments/{record_id}", status_code=204)
async def update_department(record_id: UUID, item: DepartmentUpdate, actor: CsrfActor, db: Db):
    values: dict = {"name": item.name}
    if "productTypeId" in item.model_fields_set:
        values["product_type_id"] = item.productTypeId
    await update_master(db, actor, departments, record_id, values)


@router.post("/departments/{record_id}/deactivate", status_code=204)
async def deactivate_department(record_id: UUID, actor: CsrfActor, db: Db):
    await deactivate_master(db, actor, departments, record_id)


@router.post("/departments/{record_id}/activate", status_code=204)
async def activate_department(record_id: UUID, actor: CsrfActor, db: Db):
    await activate_master(db, actor, departments, record_id)
