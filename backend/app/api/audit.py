"""Owner/MD audit search and bounded CSV/PDF downloads."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import AwareDatetime

from app.api.dependencies import ActorDep, Db
from app.policies import require
from app.services import audit_exports, audit_reads

router = APIRouter(tags=["audit"])


@router.get("/audit-events/exports/{format}")
async def export_audit_events(
    format: str,
    actor: ActorDep,
    db: Db,
    actorId: UUID | None = None,
    action: str | None = None,
    module: str | None = None,
    entityId: str | None = None,
    fromTime: AwareDatetime | None = None,
    toTime: AwareDatetime | None = None,
):
    data, media, filename = await audit_exports.export(
        db,
        actor,
        format,
        actor_id=actorId,
        action=action,
        module=module,
        entity_id=entityId,
        from_time=fromTime,
        to_time=toTime,
    )
    return Response(
        content=data,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/audit-events")
async def list_audit_events(
    actor: ActorDep,
    db: Db,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    actorId: UUID | None = None,
    action: str | None = None,
    module: str | None = None,
    entityId: str | None = None,
    fromTime: AwareDatetime | None = None,
    toTime: AwareDatetime | None = None,
    sort: Literal["occurredAt", "action", "module", "entityType", "actorEmployeeId"] = "occurredAt",
    direction: Literal["asc", "desc"] = "desc",
):
    require(actor, "audit.read")
    query = audit_reads.filtered_query(
        actor_id=actorId,
        action=action,
        module=module,
        entity_id=entityId,
        from_time=fromTime,
        to_time=toTime,
    )
    total = await audit_reads.count(db, query)
    result = await audit_reads.rows(
        db, query, (page - 1) * pageSize, pageSize, sort=sort, direction=direction
    )
    items = []
    for row in result:
        items.append(
            {
                "id": str(row["id"]),
                "actorEmployeeId": str(row["actor_employee_id"])
                if row["actor_employee_id"]
                else None,
                "action": row["action"],
                "module": row["module"],
                "entityType": row["entity_type"],
                "entityId": row["entity_id"],
                "occurredAt": row["occurred_at"],
                "context": row["context"],
                "before": row["before_values"],
                "after": row["after_values"],
            }
        )
    return {"items": items, "total": total, "page": page, "pageSize": pageSize}
