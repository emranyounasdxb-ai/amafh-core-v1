"""Uploader-scoped retained Bank-stage CSV batch results."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.attendance import csv_import_batches, csv_import_row_results
from app.db.organization import employees
from app.errors import ApiError
from app.policies import Actor


def _has_csv(actor: Actor) -> bool:
    return "case.csv" in actor.grants


async def visible_batch(session: AsyncSession, actor: Actor, batch_id: UUID):
    if not _has_csv(actor):
        return None
    return (
        (
            await session.execute(
                select(csv_import_batches).where(
                    csv_import_batches.c.id == batch_id,
                    csv_import_batches.c.kind == "bank_stage",
                    csv_import_batches.c.uploaded_by_employee_id == actor.employee_id,
                )
            )
        )
        .mappings()
        .one_or_none()
    )


def _row_public(row) -> dict:
    return {
        "rowNumber": row["row_number"],
        "internalCaseId": row["internal_case_id"],
        "bankCaseNumber": row["bank_case_number"],
        "productLabel": row["product_label"],
        "currentStage": row["current_stage"],
        "requestedStage": row["requested_stage"],
        "status": row["status"],
        "errorCode": row["error_code"],
        "errorDetail": row["error_detail"],
    }


def _counts(rows) -> dict:
    valid = sum(row["status"] in {"Valid", "Applied", "Unchanged", "Skipped"} for row in rows)
    invalid = sum(row["status"] in {"Invalid", "Rejected"} for row in rows)
    updated = sum(row["status"] == "Applied" for row in rows)
    unchanged = sum(row["status"] in {"Unchanged", "Skipped"} for row in rows)
    return {
        "totalCount": len(rows),
        "validCount": valid,
        "invalidCount": invalid,
        "appliedCount": updated,
        "unchangedCount": unchanged,
        "eligibleCount": valid if invalid == 0 and updated == 0 else 0,
    }


def _created_at(value) -> str | None:
    return value.isoformat() if value is not None else None


def _batch_public(batch, rows, uploader_name: str | None) -> dict:
    counts = _counts(rows)
    validation = batch["validation_status"] or (
        "Validated" if batch["status"] in {"Validated", "Applied"} else "Rejected"
    )
    return {
        "batchId": str(batch["id"]),
        "fileName": batch["file_name"],
        "uploaderName": uploader_name,
        "status": batch["status"],
        "validationStatus": validation,
        "createdAt": _created_at(batch["created_at"]),
        **counts,
        "rowResults": [_row_public(row) for row in rows],
    }


async def _uploader_name(session: AsyncSession, employee_id) -> str | None:
    return await session.scalar(select(employees.c.full_name).where(employees.c.id == employee_id))


async def detail(session: AsyncSession, actor: Actor, batch_id: UUID) -> dict:
    batch = await visible_batch(session, actor, batch_id)
    if batch is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    rows = (
        (
            await session.execute(
                select(csv_import_row_results)
                .where(csv_import_row_results.c.batch_id == batch_id)
                .order_by(csv_import_row_results.c.row_number)
            )
        )
        .mappings()
        .all()
    )
    return _batch_public(
        batch, rows, await _uploader_name(session, batch["uploaded_by_employee_id"])
    )


async def list_batches(
    session: AsyncSession,
    actor: Actor,
    *,
    page: int,
    page_size: int,
) -> dict:
    if not _has_csv(actor):
        raise ApiError(403, "FORBIDDEN", "This action is not available")
    conditions = [
        csv_import_batches.c.kind == "bank_stage",
        csv_import_batches.c.uploaded_by_employee_id == actor.employee_id,
    ]
    total = (
        await session.scalar(
            select(func.count()).select_from(csv_import_batches).where(*conditions)
        )
        or 0
    )
    batches = (
        (
            await session.execute(
                select(csv_import_batches)
                .where(*conditions)
                .order_by(csv_import_batches.c.created_at.desc(), csv_import_batches.c.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    items = []
    for batch in batches:
        rows = (
            (
                await session.execute(
                    select(
                        csv_import_row_results.c.status,
                    ).where(csv_import_row_results.c.batch_id == batch["id"])
                )
            )
            .mappings()
            .all()
        )
        counts = _counts(rows)
        validation = batch["validation_status"] or (
            "Validated" if batch["status"] in {"Validated", "Applied"} else "Rejected"
        )
        items.append(
            {
                "batchId": str(batch["id"]),
                "fileName": batch["file_name"],
                "uploaderName": await _uploader_name(session, batch["uploaded_by_employee_id"]),
                "createdAt": _created_at(batch["created_at"]),
                "validationStatus": validation,
                "status": batch["status"],
                "totalCount": batch["data_row_count"]
                if batch["data_row_count"] is not None
                else counts["totalCount"],
                "validCount": counts["validCount"],
                "invalidCount": counts["invalidCount"],
                "appliedCount": batch["applied_count"]
                if batch["applied_count"] is not None
                else counts["appliedCount"],
            }
        )
    return {"items": items, "total": total, "page": page, "pageSize": page_size}
