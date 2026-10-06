"""Bounded Owner and Managing Director CSV exports for connected tables."""

import json
import re

from fastapi import APIRouter, Request, Response
from pydantic import ValidationError

from app.api.dependencies import CsrfActor, Db
from app.audit import record
from app.errors import ApiError
from app.policies import MD, OWNER
from app.services import table_exports
from app.services.table_exports import TableExportInput

router = APIRouter(tags=["reports"])
MAX_REQUEST_BYTES = 4_000_000


def _invalid(message: str = "Invalid table export request") -> ApiError:
    return ApiError(422, "VALIDATION_ERROR", message)


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Repeated JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ValueError("Non-finite JSON value")


def _bounded_shape(value: object, depth: int = 0) -> None:
    if depth > 3:
        raise ValueError("Nested export request")
    if isinstance(value, dict):
        if len(value) > 5 or any(not isinstance(key, str) or len(key) > 32 for key in value):
            raise ValueError("Too many export fields")
        for child in value.values():
            _bounded_shape(child, depth + 1)
    elif isinstance(value, list):
        if len(value) > table_exports.CSV_ROWS:
            raise ValueError("Too many selections")
        for child in value:
            _bounded_shape(child, depth + 1)
    elif isinstance(value, str) and len(value) > 2048:
        raise ValueError("Oversized export value")


async def _parse_request(request: Request) -> TableExportInput:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise _invalid()
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1 or (lengths and not re.fullmatch(r"[0-9]+", lengths[0])):
        raise _invalid()
    declared = int(lengths[0]) if lengths else None
    if declared is not None and declared > MAX_REQUEST_BYTES:
        raise _invalid("Table export request exceeds 4,000,000 bytes")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_REQUEST_BYTES:
            raise _invalid("Table export request exceeds 4,000,000 bytes")
        body.extend(chunk)
    if declared is not None and declared != len(body):
        raise _invalid()
    try:
        value = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
        _bounded_shape(value)
        return TableExportInput.model_validate(value)
    except (UnicodeDecodeError, ValueError, RecursionError, ValidationError) as error:
        raise _invalid() from error


@router.post("/table-exports/csv")
async def export_table_csv(request: Request, actor: CsrfActor, db: Db):
    if actor.designation not in {OWNER, MD}:
        raise ApiError(403, "FORBIDDEN", "Access denied")
    try:
        item = await _parse_request(request)
    except ApiError as error:
        await record(
            db,
            actor=actor.employee_id,
            action="table.export_rejected",
            module="reports",
            context={"format": "csv", "reason": error.code},
        )
        await db.commit()
        raise
    data, filename = await table_exports.export(db, actor, request, item)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
