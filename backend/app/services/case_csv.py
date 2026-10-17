"""Strict all-or-nothing bank-stage CSV import with retained results."""

import csv
import hashlib
import io
import json
import re
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from fastapi import UploadFile
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import DateTime, bindparam, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.cases import (
    case_lifecycle_history,
    case_stage_history,
    cases,
    product_types,
)
from app.db.operations import csv_import_batches, csv_import_row_results, notifications
from app.db.organization import designations, employees
from app.db.query_sets import text_set, uuid_set
from app.errors import ApiError
from app.normalization import identifier
from app.policies import Actor, require
from app.services import case_import_reads, case_processing_scope, finance_completion
from app.services.case_corrections import FINAL
from app.services.idempotency import claim, complete
from app.services.notification_events import notify
from app.services.pipelines import _valid_stage_set
from app.whole_numbers import WholeAmount

HEADERS = ("Bank Case Number", "Latest Stage", "Bank Remarks")
FINAL_PF_HEADER = "Final PF amount"
TEMPLATE = "Bank Case Number,Latest Stage,Bank Remarks,Final PF amount\r\n"
MAX_CSV_BYTES = 5_000_000
MAX_DATA_ROWS = 5_000
READ_CHUNK_BYTES = 64 * 1024
INSERT_BATCH_ROWS = 512
FINANCIAL_RULE_ERRORS = frozenset(
    {"FINANCIAL_RULE_MISSING", "CC_SALARY_MISSING", "CC_SALARY_RULE_MISSING", "PF_RATE_REQUIRED"}
)
COMPLETION_ERRORS = FINANCIAL_RULE_ERRORS | {
    "PF_FINAL_AMOUNT_REQUIRED",
    "PF_COMMISSION_LIMIT",
    "PF_RESULT_LOCKED",
}
PF_AMOUNT_ADAPTER = TypeAdapter(WholeAmount)


async def read_upload(file: UploadFile) -> tuple[bytes, str, bool]:
    """Stop before hashing or retaining bytes beyond the accepted upload limit."""
    digest = hashlib.sha256()
    content = bytearray()
    too_large = False
    while chunk := await file.read(READ_CHUNK_BYTES):
        if len(content) + len(chunk) > MAX_CSV_BYTES:
            raise ApiError(
                422,
                "CSV_SIZE_LIMIT",
                "CSV exceeds the 5 MB limit",
                {"file": ["Maximum file size is 5 MB"]},
            )
        digest.update(chunk)
        if len(content) < MAX_CSV_BYTES:
            content.extend(chunk[: MAX_CSV_BYTES - len(content)])
    return bytes(content), digest.hexdigest(), too_large


def safe_file_name(name: str | None) -> str:
    raw = (name or "bank-stage.csv").replace("\\", "/").split("/")[-1].strip()
    cleaned = "".join(
        character if character.isprintable() and character not in '<>:"|?*' else "_"
        for character in raw
    )
    return (cleaned or "bank-stage.csv")[:255]


def _parse(content: bytes) -> tuple[list[tuple[int, str, str, str, Decimal | None]], list[dict]]:
    next_row = 1
    try:
        source = io.StringIO(content.decode("utf-8-sig", errors="strict"), newline="")
        reader = csv.reader(source, strict=True)
        header = next(reader, None)
        if header is None or not (
            (len(header) == 3 and set(header) == set(HEADERS))
            or (len(header) == 4 and set(header) == {*HEADERS, FINAL_PF_HEADER})
        ):
            return [], [
                {
                    "rowNumber": 1,
                    "code": "INVALID_HEADER",
                    "message": "Use Bank Case Number, Latest Stage, Bank Remarks; "
                    "Final PF amount is the optional fourth column",
                }
            ]
        positions = [header.index(name) for name in HEADERS]
        pf_position = header.index(FINAL_PF_HEADER) if FINAL_PF_HEADER in header else None
        rows = []
        errors = []
        seen = set()
        for line_number, raw in enumerate(reader, start=2):
            next_row = line_number + 1
            if line_number - 1 > MAX_DATA_ROWS:
                errors.append(
                    {
                        "rowNumber": line_number,
                        "code": "CSV_ROW_LIMIT",
                        "message": "CSV exceeds 5,000 data rows",
                    }
                )
                break
            # A missing final optional trailing cell is equivalent to an empty
            # cell, never to a missing/reordered required column.
            if len(raw) == 3 and len(header) == 4 and header[-1] == FINAL_PF_HEADER:
                raw.append("")
            if len(raw) != len(header):
                errors.append(
                    {
                        "rowNumber": line_number,
                        "code": "MALFORMED_ROW",
                        "message": "Row values must match the template columns",
                    }
                )
                continue
            number, stage, remark = (raw[position].strip() for position in positions)
            final_amount = None
            pf_text = raw[pf_position].strip() if pf_position is not None else ""
            if pf_text:
                try:
                    if len(pf_text) > 40 or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", pf_text):
                        raise ValueError
                    final_amount = PF_AMOUNT_ADAPTER.validate_python(pf_text)
                    if final_amount <= 0:
                        raise ValueError
                except ValueError, ValidationError, InvalidOperation:
                    errors.append(
                        {
                            "rowNumber": line_number,
                            "code": "INVALID_FINAL_PF_AMOUNT",
                            "message": "Final PF amount must be positive AED, "
                            "maximum 18 whole digits",
                        }
                    )
                    continue
            number = identifier(number)
            if not number or not stage or not remark:
                errors.append(
                    {
                        "rowNumber": line_number,
                        "code": "REQUIRED_VALUE",
                        "message": "Required value missing",
                    }
                )
                continue
            if number in seen:
                errors.append(
                    {
                        "rowNumber": line_number,
                        "code": "DUPLICATE_ROW",
                        "message": "Bank Case Number repeated",
                    }
                )
                continue
            seen.add(number)
            rows.append((line_number, number, stage, remark, final_amount))
        if not rows and not errors:
            errors.append(
                {
                    "rowNumber": 2,
                    "code": "EMPTY_FILE",
                    "message": "At least one row is required",
                }
            )
        return rows, errors
    except UnicodeDecodeError, csv.Error:
        return [], [
            {
                "rowNumber": next_row,
                "code": "MALFORMED_CSV",
                "message": "Invalid UTF-8 CSV",
            }
        ]


def _context(row_number, number, stage_name, remark, case=None, products=None, final_amount=None):
    product = None
    if case is not None and products:
        product = products.get(case["product_type_id"])
    return {
        "rowNumber": row_number,
        "caseId": case["id"] if case is not None else None,
        "internalCaseId": case["internal_case_id"] if case is not None else None,
        "bankCaseNumber": (case["bank_case_number"] if case is not None else None) or number,
        "productLabel": product,
        "currentStage": case["current_stage"] if case is not None else None,
        "requestedStage": stage_name,
        "remark": remark,
        "finalPfAmount": final_amount,
    }


async def _product_names(session: AsyncSession) -> dict:
    return {
        row.id: row.name
        for row in (await session.execute(select(product_types.c.id, product_types.c.name)))
    }


async def _validate_rows(session: AsyncSession, actor: Actor, rows):
    await case_processing_scope.lock_assignment(session, actor)
    errors = []
    resolved = []
    contexts = {}
    products = await _product_names(session)
    product_codes = {
        row.id: row.code
        for row in await session.execute(select(product_types.c.id, product_types.c.code))
    }
    numbers = sorted({row[1] for row in rows})
    normalized_number = func.upper(
        func.regexp_replace(func.btrim(cases.c.bank_case_number), "[[:space:]]+", " ", "g")
    )
    by_number = dict.fromkeys(numbers)
    if numbers:
        locked = (
            await session.execute(
                select(cases, normalized_number.label("_csv_number"))
                .where(text_set(normalized_number, numbers))
                .order_by(normalized_number, cases.c.id)
                .with_for_update(of=cases)
            )
        ).mappings()
        for row in locked:
            by_number[row["_csv_number"]] = {
                key: value for key, value in row.items() if key != "_csv_number"
            }
    pipeline_sets = {}
    for row_number, number, stage_name, remark, final_amount in rows:
        case = by_number[number]
        contexts[row_number] = _context(row_number, number, stage_name, remark)
        if case is None:
            errors.append(
                {
                    "rowNumber": row_number,
                    "code": "CASE_UNAVAILABLE",
                    "message": "Case unavailable",
                }
            )
            continue
        if case["administratively_voided_at"] is not None:
            errors.append(
                {
                    "rowNumber": row_number,
                    "code": "CASE_UNAVAILABLE",
                    "message": "Case unavailable",
                }
            )
            continue
        if actor.designation == "Coordinator" and not (
            case_processing_scope.current_scope(actor, case)
            and (
                case["coordinator_employee_id"] == actor.employee_id
                or case["owner_transfer_previous_status"] is None
            )
        ):
            errors.append(
                {
                    "rowNumber": row_number,
                    "code": "CASE_UNAVAILABLE",
                    "message": "Case unavailable",
                }
            )
            continue
        contexts[row_number] = _context(
            row_number, number, stage_name, remark, case, products, final_amount
        )
        if case["owner_transfer_previous_status"] is not None:
            errors.append(
                {
                    "rowNumber": row_number,
                    "code": "CASE_PENDING_APPROVAL",
                    "message": "Case awaits Coordinator approval",
                }
            )
            continue
        if case["current_status"] in FINAL:
            errors.append(
                {
                    "rowNumber": row_number,
                    "code": "FINAL_LOCK",
                    "message": "Case is final",
                }
            )
            continue
        if case["bank_case_number"] is None or case["pipeline_configuration_id"] is None:
            errors.append(
                {
                    "rowNumber": row_number,
                    "code": "NOT_BOOKED",
                    "message": "Case is not booked",
                }
            )
            continue
        pipeline_id = case["pipeline_configuration_id"]
        if pipeline_id not in pipeline_sets:
            pipeline_sets[pipeline_id] = await _valid_stage_set(session, pipeline_id)
        stages = pipeline_sets[pipeline_id]
        stage = next((item for item in stages if item["name"] == stage_name), None)
        if stage is None:
            errors.append(
                {
                    "rowNumber": row_number,
                    "code": "INVALID_STAGE",
                    "message": "Stage is not in the retained Pipeline",
                }
            )
            continue
        is_pf_completion = (
            product_codes.get(case["product_type_id"]) == "PF"
            and stage["final_status"] == "Completed"
        )
        if is_pf_completion and final_amount is None:
            errors.append(
                {
                    "rowNumber": row_number,
                    "code": "PF_FINAL_AMOUNT_REQUIRED",
                    "message": "Final PF amount is required for PF completion",
                }
            )
            continue
        if final_amount is not None and not is_pf_completion:
            errors.append(
                {
                    "rowNumber": row_number,
                    "code": "PF_AMOUNT_CONTEXT_INVALID",
                    "message": "Final PF amount is allowed only for a completed PF Case",
                }
            )
            continue
        resolved_case = {**case, "_csv_final_pf_amount": final_amount}
        resolved.append((row_number, resolved_case, stage, remark))
    return resolved, errors, contexts


async def _record_results(session, batch_id, rows, errors, valid, contexts, *, one_shot: bool):
    failures = {item["rowNumber"]: item for item in errors}
    numbers = sorted({row[0] for row in rows} | set(failures) | set(contexts))
    values = []
    for number in numbers:
        failure = failures.get(number)
        context = contexts.get(number, {})
        if one_shot:
            status = "Applied" if valid else ("Rejected" if failure else "Skipped")
        else:
            status = "Invalid" if failure else "Valid"
        values.append(
            dict(
                id=uuid4(),
                batch_id=batch_id,
                row_number=number,
                status=status,
                error_code=failure["code"] if failure else None,
                error_detail=failure["message"] if failure else None,
                case_id=context.get("caseId"),
                internal_case_id=context.get("internalCaseId"),
                bank_case_number=context.get("bankCaseNumber"),
                product_label=context.get("productLabel"),
                current_stage=context.get("currentStage"),
                requested_stage=context.get("requestedStage"),
                remark=context.get("remark"),
                final_pf_amount=context.get("finalPfAmount"),
            )
        )
    if values:
        await _insert_rows(session, csv_import_row_results, values)


async def _insert_rows(session: AsyncSession, table, values: list[dict]) -> None:
    # Explicit bounded VALUES statements avoid one protocol execution per row.
    # UUIDs, field values and server defaults retain their original semantics;
    # every chunk remains inside the caller's all-or-nothing transaction.
    for offset in range(0, len(values), INSERT_BATCH_ROWS):
        await session.execute(table.insert().values(values[offset : offset + INSERT_BATCH_ROWS]))


async def _notify_final(session: AsyncSession, case: dict, status: str) -> None:
    managers = (
        (
            await session.execute(
                select(employees.c.id)
                .select_from(
                    employees.join(designations, employees.c.designation_id == designations.c.id)
                )
                .where(
                    employees.c.branch_id == case["branch_id"],
                    employees.c.department_id == case["department_id"],
                    employees.c.status == "Active",
                    designations.c.name == "Sales Manager",
                )
            )
        )
        .scalars()
        .all()
    )
    recipients = {
        case["owner_employee_id"],
        case["created_by_employee_id"],
        case["coordinator_employee_id"],
        *managers,
    }
    for recipient in recipients - {None}:
        await session.execute(
            notifications.insert().values(
                id=uuid4(),
                recipient_employee_id=recipient,
                kind="case.final_status",
                case_id=case["id"],
                message=f"Case {case['internal_case_id']} reached {status}",
            )
        )


async def _has_blocking_upload(session: AsyncSession, digest: str, actor: Actor) -> bool:
    prior = (
        await session.execute(
            select(
                csv_import_batches.c.id,
                csv_import_batches.c.status,
                csv_import_batches.c.uploaded_by_employee_id,
            ).where(
                csv_import_batches.c.kind == "bank_stage",
                csv_import_batches.c.content_hash == digest,
            )
        )
    ).all()
    for batch_id, status, uploader in prior:
        if status == "Validated":
            continue
        if status != "Rejected":
            return True
        # A denied attempt is evidence for its uploader, not a global reservation.
        # Other uploaders must still pass current validation before applying bytes.
        if uploader != actor.employee_id:
            continue
        codes = (
            (
                await session.execute(
                    select(csv_import_row_results.c.error_code).where(
                        csv_import_row_results.c.batch_id == batch_id
                    )
                )
            )
            .scalars()
            .all()
        )
        if not any(code in FINANCIAL_RULE_ERRORS for code in codes) or any(
            code is not None and code not in FINANCIAL_RULE_ERRORS for code in codes
        ):
            return True
    return False


async def _evaluate(session, actor, content, digest, too_large):
    if too_large or len(content) > MAX_CSV_BYTES:
        return (
            [],
            [
                {
                    "rowNumber": 1,
                    "code": "CSV_SIZE_LIMIT",
                    "message": "CSV exceeds 5 MB (5,000,000 bytes)",
                }
            ],
            [],
            {},
        )
    rows, errors = _parse(content)
    resolved = []
    contexts = {}
    if not any(error["code"] in {"CSV_SIZE_LIMIT", "CSV_ROW_LIMIT"} for error in errors):
        resolved, row_errors, contexts = await _validate_rows(session, actor, rows)
        errors += row_errors
    now = utcnow()
    if not errors:
        for row_number, case, stage, _ in resolved:
            if stage["final_status"] == "Completed":
                try:
                    await finance_completion.prepare(session, case, now)
                except ApiError as exc:
                    if exc.code not in COMPLETION_ERRORS:
                        raise
                    errors.append(
                        {
                            "rowNumber": row_number,
                            "code": exc.code,
                            "message": exc.message,
                        }
                    )
    for row_number, number, stage_name, remark, _final_amount in rows:
        contexts.setdefault(row_number, _context(row_number, number, stage_name, remark))
    return rows, errors, resolved, contexts


async def _apply_resolved(session, actor, batch_id, resolved, now):
    if resolved and all(
        not stage["is_final"] and stage["final_status"] is None for _, _, stage, _ in resolved
    ):
        await _apply_nonfinal_bulk(session, actor, batch_id, resolved, now)
        return
    prepared = {}
    for _row_number, case, stage, _ in resolved:
        if stage["final_status"] == "Completed":
            prepared[case["id"]] = await finance_completion.prepare(session, case, now)
    for _, case, stage, remark in resolved:
        next_status = stage["final_status"] or "Booked"
        extra_values = {}
        financial = prepared.get(case["id"])
        if (
            next_status == "Completed"
            and financial is not None
            and financial["product_code"] == "PF"
        ):
            extra_values["final_pf_amount"] = case["_csv_final_pf_amount"]
        await session.execute(
            update(cases)
            .where(cases.c.id == case["id"])
            .values(
                current_stage=stage["name"],
                current_status=next_status,
                finalized_at=now if stage["is_final"] else None,
                updated_at=now,
                **extra_values,
            )
        )
        await session.execute(
            case_stage_history.insert().values(
                id=uuid4(),
                case_id=case["id"],
                stage=stage["name"],
                remark=remark,
                status=next_status,
                updated_by_employee_id=actor.employee_id,
                csv_import_batch_id=batch_id,
                occurred_at=now,
            )
        )
        if next_status != case["current_status"]:
            await session.execute(
                case_lifecycle_history.insert().values(
                    id=uuid4(),
                    case_id=case["id"],
                    previous_status=case["current_status"],
                    status=next_status,
                    actor_employee_id=actor.employee_id,
                    occurred_at=now,
                    context={"csvImportBatchId": str(batch_id), "stage": stage["name"]},
                )
            )
        if next_status == "Completed":
            await finance_completion.apply(session, actor, case, prepared[case["id"]], now)
        if stage["is_final"]:
            await _notify_final(session, case, next_status)
        await notify(
            session,
            {case["owner_employee_id"], case["created_by_employee_id"]},
            "case.stage_updated",
            f"Case {case['internal_case_id']} stage updated",
            case_id=case["id"],
        )


def _result(batch_id, status, applied_count, errors, validation_status=None):
    payload = {
        "batchId": str(batch_id),
        "status": status,
        "appliedCount": applied_count,
        "errors": errors,
    }
    if validation_status is not None:
        payload["validationStatus"] = validation_status
    return payload


async def _lock_hash(session, digest: str) -> None:
    lock_key = int.from_bytes(
        hashlib.blake2b(f"bank_stage:{digest}".encode(), digest_size=8).digest(),
        "big",
        signed=True,
    )
    await session.execute(select(func.pg_advisory_xact_lock(lock_key)))


async def import_stages(
    session: AsyncSession,
    actor: Actor,
    content: bytes,
    key: str,
    *,
    content_hash: str | None = None,
    too_large: bool = False,
    file_name: str | None = None,
) -> dict:
    require(actor, "case.csv")
    digest = content_hash or hashlib.sha256(content).hexdigest()
    too_large = too_large or len(content) > MAX_CSV_BYTES
    try:
        record_id, replay = await claim(session, actor, "case.csv", key, {"sha256": digest})
        if replay is not None:
            await session.rollback()
            return await case_import_reads.scoped_result(session, actor, replay)
        await _lock_hash(session, digest)
        if await _has_blocking_upload(session, digest, actor):
            raise ApiError(409, "DUPLICATE_UPLOAD", "CSV has already been processed")
        rows, errors, resolved, contexts = await _evaluate(
            session, actor, content, digest, too_large
        )
        now = utcnow()
        batch_id = uuid4()
        valid = not errors
        await session.execute(
            csv_import_batches.insert().values(
                id=batch_id,
                kind="bank_stage",
                uploaded_by_employee_id=actor.employee_id,
                status="Applied" if valid else "Rejected",
                validation_status="Validated" if valid else "Rejected",
                content_hash=digest,
                file_name=safe_file_name(file_name),
                data_row_count=len(
                    {row[0] for row in rows} | {item["rowNumber"] for item in errors}
                ),
                applied_count=len(resolved) if valid else 0,
                error_count=len(errors),
                created_at=now,
            )
        )
        await _record_results(session, batch_id, rows, errors, valid, contexts, one_shot=True)
        if valid:
            await _apply_resolved(session, actor, batch_id, resolved, now)
        await notify(
            session,
            {actor.employee_id},
            "case.csv_upload_result",
            "A Bank-stage CSV upload result is available",
            csv_import_batch_id=batch_id,
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="case.csv_imported",
            module="cases",
            entity_type="csv_import_batch",
            entity_id=batch_id,
            after={
                "status": "Applied" if valid else "Rejected",
                "rowCount": len(rows),
                "errorCount": len(errors),
                "contentHash": digest,
            },
            context={"caseIds": [str(case["id"]) for _, case, _, _ in resolved] if valid else []},
        )
        result = _result(
            batch_id,
            "Applied" if valid else "Rejected",
            len(resolved) if valid else 0,
            errors,
        )
        await complete(session, record_id, 200, result)
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        raise


async def validate_stages(
    session: AsyncSession,
    actor: Actor,
    content: bytes,
    key: str,
    *,
    content_hash: str | None = None,
    too_large: bool = False,
    file_name: str | None = None,
) -> dict:
    require(actor, "case.csv")
    digest = content_hash or hashlib.sha256(content).hexdigest()
    too_large = too_large or len(content) > MAX_CSV_BYTES
    try:
        record_id, replay = await claim(
            session, actor, "case.csv.validate", key, {"sha256": digest}
        )
        if replay is not None:
            await session.rollback()
            return await case_import_reads.scoped_result(session, actor, replay)
        await _lock_hash(session, digest)
        if await _has_blocking_upload(session, digest, actor):
            raise ApiError(409, "DUPLICATE_UPLOAD", "CSV has already been processed")
        rows, errors, resolved, contexts = await _evaluate(
            session, actor, content, digest, too_large
        )
        now = utcnow()
        batch_id = uuid4()
        valid = not errors
        row_count = len({row[0] for row in rows} | {item["rowNumber"] for item in errors})
        await session.execute(
            csv_import_batches.insert().values(
                id=batch_id,
                kind="bank_stage",
                uploaded_by_employee_id=actor.employee_id,
                status="Validated" if valid else "Rejected",
                validation_status="Validated" if valid else "Rejected",
                content_hash=digest,
                file_name=safe_file_name(file_name),
                data_row_count=row_count,
                applied_count=0,
                error_count=len(errors),
                created_at=now,
            )
        )
        await _record_results(session, batch_id, rows, errors, valid, contexts, one_shot=False)
        await notify(
            session,
            {actor.employee_id},
            "case.csv_upload_result",
            "A Bank-stage CSV validation result is available",
            csv_import_batch_id=batch_id,
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="case.csv_validated",
            module="cases",
            entity_type="csv_import_batch",
            entity_id=batch_id,
            after={
                "status": "Validated" if valid else "Rejected",
                "validationStatus": "Validated" if valid else "Rejected",
                "rowCount": row_count,
                "errorCount": len(errors),
                "contentHash": digest,
                "appliedCount": 0,
            },
            context={"caseIds": []},
        )
        result = await case_import_reads.detail(session, actor, batch_id)
        await complete(session, record_id, 200, result)
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        raise


async def apply_validated_batch(
    session: AsyncSession,
    actor: Actor,
    batch_id,
    key: str,
) -> dict:
    require(actor, "case.csv")
    try:
        record_id, replay = await claim(
            session, actor, "case.csv.apply", key, {"batchId": str(batch_id)}
        )
        if replay is not None:
            await session.rollback()
            return await case_import_reads.scoped_result(session, actor, replay)
        batch = (
            (
                await session.execute(
                    select(csv_import_batches)
                    .where(
                        csv_import_batches.c.id == batch_id,
                        csv_import_batches.c.kind == "bank_stage",
                        csv_import_batches.c.uploaded_by_employee_id == actor.employee_id,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if batch is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        if batch["status"] == "Applied":
            raise ApiError(409, "DUPLICATE_UPLOAD", "CSV has already been processed")
        if batch["status"] != "Validated" or batch["validation_status"] != "Validated":
            raise ApiError(409, "BATCH_INVALID", "This batch cannot be imported")
        digest = batch["content_hash"]
        await _lock_hash(session, digest)
        if await _has_blocking_upload(session, digest, actor):
            raise ApiError(409, "DUPLICATE_UPLOAD", "CSV has already been processed")
        stored = (
            (
                await session.execute(
                    select(csv_import_row_results)
                    .where(csv_import_row_results.c.batch_id == batch_id)
                    .order_by(csv_import_row_results.c.row_number)
                    .with_for_update()
                )
            )
            .mappings()
            .all()
        )
        if any(row["status"] != "Valid" for row in stored) or not stored:
            raise ApiError(409, "BATCH_INVALID", "This batch cannot be imported")
        rows = [
            (
                row["row_number"],
                identifier(row["bank_case_number"] or ""),
                row["requested_stage"] or "",
                row["remark"] or "",
                row["final_pf_amount"],
            )
            for row in stored
        ]
        resolved, errors, _ = await _validate_rows(session, actor, rows)
        now = utcnow()
        if not errors:
            for row_number, case, stage, _ in resolved:
                if stage["final_status"] == "Completed":
                    try:
                        await finance_completion.prepare(session, case, now)
                    except ApiError as exc:
                        if exc.code not in COMPLETION_ERRORS:
                            raise
                        errors.append(
                            {
                                "rowNumber": row_number,
                                "code": exc.code,
                                "message": exc.message,
                            }
                        )
        if errors:
            failures = {item["rowNumber"]: item for item in errors}
            for row in stored:
                failure = failures.get(row["row_number"])
                await session.execute(
                    update(csv_import_row_results)
                    .where(csv_import_row_results.c.id == row["id"])
                    .values(
                        status="Rejected" if failure else "Unchanged",
                        error_code=failure["code"] if failure else None,
                        error_detail=failure["message"] if failure else None,
                    )
                )
            await session.execute(
                update(csv_import_batches)
                .where(csv_import_batches.c.id == batch_id)
                .values(status="Rejected", applied_count=0, error_count=len(errors))
            )
            await audit.record(
                session,
                actor=actor.employee_id,
                action="case.csv_imported",
                module="cases",
                entity_type="csv_import_batch",
                entity_id=batch_id,
                after={
                    "status": "Rejected",
                    "rowCount": len(stored),
                    "errorCount": len(errors),
                    "contentHash": digest,
                },
                context={"caseIds": []},
            )
            result = await case_import_reads.detail(session, actor, batch_id)
            await complete(session, record_id, 200, result)
            await session.commit()
            return result
        await _apply_resolved(session, actor, batch_id, resolved, now)
        await session.execute(
            update(csv_import_row_results)
            .where(uuid_set(csv_import_row_results.c.id, [row["id"] for row in stored]))
            .values(status="Applied", error_code=None, error_detail=None)
        )
        await session.execute(
            update(csv_import_batches)
            .where(csv_import_batches.c.id == batch_id)
            .values(status="Applied", applied_count=len(resolved), error_count=0)
        )
        await notify(
            session,
            {actor.employee_id},
            "case.csv_upload_result",
            "A Bank-stage CSV upload result is available",
            csv_import_batch_id=batch_id,
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="case.csv_imported",
            module="cases",
            entity_type="csv_import_batch",
            entity_id=batch_id,
            after={
                "status": "Applied",
                "rowCount": len(resolved),
                "errorCount": 0,
                "contentHash": digest,
            },
            context={"caseIds": [str(case["id"]) for _, case, _, _ in resolved]},
        )
        result = await case_import_reads.detail(session, actor, batch_id)
        await complete(session, record_id, 200, result)
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        raise


async def _apply_nonfinal_bulk(session, actor, batch_id, resolved, now):
    # Only the non-financial path uses bulk statements. Validation already
    # holds Coordinator assignment and all Case locks in canonical-number order.
    updates = []
    histories = []
    lifecycles = []
    notices = []
    for _, case, stage, remark in resolved:
        updates.append(dict(id=str(case["id"]), stage=stage["name"]))
        histories.append(
            dict(
                id=uuid4(),
                case_id=case["id"],
                stage=stage["name"],
                remark=remark,
                status="Booked",
                updated_by_employee_id=actor.employee_id,
                csv_import_batch_id=batch_id,
                occurred_at=now,
            )
        )
        if case["current_status"] != "Booked":
            lifecycles.append(
                dict(
                    id=uuid4(),
                    case_id=case["id"],
                    previous_status=case["current_status"],
                    status="Booked",
                    actor_employee_id=actor.employee_id,
                    occurred_at=now,
                    context={"csvImportBatchId": str(batch_id), "stage": stage["name"]},
                )
            )
        for recipient in sorted(
            {case["owner_employee_id"], case["created_by_employee_id"]}, key=str
        ):
            notices.append(
                dict(
                    id=uuid4(),
                    recipient_employee_id=recipient,
                    kind="case.stage_updated",
                    case_id=case["id"],
                    message=f"Case {case['internal_case_id']} stage updated",
                )
            )
    # Validation owns every listed Case lock before this statement. Join only
    # those exact IDs, preserving per-row stages and all database row guards.
    # One bound JSON payload avoids 5,000 UPDATE protocol executions.
    statement = text("""
        UPDATE cases AS c
        SET current_stage=source.stage, current_status='Booked',
            finalized_at=NULL, updated_at=:updated_at
        FROM jsonb_to_recordset(CAST(:updates AS jsonb)) AS source(id uuid, stage text)
        WHERE c.id=source.id
    """).bindparams(bindparam("updated_at", type_=DateTime(timezone=True)))
    result = await session.execute(statement, {"updates": json.dumps(updates), "updated_at": now})
    if result.rowcount != len(updates):
        raise RuntimeError("CSV locked Case update count differs")
    await _insert_rows(session, case_stage_history, histories)
    if lifecycles:
        await _insert_rows(session, case_lifecycle_history, lifecycles)
    await _insert_rows(session, notifications, notices)
