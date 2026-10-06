"""Bounded, metadata-only audit exports with an explicit readable column list."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.assets import assets
from app.db.cases import cases, customers
from app.db.organization import employees
from app.errors import ApiError
from app.policies import Actor, require
from app.services import audit_reads
from app.services.performance_math import DUBAI
from app.services.report_exports import (
    CSV_ROWS,
    LABEL_CHUNK,
    PDF_ROWS,
    ExportLimitError,
    person_label,
    readable_code,
    readable_value,
    reference,
    relation_labels,
    render_csv,
    render_pdf,
)
from app.services.table_export_spec import ExportColumn

COLUMNS = (
    ExportColumn("Occurred At (Dubai)", "occurredAt", "dubai_time"),
    ExportColumn("Event", "action", "label"),
    ExportColumn("Module", "module", "label"),
    ExportColumn("Record Type", "entityType", "label"),
    ExportColumn("Record", "entityId", "record"),
    ExportColumn("Actor", "actorEmployeeId", "employee"),
    ExportColumn("Actor Code", "actorEmployeeId", "employee_code"),
)
RECORD_SOURCES = (
    (cases.c.id, cases.c.internal_case_id),
    (customers.c.id, customers.c.customer_id),
    (assets.c.id, assets.c.asset_code),
)


async def record_labels(
    session: AsyncSession, actor: Actor, ids: set[UUID]
) -> dict[tuple[str, str], str]:
    """Audit record references resolve to business labels for audit readers only."""
    if not ids or "audit.read" not in actor.grants:
        return {}
    kinds = ("employee", "team", "branch", "department", "bank", "designation")
    found = await relation_labels(session, actor, {kind: set(ids) for kind in kinds})
    labels: dict[tuple[str, str], str] = {}
    for ident in ids:
        key = str(ident)
        label = person_label(found, ident) or next(
            (found[(kind, key)] for kind in kinds[1:] if (kind, key) in found), None
        )
        if label:
            labels[("record", key)] = label
    remaining = sorted(ident for ident in ids if ("record", str(ident)) not in labels)
    for key_column, label_column in RECORD_SOURCES:
        for start in range(0, len(remaining), LABEL_CHUNK):
            chunk = remaining[start : start + LABEL_CHUNK]
            for ident, label in await session.execute(
                select(key_column, label_column).where(key_column.in_(chunk))
            ):
                if label:
                    labels[("record", str(ident))] = label
    return labels


async def _record_label(session: AsyncSession, actor: Actor, entity_id: str) -> str:
    """A record reference filter is shown by its business label, never by its identifier."""
    ident = reference(entity_id)
    if ident is None:
        return "Applied"
    labels = await record_labels(session, actor, {ident})
    return labels.get(("record", str(ident)), "Applied")


def _dubai_minute(value: datetime) -> str:
    return value.astimezone(DUBAI).strftime("%Y-%m-%d %H:%M")


async def export(
    session: AsyncSession,
    actor: Actor,
    format: str,
    *,
    actor_id: UUID | None = None,
    action: str | None = None,
    module: str | None = None,
    entity_id: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> tuple[bytes, str, str]:
    require(actor, "audit.read")
    if format not in {"csv", "pdf"}:
        raise ApiError(404, "NOT_FOUND", "Export format unavailable")
    filter_names = sorted(
        key
        for key, value in {
            "actorId": actor_id,
            "action": action,
            "module": module,
            "entityId": entity_id,
            "fromTime": from_time,
            "toTime": to_time,
        }.items()
        if value is not None
    )
    query = audit_reads.filtered_query(
        actor_id=actor_id,
        action=action,
        module=module,
        entity_id=entity_id,
        from_time=from_time,
        to_time=to_time,
    )
    total = await audit_reads.count(session, query)
    limit = CSV_ROWS if format == "csv" else PDF_ROWS
    metadata = {"format": format, "filterNames": filter_names, "rowCount": total}
    if total > limit:
        await audit.record(
            session,
            actor=actor.employee_id,
            action="audit.export_rejected",
            module="audit",
            context={**metadata, "reason": "row_limit", "rowLimit": limit},
        )
        await session.commit()
        raise ExportLimitError(
            "EXPORT_ROWS_LIMIT",
            f"{format.upper()} export exceeds {limit:,} data rows",
            "rowCount",
            total,
            limit,
        )
    rows = [
        {
            "occurredAt": row["occurred_at"],
            "actorEmployeeId": str(row["actor_employee_id"]) if row["actor_employee_id"] else "",
            "action": row["action"],
            "module": row["module"],
            "entityType": row["entity_type"] or "",
            "entityId": row["entity_id"] or "",
        }
        for row in await audit_reads.rows(session, query, 0, limit)
    ]
    actors = {ident for row in rows if (ident := reference(row["actorEmployeeId"]))}
    if actor_id is not None:
        actors.add(actor_id)
    labels = await relation_labels(session, actor, {"employee": actors})
    labels.update(
        await record_labels(
            session, actor, {ident for row in rows if (ident := reference(row["entityId"]))}
        )
    )
    filters: dict[str, str] = {}
    if actor_id is not None:
        filters["Actor"] = person_label(labels, actor_id) or "Unavailable"
    if action is not None:
        filters["Event"] = readable_code(action)
    if module is not None:
        filters["Module"] = readable_code(module)
    if entity_id is not None:
        filters["Record reference"] = await _record_label(session, actor, entity_id)
    if from_time is not None:
        filters["From (Dubai)"] = _dubai_minute(from_time)
    if to_time is not None:
        filters["To (Dubai)"] = _dubai_minute(to_time)
    result = {
        "title": "Audit Events",
        "startDate": from_time.astimezone(DUBAI).date().isoformat() if from_time else "All",
        "endDate": to_time.astimezone(DUBAI).date().isoformat() if to_time else "All",
        "filters": filters,
        "summary": {"Events": total},
        "columns": [{"key": column.heading, "heading": column.heading} for column in COLUMNS],
        "items": [
            {column.heading: readable_value(column, row, labels) for column in COLUMNS}
            for row in rows
        ],
    }
    try:
        if format == "csv":
            data, media = render_csv(result), "text/csv; charset=utf-8"
        else:
            code = await session.scalar(
                select(employees.c.system_employee_code).where(employees.c.id == actor.employee_id)
            )
            data, media = render_pdf(result, actor.display_name, code or ""), "application/pdf"
    except ApiError as error:
        await audit.record(
            session,
            actor=actor.employee_id,
            action="audit.export_rejected",
            module="audit",
            context={
                **metadata,
                "reason": error.code,
                **(
                    {error.metric: error.count, error.metric.replace("Count", "Limit"): error.limit}
                    if isinstance(error, ExportLimitError)
                    else {}
                ),
            },
        )
        await session.commit()
        raise
    await audit.record(
        session,
        actor=actor.employee_id,
        action="audit.exported",
        module="audit",
        context={**metadata, "byteSize": len(data)},
    )
    await session.commit()
    stamp = datetime.now(DUBAI).strftime("%Y%m%d-%H%M%S")
    return data, media, f"amafh-core-audit-events-{stamp}.{format}"
