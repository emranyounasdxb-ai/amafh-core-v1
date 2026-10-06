"""Audited table CSV generated from the existing authorized API projections."""

import asyncio
import json
import math
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit
from uuid import UUID

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Table, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record
from app.db.cases import banks, product_types, product_variants
from app.db.organization import (
    branches,
    business_units,
    departments,
    designations,
    employees,
    teams,
)
from app.db.session import session_factory
from app.errors import ApiError
from app.policies import EMPLOYEE_SCOPE, MD, OWNER, Actor
from app.services.audit_exports import record_labels
from app.services.report_exports import (
    CSV_ROWS,
    ExportLimitError,
    readable_value,
    reference,
    render_csv,
)
from app.services.table_export_spec import TableSpec, resolve

LOOKUP_TABLES: dict[str, Table] = {
    "employee": employees,
    "employee_code": employees,
    "branch": branches,
    "department": departments,
    "bank": banks,
    "product": product_types,
    "variant": product_variants,
    "business_unit": business_units,
    "designation": designations,
    "team": teams,
}
LOOKUP_CHUNK = 5_000


class SelectionRef(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    index: int = Field(ge=0, le=10_000_000)
    fingerprint: str = Field(min_length=16, max_length=16, pattern=r"^[0-9a-f]{16}$")


class TableExportInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    sourcePath: str = Field(min_length=1, max_length=2048)
    mode: Literal["selected", "all"]
    allMatching: bool = False
    expectedTotal: int | None = Field(default=None, ge=0, le=10_000_000)
    selections: list[SelectionRef] = Field(default_factory=list, max_length=CSV_ROWS)

    @model_validator(mode="after")
    def valid_selection(self) -> TableExportInput:
        if len({item.index for item in self.selections}) != len(self.selections):
            raise ValueError("Selection identifiers must be unique")
        if self.mode == "all":
            if self.allMatching or self.selections or self.expectedTotal is not None:
                raise ValueError("Export All does not accept row selections")
        elif self.expectedTotal is None or (not self.allMatching and not self.selections):
            raise ValueError("Export Selected requires a current selection")
        return self


def _number_text(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise ValueError("Non-finite table value")
    if value == 0:
        return "0"
    decimal = Decimal(repr(value))
    if Decimal("0.000001") <= abs(decimal) < Decimal("1e21"):
        result = format(decimal, "f")
        return result.rstrip("0").rstrip(".") if "." in result else result
    mantissa, exponent = format(decimal.normalize(), "e").split("e")
    mantissa = mantissa.rstrip("0").rstrip(".") if "." in mantissa else mantissa
    return f"{mantissa}e{int(exponent):+d}" if int(exponent) >= 0 else f"{mantissa}e{int(exponent)}"


def _canonical(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, (int, float)):
        return _number_text(value)
    if isinstance(value, list):
        return "[" + ",".join(_canonical(item) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(
                f"{json.dumps(key, ensure_ascii=False)}:{_canonical(value[key])}"
                for key in sorted(value)
            )
            + "}"
        )
    raise ValueError("Unsupported table value")


def row_fingerprint(row: dict) -> str:
    value = 0xCBF29CE484222325
    for byte in _canonical(row).encode("utf-8"):
        value = ((value ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{value:016x}"


async def _authorized_page(
    request: Request, source: str, read_session: AsyncSession, actor: Actor
) -> dict | list:
    """Route a scoped GET through the real API while sharing its read-only snapshot."""
    parsed = urlsplit(source)
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": request.url.scheme,
        "path": f"/api/v1{parsed.path}",
        "raw_path": f"/api/v1{parsed.path}".encode("ascii"),
        "query_string": parsed.query.encode("ascii"),
        "root_path": "",
        "headers": [],
        "client": request.client,
        "server": request.scope.get("server"),
        "state": {"_table_export_read_session": read_session, "_table_export_actor": actor},
    }
    sent = False
    status = 500
    body = bytearray()

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.sleep(3600)
        return {"type": "http.disconnect"}

    async def send(message):
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]
        elif message["type"] == "http.response.body":
            body.extend(message.get("body", b""))

    await request.app(scope, receive, send)
    if status != 200:
        raise ApiError(422, "TABLE_EXPORT_SOURCE_UNAVAILABLE", "Table data is unavailable")
    try:
        result = json.loads(body)
    except (ValueError, UnicodeDecodeError) as error:
        raise ApiError(502, "TABLE_EXPORT_SOURCE_INVALID", "Table data is unavailable") from error
    if not isinstance(result, (dict, list)):
        raise ApiError(502, "TABLE_EXPORT_SOURCE_INVALID", "Table data is unavailable")
    return result


def _page_path(source: str, page: int) -> str:
    parsed = urlsplit(source)
    query = [
        (key, value) for key, value in parse_qsl(parsed.query) if key not in {"page", "pageSize"}
    ]
    query.extend((("page", str(page)), ("pageSize", "100")))
    return f"{parsed.path}?{urlencode(query)}"


def _items(result: dict | list, paged: bool) -> tuple[list[dict], int]:
    if isinstance(result, list):
        if paged or not all(isinstance(row, dict) for row in result):
            raise ApiError(502, "TABLE_EXPORT_SOURCE_INVALID", "Table data is unavailable")
        return result, len(result)
    rows = result.get("items")
    total = result.get("total", len(rows) if isinstance(rows, list) else None)
    if not isinstance(rows, list) or not isinstance(total, int) or total < 0:
        raise ApiError(502, "TABLE_EXPORT_SOURCE_INVALID", "Table data is unavailable")
    if not all(isinstance(row, dict) for row in rows):
        raise ApiError(502, "TABLE_EXPORT_SOURCE_INVALID", "Table data is unavailable")
    return rows, total


def _stale() -> ApiError:
    return ApiError(
        409, "TABLE_SELECTION_STALE", "Table selection changed. Refresh and select again"
    )


async def _collect(
    request: Request,
    spec: TableSpec,
    source: str,
    item: TableExportInput,
    read_session: AsyncSession,
    actor: Actor,
) -> tuple[list[dict], int]:
    first = await _authorized_page(
        request, _page_path(source, 1) if spec.paged else source, read_session, actor
    )
    first_rows, total = _items(first, spec.paged)
    all_rows = item.mode == "all" or item.allMatching
    if item.mode == "selected" and item.expectedTotal != total:
        raise _stale()
    if not all_rows and not item.selections:
        raise ApiError(422, "TABLE_SELECTION_EMPTY", "Select at least one row")
    by_index = {entry.index: entry.fingerprint for entry in item.selections}
    if any(index >= total for index in by_index):
        raise _stale()
    selected_count = total - len(by_index) if all_rows else len(by_index)
    if selected_count > CSV_ROWS:
        raise ExportLimitError(
            "EXPORT_ROWS_LIMIT",
            "CSV export exceeds 50,000 data rows",
            "rowCount",
            selected_count,
            CSV_ROWS,
        )
    pages = (
        range(1, (total + 99) // 100 + 1)
        if all_rows and spec.paged
        else sorted({index // 100 + 1 for index in by_index})
        if spec.paged
        else (1,)
    )
    output: list[dict] = []
    checked: set[int] = set()
    for page in pages:
        rows = (
            first_rows
            if page == 1
            else _items(
                await _authorized_page(request, _page_path(source, page), read_session, actor), True
            )[0]
        )
        offset = (page - 1) * 100 if spec.paged else 0
        for position, row in enumerate(rows, offset):
            if position in by_index:
                if row_fingerprint(row) != by_index[position]:
                    raise _stale()
                checked.add(position)
            if (all_rows and position not in by_index) or (not all_rows and position in by_index):
                output.append(row)
    if checked != set(by_index) or (all_rows and len(output) + len(by_index) != total):
        raise _stale()
    return output, total


def _may_resolve_labels(actor: Actor) -> bool:
    """Lookups read whole tables, so only company-wide readers may resolve names."""
    return EMPLOYEE_SCOPE.get(actor.designation) == "all" and "organization.read" in actor.grants


async def _labels(
    read_session: AsyncSession, spec: TableSpec, rows: list[dict], actor: Actor
) -> dict[tuple[str, str], str]:
    if not _may_resolve_labels(actor):
        return {}
    wanted: dict[str, set[UUID]] = {}
    for column in spec.columns:
        if column.lookup not in LOOKUP_TABLES:
            continue
        kind: str = "employee" if column.lookup == "employee_code" else column.lookup
        wanted.setdefault(kind, set()).update(
            ident for row in rows if (ident := reference(row.get(column.source))) is not None
        )
    labels: dict[tuple[str, str], str] = {}
    for kind, ids in wanted.items():
        table = LOOKUP_TABLES[kind]
        ordered = sorted(ids)
        for start in range(0, len(ordered), LOOKUP_CHUNK):
            chunk = ordered[start : start + LOOKUP_CHUNK]
            if kind == "employee":
                result = await read_session.execute(
                    select(
                        employees.c.id, employees.c.full_name, employees.c.company_employee_code
                    ).where(employees.c.id.in_(chunk))
                )
                for ident, full_name, code in result:
                    labels[("employee", str(ident))] = full_name
                    labels[("employee_code", str(ident))] = code
            else:
                result = await read_session.execute(
                    select(table.c.id, table.c.name).where(table.c.id.in_(chunk))
                )
                for ident, label in result:
                    labels[(kind, str(ident))] = label
    records = {
        ident
        for column in spec.columns
        if column.lookup == "record"
        for row in rows
        if (ident := reference(row.get(column.source))) is not None
    }
    labels.update(await record_labels(read_session, actor, records))
    return labels


def _projection(
    spec: TableSpec, rows: list[dict], labels: dict[tuple[str, str], str] | None = None
) -> dict:
    if spec.columns:
        return {
            "columns": [
                {"key": column.heading, "heading": column.heading} for column in spec.columns
            ],
            "items": [
                {
                    column.heading: readable_value(column, row, labels or {})
                    for column in spec.columns
                }
                for row in rows
            ],
        }
    columns = [{"key": key, "heading": key} for key in spec.fields]
    projected = []
    for row in rows:
        values = {}
        for key in spec.fields:
            value = row.get(key)
            values[key] = (
                json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                if isinstance(value, (dict, list))
                else value
            )
        projected.append(values)
    return {"columns": columns, "items": projected}


async def export(
    db: AsyncSession, actor: Actor, request: Request, item: TableExportInput
) -> tuple[bytes, str]:
    if actor.designation not in {OWNER, MD}:
        raise ApiError(403, "FORBIDDEN", "Access denied")
    context = {"mode": item.mode, "format": "csv"}
    row_count: int | None = None
    try:
        spec, source = resolve(item.sourcePath)
        context["table"] = spec.name
        async with session_factory()() as read_session:
            await read_session.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            )
            rows, total = await _collect(request, spec, source, item, read_session, actor)
            labels = await _labels(read_session, spec, rows, actor) if spec.columns else {}
            await read_session.rollback()
        row_count = len(rows)
        if len(rows) > CSV_ROWS:
            raise ExportLimitError(
                "EXPORT_ROWS_LIMIT",
                "CSV export exceeds 50,000 data rows",
                "rowCount",
                len(rows),
                CSV_ROWS,
            )
        data = render_csv(_projection(spec, rows, labels))
    except ApiError as error:
        metadata: dict[str, str | int] = {**context, "reason": error.code}
        if isinstance(error, ExportLimitError):
            metadata.update(
                {error.metric: error.count, error.metric.replace("Count", "Limit"): error.limit}
            )
            if row_count is not None:
                metadata["rowCount"] = row_count
        await record(
            db,
            actor=actor.employee_id,
            action="table.export_rejected",
            module="reports",
            context=metadata,
        )
        await db.commit()
        raise
    await record(
        db,
        actor=actor.employee_id,
        action="table.exported",
        module="reports",
        context={
            **context,
            "rowCount": len(rows),
            "authorizedTotal": total,
            "byteCount": len(data),
        },
    )
    await db.commit()
    return data, f"amafh-core-{spec.name}.csv"
