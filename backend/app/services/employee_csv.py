"""Read-only employee CSV review and atomic creation through the normal service."""

import csv
import io
import re
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import branches, departments, designations, employees
from app.errors import ApiError
from app.normalization import identifier
from app.policies import Actor, require
from app.repositories.employee_scope import employee_query
from app.schemas.organization import EmployeeCreate
from app.services import organization
from app.services.case_csv import MAX_CSV_BYTES, MAX_DATA_ROWS
from app.services.idempotency import claim, complete

# Every creation field is represented; internal UUIDs are resolved from readable references.
COLUMNS = {
    "companyEmployeeCode": "Company Employee Code",
    "fullName": "Full name",
    "mobile": "Mobile",
    "personalEmail": "Personal email",
    "nationality": "Nationality",
    "gender": "Gender",
    "maritalStatus": "Marital status",
    "dateOfJoining": "Joining date",
    "passportNumber": "Passport number",
    "emiratesIdNumber": "Emirates ID",
    "designationId": "User Type",
    "branchId": "Branch",
    "departmentId": "Department",
    "reportingManagerId": "Reporting Manager Company Employee Code",
}
UNIQUE_FIELDS = {
    "companyEmployeeCode": employees.c.company_employee_code,
    "passportNumber": employees.c.passport_number,
    "emiratesIdNumber": employees.c.emirates_id_number,
}


def columns() -> list[dict]:
    return [
        {"field": field, "label": COLUMNS[field], "required": definition.is_required()}
        for field, definition in EmployeeCreate.model_fields.items()
    ]


def template() -> str:
    output = io.StringIO(newline="")
    csv.writer(output).writerow([column["label"] for column in columns()])
    return output.getvalue()


def error(row: int, column: str, message: str) -> dict:
    return {"rowNumber": row, "column": column, "message": message}


def parse(content: bytes) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    errors: list[dict] = []
    if len(content) > MAX_CSV_BYTES:
        return [], [error(1, "file", "Maximum file size is 5 MB (5,000,000 bytes).")]
    number = 1
    try:
        reader = csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        header = next(reader, None)
        if header is None:
            return [], [error(1, "file", "Empty CSV. Download and fill the template.")]
        if len(header) > len(COLUMNS):
            return [], [error(1, "header", "Too many columns. Use the downloaded template.")]
        for name in header:
            if header.count(name) > 1:
                errors.append(error(1, name, "Duplicate header. Keep each column once."))
            elif name not in COLUMNS.values():
                errors.append(error(1, name, "Unsupported header. Use the downloaded template."))
        for column in columns():
            if column["required"] and column["label"] not in header:
                errors.append(error(1, column["label"], "Required header is missing."))
        if errors:
            return [], errors
        for number, raw in enumerate(reader, 2):
            if number - 1 > MAX_DATA_ROWS:
                errors.append(error(number, "file", "Maximum 5,000 employee rows per CSV."))
                break
            values = dict(zip(header, raw, strict=False))
            row_errors = []
            if len(raw) != len(header):
                row_errors.append(error(number, "row", "Row must have one value per header."))
            if not any(value.strip() for value in raw):
                row_errors.append(error(number, "row", "Empty employee row. Remove or fill it."))
            rows.append({"rowNumber": number, "values": values, "errors": row_errors})
    except UnicodeDecodeError, csv.Error:
        errors.append(error(number, "file", "Invalid UTF-8 CSV or malformed quoting."))
    if not rows and not errors:
        errors.append(error(2, "file", "At least one employee row is required."))
    return rows, errors


async def reference_data(session: AsyncSession, actor: Actor) -> dict:
    require(actor, "employee.write")
    return {
        "columns": columns(),
        "branches": [dict(row) for row in (await session.execute(select(branches))).mappings()],
        "departments": [
            dict(row) for row in (await session.execute(select(departments))).mappings()
        ],
        "userTypes": [
            dict(row)
            for row in (await session.execute(select(designations))).mappings()
            if row["name"] != "Owner"
            and (actor.designation == "Owner" or row["name"] != "Managing Director")
        ],
        "managers": [
            {"code": row["company_employee_code"], "name": row["full_name"]}
            for row in (
                await session.execute(employee_query(actor).where(employees.c.status == "Active"))
            ).mappings()
            if row["designation"] in {"Owner", "Managing Director", "Sales Manager", "Team Leader"}
        ],
    }


def match(records: list[dict], value: str, key: str = "name") -> UUID | None:
    found = [
        record["id"] for record in records if identifier(str(record[key])) == identifier(value)
    ]
    return found[0] if len(found) == 1 else None


async def validate(session: AsyncSession, actor: Actor, content: bytes) -> tuple[dict, list]:
    require(actor, "employee.write")
    rows, errors = parse(content)
    branch_rows = [dict(row) for row in (await session.execute(select(branches))).mappings()]
    department_rows = [dict(row) for row in (await session.execute(select(departments))).mappings()]
    role_rows = [dict(row) for row in (await session.execute(select(designations))).mappings()]
    manager_rows = [dict(row) for row in (await session.execute(employee_query(actor))).mappings()]
    items: list[tuple[dict, EmployeeCreate]] = []
    seen: dict[tuple[str, str], dict] = {}
    for row in rows:
        for field in UNIQUE_FIELDS:
            text = row["values"].get(COLUMNS[field], "").strip()
            if not text:
                continue
            key = (field, identifier(text))
            previous = seen.get(key)
            if previous is not None:
                for affected in (previous, row):
                    affected["errors"].append(
                        error(affected["rowNumber"], COLUMNS[field], "Repeated within this CSV.")
                    )
            else:
                seen[key] = row
        if any(e["column"] == "row" for e in row["errors"]):
            continue
        raw = row["values"]
        number = row["rowNumber"]
        payload = {
            field: raw.get(label, "").strip()
            for field, label in COLUMNS.items()
            if not field.endswith("Id") and raw.get(label, "").strip()
        }
        date_text = raw.get("Joining date", "").strip()
        if date_text and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_text):
            row["errors"].append(error(number, "Joining date", "Use YYYY-MM-DD."))
        for field, records, reference_key in (
            ("designationId", role_rows, "name"),
            ("branchId", branch_rows, "name"),
            ("departmentId", department_rows, "name"),
            ("reportingManagerId", manager_rows, "company_employee_code"),
        ):
            label = COLUMNS[field]
            text = raw.get(label, "").strip()
            if not text:
                continue
            candidates = records
            if field == "departmentId":
                candidates = [r for r in records if r["branch_id"] == payload.get("branchId")]
            resolved = match(candidates, text, reference_key)
            if resolved is None:
                row["errors"].append(
                    error(
                        number, label, "Reference is missing or ambiguous. Use an available value."
                    )
                )
            else:
                payload[field] = resolved
        try:
            item = EmployeeCreate.model_validate(payload)
        except ValidationError as failure:
            for detail in failure.errors():
                field = str(detail["loc"][0])
                if not any(e["column"] == COLUMNS.get(field) for e in row["errors"]):
                    row["errors"].append(error(number, COLUMNS.get(field, field), detail["msg"]))
            continue
        if item.emiratesIdNumber is not None and len(item.emiratesIdNumber) > 100:
            row["errors"].append(
                error(number, "Emirates ID", "Maximum stored length is 100 characters.")
            )
        # Show the same normalized text that normal creation persists, with readable references.
        row["values"].update(
            {
                COLUMNS[field]: str(value)
                for field, value in item.model_dump().items()
                if not field.endswith("Id") and value is not None
            }
        )
        row["values"]["Personal email"] = str(item.personalEmail).lower()
        try:
            await organization.validate_employee_creation(session, actor, item, uuid4())
        except ApiError as failure:
            field = {
                "INVALID_ASSIGNMENT": "Department",
                "INVALID_MANAGER": COLUMNS["reportingManagerId"],
                "INVALID_DESIGNATION": "User Type",
                "FORBIDDEN": "User Type",
                "INVALID_EMPLOYEE": "Gender / Marital status",
            }.get(failure.code, "row")
            row["errors"].append(error(number, field, failure.message))
        items.append((row, item))
    # Compare exactly the canonical forms enforced by the existing unique indexes.
    for field, column in UNIQUE_FIELDS.items():
        values = [key[1] for key in seen if key[0] == field]
        if not values:
            continue
        canonical = func.upper(func.regexp_replace(func.btrim(column), "[[:space:]]+", " ", "g"))
        existing = set(
            (await session.scalars(select(canonical).where(canonical.in_(values)))).all()
        )
        for row, item in items:
            value = getattr(item, field)
            if value is not None and identifier(value) in existing:
                row["errors"].append(
                    error(
                        row["rowNumber"],
                        COLUMNS[field],
                        "Already used by an employee. Correct this value.",
                    )
                )
    invalid = sum(bool(row["errors"]) for row in rows)
    return {
        "totalRows": len(rows),
        "validRows": len(rows) - invalid,
        "invalidRows": invalid,
        "canImport": bool(rows) and not invalid and not errors,
        "rows": rows,
        "errors": errors,
    }, items


def refuse(result: dict) -> None:
    errors = [*result["errors"], *(e for row in result["rows"] for e in row["errors"])]
    fields: dict[str, list[str]] = {}
    for item in errors:
        fields.setdefault(f"rows.{item['rowNumber']}.{item['column']}", []).append(item["message"])
    raise ApiError(
        422,
        "EMPLOYEE_IMPORT_INVALID",
        "No employees imported. Correct the CSV and validate again.",
        fields,
    )


async def apply(session: AsyncSession, actor: Actor, content: bytes, digest: str, key: str) -> dict:
    require(actor, "employee.write")
    current_row = 1
    try:
        record_id, replay = await claim(session, actor, "employee.csv.import", key, {"csv": digest})
        if replay is not None:
            await session.commit()
            return replay
        result, items = await validate(session, actor, content)
        if not result["canImport"]:
            refuse(result)
        created = []
        for row, item in items:
            current_row = row["rowNumber"]
            try:
                created.append(
                    await organization.create_employee(session, actor, item, commit=False)
                )
            except ApiError as failure:
                raise ApiError(
                    failure.status,
                    failure.code,
                    "No employees imported. " + failure.message,
                    {f"rows.{current_row}.row": [failure.message]},
                ) from failure
        response = {"createdCount": len(created), "employees": created}
        await complete(session, record_id, 201, response)
        await session.commit()
        return response
    except IntegrityError as failure:
        await session.rollback()
        constraint = getattr(getattr(failure.orig, "diag", None), "constraint_name", "") or ""
        field = next(
            (COLUMNS[name] for name, column in UNIQUE_FIELDS.items() if column.name in constraint),
            "row",
        )
        raise ApiError(
            409,
            "EMPLOYEE_IMPORT_CONFLICT",
            "No employees imported. A unique value conflicts with current data; validate again.",
            {f"rows.{current_row}.{field}": ["Conflicts with current employee data."]},
        ) from failure
    except Exception:
        await session.rollback()
        raise
