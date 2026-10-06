"""Bounded, server-only CSV and PDF rendering of authorized report results."""

import csv
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import A4, landscape  # type: ignore[import-untyped]
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-untyped]
from reportlab.pdfgen import canvas  # type: ignore[import-untyped]
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record
from app.db.cases import banks
from app.db.organization import branches, departments, designations, employees, teams
from app.errors import ApiError
from app.policies import MD, OWNER, Actor
from app.repositories.employee_scope import employee_query
from app.schemas.reports import ReportFilters
from app.services.performance_math import DUBAI
from app.services.reports import read
from app.services.table_export_spec import ExportColumn, report_columns

CSV_ROWS = 50_000
PDF_ROWS = 5_000
MAX_BYTES = 25_000_000
PDF_PAGES = 200
PDF_FONT = "AMAFH-DejaVuSans"
PDF_FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "DejaVuSans.ttf"
UNAVAILABLE = "Unavailable"
LABEL_CHUNK = 5_000
ACRONYMS = {"csv", "pdf", "aed", "cc", "pf", "hr", "md"}
COMPANY_ORGANIZATION = {OWNER, MD, "HR", "Finance"}
FILTER_LABELS = {
    "branchId": "Branch",
    "departmentId": "Department",
    "teamId": "Team",
    "employeeId": "Employee",
    "designationId": "Designation",
    "bankId": "Bank",
    "productCode": "Product",
    "customerType": "Customer Type",
    "status": "Status",
    "accessStatus": "Access Status",
    "category": "Category",
}
FILTER_LOOKUPS = {
    "branchId": "branch",
    "departmentId": "department",
    "teamId": "team",
    "employeeId": "employee",
    "designationId": "designation",
    "bankId": "bank",
}
SUMMARY_LABELS = {
    "totalCases": "Total cases",
    "pendingApproval": "Pending approval",
    "bookedCases": "Booked cases",
    "completedCases": "Completed cases",
    "rejectedCases": "Rejected cases",
    "delayedCases": "Delayed cases",
    "delayedMetricState": "Delayed metric",
    "totalCustomers": "Total customers",
    "newCustomers": "New customers",
    "existingWithNewCases": "Existing with new cases",
    "individualCustomers": "Individual customers",
    "companyCustomers": "Company customers",
    "employees": "Employees",
    "createdCases": "Created cases",
    "achievedCCPoints": "CC points",
    "achievedPFAed": "PF AED",
    "rankedEmployees": "Ranked employees",
    "winnerEmployeeId": "Winner",
    "decisionState": "Decision",
    "coordinators": "Coordinators",
    "recordCount": "Records",
    "totalCommissionAed": "Total commission AED",
    "totalAmountAed": "Total amount AED",
    "totalCCPoints": "Total CC points",
    "totalPFAed": "Total PF AED",
    "salaryPaidAed": "Salary paid AED",
    "commissionPaidAed": "Commission paid AED",
    "totalPaidAed": "Total paid AED",
    "presentCount": "Present",
    "absentCount": "Absent",
    "lateCount": "Late",
    "availableCount": "Available",
    "issuedCount": "Issued",
    "maintenanceCount": "Maintenance",
    "damagedCount": "Damaged",
    "totalEmployees": "Total employees",
    "activeEmployees": "Active employees",
    "offboardedEmployees": "Offboarded employees",
    "assignmentCount": "Assignments",
}


class ExportLimitError(ApiError):
    def __init__(self, code: str, message: str, metric: str, count: int, limit: int) -> None:
        super().__init__(422, code, message)
        self.metric = metric
        self.count = count
        self.limit = limit


def readable_code(value: Any) -> str:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", "" if value is None else str(value))
    words = [
        word.upper() if word.lower() in ACRONYMS else word.lower()
        for word in re.sub(r"[._-]+", " ", spaced).split()
    ]
    text = " ".join(words)
    return text[:1].upper() + text[1:]


def dubai_timestamp(value: Any) -> str | None:
    if value is None or value == "":
        return None
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return moment.astimezone(DUBAI).isoformat()


def reference(value: Any) -> UUID | None:
    if value is None or value == "":
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


async def _label_rows(
    session: AsyncSession, actor: Actor, kind: str, ids: list[UUID], row_banks: set[UUID]
) -> list[tuple[UUID, str, str | None]]:
    """Each kind mirrors the list API the actor could already use to read that name."""
    if kind == "employee":
        rows = await session.execute(employee_query(actor).where(employees.c.id.in_(ids)))
        return [
            (row["id"], row["full_name"], row["company_employee_code"]) for row in rows.mappings()
        ]
    if kind == "branch":
        query = select(branches.c.id, branches.c.name).where(branches.c.id.in_(ids))
        if actor.designation not in COMPANY_ORGANIZATION:
            query = query.where(branches.c.id == actor.branch_id)
    elif kind == "department":
        query = select(departments.c.id, departments.c.name).where(departments.c.id.in_(ids))
        if actor.designation not in COMPANY_ORGANIZATION:
            query = query.where(departments.c.branch_id == actor.branch_id)
    elif kind == "bank":
        if not {"pipeline.write", "case.create", "case.read"} & actor.grants:
            return []
        query = select(banks.c.id, banks.c.name).where(banks.c.id.in_(ids))
        if actor.designation not in {OWNER, MD}:
            query = query.where(or_(banks.c.active.is_(True), banks.c.id.in_(sorted(row_banks))))
    elif kind == "team":
        if actor.designation not in {OWNER, MD, "Finance", "Sales Manager"}:
            return []
        query = select(teams.c.id, teams.c.name).where(teams.c.id.in_(ids))
        if actor.designation == "Sales Manager":
            query = query.where(
                teams.c.branch_id == actor.branch_id,
                teams.c.department_id == actor.department_id,
            )
    elif kind == "designation":
        query = select(designations.c.id, designations.c.name).where(designations.c.id.in_(ids))
    else:
        return []
    return [(ident, name, None) for ident, name in await session.execute(query)]


async def relation_labels(
    session: AsyncSession,
    actor: Actor,
    wanted: dict[str, set[UUID]],
    row_banks: set[UUID] | None = None,
) -> dict[tuple[str, str], str]:
    labels: dict[tuple[str, str], str] = {}
    for kind, ids in wanted.items():
        ordered = sorted(ids)
        for start in range(0, len(ordered), LABEL_CHUNK):
            chunk = ordered[start : start + LABEL_CHUNK]
            for ident, name, code in await _label_rows(
                session, actor, kind, chunk, row_banks or set()
            ):
                labels[(kind, str(ident))] = name
                if kind == "employee":
                    labels[("employee_code", str(ident))] = code or ""
    return labels


def _source_value(row: dict, source: str) -> Any:
    """Dotted sources read a nested value, such as one product's target progress."""
    if source in row or "." not in source:
        return row.get(source)
    value: Any = row
    for part in source.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def readable_value(column: ExportColumn, row: dict, labels: dict[tuple[str, str], str]) -> Any:
    value = _source_value(row, column.source)
    if column.lookup == "present":
        return value is not None
    if column.lookup is None:
        return value
    if column.lookup == "label":
        return readable_code(value) if value else None
    if column.lookup == "dubai_time":
        return dubai_timestamp(value)
    ident = reference(value)
    if column.lookup == "record":
        if value in (None, ""):
            return None
        return labels.get(("record", str(ident)), "Related record")
    if ident is None:
        return None if value in (None, "") else UNAVAILABLE
    fallback = None if column.lookup == "employee_code" else UNAVAILABLE
    return labels.get((column.lookup, str(ident)), fallback)


def person_label(labels: dict[tuple[str, str], str], ident: UUID | None) -> str | None:
    if ident is None:
        return None
    name = labels.get(("employee", str(ident)))
    if not name:
        return None
    code = labels.get(("employee_code", str(ident)))
    return f"{name} ({code})" if code else name


def _filter_heading(kind: str, key: str) -> str:
    if key == "employeeId" and kind == "assets":
        return "Issued Employee"
    if key == "status" and kind in {"hr-employees", "hr-assignments"}:
        return "Employee Status"
    return FILTER_LABELS.get(key) or readable_code(key)


def _summary_value(value: Any) -> Any:
    if value is None:
        return UNAVAILABLE
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z]+(_[A-Za-z]+)+", value):
        return readable_code(value)
    return value


async def readable_report(session: AsyncSession, actor: Actor, result: dict) -> dict:
    """Project an authorized report result into readable export columns, filters and summary."""
    kind = result["report"]
    columns = report_columns(kind, result["filters"].get("productCode"))
    wanted: dict[str, set[UUID]] = {}
    row_banks: set[UUID] = set()
    for column in columns:
        if column.lookup not in {"employee", "employee_code", "branch", "department", "bank"}:
            continue
        lookup = "employee" if column.lookup == "employee_code" else column.lookup
        ids = {ident for row in result["items"] if (ident := reference(row.get(column.source)))}
        wanted.setdefault(lookup, set()).update(ids)
        if lookup == "bank":
            row_banks |= ids
    for key, value in result["filters"].items():
        if key in FILTER_LOOKUPS and (ident := reference(value)):
            wanted.setdefault(FILTER_LOOKUPS[key], set()).add(ident)
    winner = reference(result["summary"].get("winnerEmployeeId"))
    if winner:
        wanted.setdefault("employee", set()).add(winner)
    labels = await relation_labels(session, actor, wanted, row_banks)

    order = list(FILTER_LABELS)
    filters: dict[str, Any] = {}
    for key in sorted(
        result["filters"], key=lambda name: order.index(name) if name in order else len(order)
    ):
        value = result["filters"][key]
        if key == "employeeId":
            shown: Any = person_label(labels, reference(value)) or UNAVAILABLE
        elif key in FILTER_LOOKUPS:
            shown = labels.get((FILTER_LOOKUPS[key], str(reference(value))), UNAVAILABLE)
        else:
            shown = value
        filters[_filter_heading(kind, key)] = shown

    summary: dict[str, Any] = {}
    for key, value in result["summary"].items():
        label = SUMMARY_LABELS.get(key) or readable_code(key)
        if key == "winnerEmployeeId":
            ranked_name = next(
                (
                    row.get("employeeName")
                    for row in result["items"]
                    if winner and row.get("employeeId") == str(winner)
                ),
                None,
            )
            summary[label] = (
                "None"
                if winner is None
                else person_label(labels, winner) or ranked_name or UNAVAILABLE
            )
        else:
            summary[label] = _summary_value(value)

    return {
        **result,
        "columns": [{"key": column.heading, "heading": column.heading} for column in columns],
        "items": [
            {column.heading: readable_value(column, row, labels) for column in columns}
            for row in result["items"]
        ],
        "filters": filters,
        "summary": summary,
    }


def _font() -> None:
    if PDF_FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(PDF_FONT, str(PDF_FONT_PATH)))


def _visual_text(value: str) -> str:
    font = pdfmetrics.getFont(PDF_FONT)
    visual = get_display(arabic_reshaper.reshape(value), base_dir="L")
    if any(ord(char) not in font.face.charToGlyph for char in visual):
        raise ApiError(
            422, "EXPORT_GLYPH_UNAVAILABLE", "PDF text contains an unsupported character"
        )
    return visual


def _safe_csv(value) -> str:
    cell = "" if value is None else str(value)
    leading = cell.lstrip(" \t\r\n\ufeff")
    dangerous = cell[:1] in "\t\r\n" or leading[:1] in "=+-@"
    return "'" + cell if cell and dangerous else cell


def render_csv(result: dict) -> bytes:
    output = io.BytesIO()
    stream = io.TextIOWrapper(output, encoding="utf-8-sig", newline="", write_through=True)
    writer = csv.writer(stream, lineterminator="\r\n")
    columns = result["columns"]
    writer.writerow([column["heading"] for column in columns])
    for row in result["items"]:
        writer.writerow([_safe_csv(row[column["key"]]) for column in columns])
        if output.tell() > MAX_BYTES:
            raise ExportLimitError(
                "EXPORT_BYTES_LIMIT",
                "CSV export exceeds 25,000,000 bytes",
                "byteCount",
                output.tell(),
                MAX_BYTES,
            )
    stream.flush()
    data = output.getvalue()
    if len(data) > MAX_BYTES:
        raise ExportLimitError(
            "EXPORT_BYTES_LIMIT",
            "CSV export exceeds 25,000,000 bytes",
            "byteCount",
            len(data),
            MAX_BYTES,
        )
    return data


def _pdf_text(value) -> str:
    raw = "" if value is None else str(value)
    return "".join(" " if ord(char) < 32 else char for char in raw).strip()


def _wrap(value: str, width: float, font_size: int = 8) -> list[str]:
    if not value:
        return [""]
    lines = []
    remaining = value
    while remaining:
        used = 0.0
        end = 0
        for char in remaining:
            char_width = pdfmetrics.stringWidth(char, PDF_FONT, font_size)
            if used + char_width > width:
                break
            used += char_width
            end += 1
        if end == len(remaining):
            lines.append(remaining)
            break
        split = remaining.rfind(" ", 1, end + 1)
        if split <= 0:
            split = max(end, 1)
        lines.append(remaining[:split])
        remaining = remaining[split:].lstrip()
    return lines


def render_pdf(result: dict, actor_name: str, employee_code: str) -> bytes:
    _font()
    width, height = landscape(A4)
    line_width = width - 80
    generation = datetime.now(DUBAI).strftime("%Y-%m-%d %H:%M:%S %Z")
    context = [
        "AMAFH CORE | AMAFH Commercial Brokers L.L.C.",
        result["title"],
        f"Period: {result['startDate']} to {result['endDate']}",
        "Filters: "
        + ("; ".join(f"{label}: {value}" for label, value in result["filters"].items()) or "None"),
        f"Generated: {generation}",
        f"By: {_pdf_text(actor_name)} ({_pdf_text(employee_code)})",
        "Summary: "
        + ("; ".join(f"{label}: {value}" for label, value in result["summary"].items()) or "None"),
    ]
    per_page = int((height - 100) // 11)
    lines = []
    for entry in context:
        lines.extend(_wrap(_pdf_text(entry), line_width))
    lines.append("")
    for item in result["items"]:
        lines.append("")
        for column in result["columns"]:
            entry = f"{column['heading']}: {_pdf_text(item[column['key']])}"
            lines.extend(_wrap(entry, line_width))
    pages = [lines[index : index + per_page] for index in range(0, len(lines), per_page)] or [[]]
    if len(pages) > PDF_PAGES:
        raise ExportLimitError(
            "EXPORT_PAGES_LIMIT",
            "PDF export exceeds 200 pages",
            "pageCount",
            len(pages),
            PDF_PAGES,
        )
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(width, height), pageCompression=1)
    pdf.setTitle(result["title"])
    for page_number, page_lines in enumerate(pages, 1):
        pdf.setFont(PDF_FONT, 8)
        y = height - 42
        for line in page_lines:
            pdf.drawString(40, y, _visual_text(line))
            y -= 11
        pdf.setFont(PDF_FONT, 8)
        pdf.drawString(40, 28, _visual_text("Confidential — Internal Use Only"))
        pdf.drawRightString(width - 40, 28, f"Page {page_number} of {len(pages)}")
        pdf.showPage()
    pdf.save()
    data = output.getvalue()
    if len(data) > MAX_BYTES:
        raise ExportLimitError(
            "EXPORT_BYTES_LIMIT",
            "PDF export exceeds 25,000,000 bytes",
            "byteCount",
            len(data),
            MAX_BYTES,
        )
    return data


async def export(
    session: AsyncSession, actor: Actor, kind: str, filters: ReportFilters, format: str
) -> tuple[bytes, str, str]:
    if format not in {"csv", "pdf"}:
        raise ApiError(404, "NOT_FOUND", "Export format unavailable")
    limit = CSV_ROWS if format == "csv" else PDF_ROWS
    try:
        result = await read(
            session,
            actor,
            kind,
            filters,
            page=1,
            page_size=limit + 1,
            export_limit=limit,
        )
    except ApiError as error:
        await record(
            session,
            actor=actor.employee_id,
            action="report.export_rejected",
            module="reports",
            context={"report": kind, "format": format, "reason": error.code},
        )
        await session.commit()
        raise
    context = {
        "report": kind,
        "format": format,
        "startDate": result["startDate"].isoformat(),
        "endDate": result["endDate"].isoformat(),
        "filters": result["filters"],
    }
    if result["total"] > limit:
        await record(
            session,
            actor=actor.employee_id,
            action="report.export_rejected",
            module="reports",
            context={
                **context,
                "reason": "row_limit",
                "rowCount": result["total"],
                "rowLimit": limit,
            },
        )
        await session.commit()
        raise ExportLimitError(
            "EXPORT_ROWS_LIMIT",
            f"{format.upper()} export exceeds {limit:,} data rows",
            "rowCount",
            result["total"],
            limit,
        )
    try:
        readable = await readable_report(session, actor, result)
        if format == "csv":
            data = render_csv(readable)
            media = "text/csv; charset=utf-8"
        else:
            code = await session.scalar(
                select(employees.c.system_employee_code).where(employees.c.id == actor.employee_id)
            )
            data = render_pdf(readable, actor.display_name, code or "")
            media = "application/pdf"
    except ApiError as error:
        await record(
            session,
            actor=actor.employee_id,
            action="report.export_rejected",
            module="reports",
            context={
                **context,
                "reason": error.code,
                "rowCount": result["total"],
                "rowLimit": limit,
                **(
                    {error.metric: error.count, error.metric.replace("Count", "Limit"): error.limit}
                    if isinstance(error, ExportLimitError)
                    else {}
                ),
            },
        )
        await session.commit()
        raise
    await record(
        session,
        actor=actor.employee_id,
        action="report.exported",
        module="reports",
        context={**context, "rowCount": result["total"], "byteSize": len(data)},
    )
    await session.commit()
    filename = (
        f"amafh-core-{kind}-{result['startDate'].isoformat()}-"
        f"{result['endDate'].isoformat()}.{format}"
    )
    return data, media, filename
