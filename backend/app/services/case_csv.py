"""Strict all-or-nothing bank-stage CSV import with retained results."""

import csv
import hashlib
import io
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.cases import case_lifecycle_history, case_stage_history, cases, product_types
from app.db.operations import csv_import_batches, csv_import_row_results, notifications
from app.db.organization import designations, employees
from app.errors import ApiError
from app.normalization import identifier
from app.policies import Actor, require
from app.services import finance_completion
from app.services.case_corrections import FINAL
from app.services.idempotency import claim, complete
from app.services.notification_events import notify
from app.services.pipelines import _valid_stage_set

HEADERS = ("Bank Case Number", "Latest Stage", "Bank Remarks")
TEMPLATE = "Bank Case Number,Latest Stage,Bank Remarks\r\n"
MAX_CSV_BYTES = 5_000_000
MAX_DATA_ROWS = 5_000
READ_CHUNK_BYTES = 64 * 1024


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


def _parse(content: bytes) -> tuple[list[tuple[int, str, str, str]], list[dict]]:
    next_row = 1
    try:
        source = io.StringIO(content.decode("utf-8-sig", errors="strict"), newline="")
        reader = csv.reader(source, strict=True)
        header = next(reader, None)
        if header is None or len(header) != 3 or set(header) != set(HEADERS):
            return [], [
                {
                    "rowNumber": 1,
                    "code": "INVALID_HEADER",
                    "message": "Expected the three template columns",
                }
            ]
        positions = [header.index(name) for name in HEADERS]
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
            if len(raw) != 3:
                errors.append(
                    {
                        "rowNumber": line_number,
                        "code": "MALFORMED_ROW",
                        "message": "Expected three values",
                    }
                )
                continue
            number, stage, remark = (raw[position].strip() for position in positions)
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
            rows.append((line_number, number, stage, remark))
        if not rows and not errors:
            errors.append(
                {"rowNumber": 2, "code": "EMPTY_FILE", "message": "At least one row is required"}
            )
        return rows, errors
    except UnicodeDecodeError, csv.Error:
        return [], [
            {"rowNumber": next_row, "code": "MALFORMED_CSV", "message": "Invalid UTF-8 CSV"}
        ]


def _context(row_number, number, stage_name, remark, case=None, products=None):
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
    }


async def _product_names(session: AsyncSession) -> dict:
    return {
        row.id: row.name
        for row in (await session.execute(select(product_types.c.id, product_types.c.name)))
    }


async def _validate_rows(session: AsyncSession, actor: Actor, rows):
    errors = []
    resolved = []
    contexts = {}
    products = await _product_names(session)
    by_number = {}
    for number in sorted({row[1] for row in rows}):
        case = (
            (
                await session.execute(
                    select(cases)
                    .where(
                        func.upper(
                            func.regexp_replace(
                                func.btrim(cases.c.bank_case_number), "[[:space:]]+", " ", "g"
                            )
                        )
                        == number
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        by_number[number] = case
    for row_number, number, stage_name, remark in rows:
        case = by_number[number]
        contexts[row_number] = _context(row_number, number, stage_name, remark, case, products)
        if case is None:
            errors.append(
                {"rowNumber": row_number, "code": "CASE_UNAVAILABLE", "message": "Case unavailable"}
            )
            continue
        if case["administratively_voided_at"] is not None:
            errors.append(
                {"rowNumber": row_number, "code": "CASE_UNAVAILABLE", "message": "Case unavailable"}
            )
            continue
        if actor.designation == "Coordinator" and not (
            case["coordinator_employee_id"] == actor.employee_id
            or (
                case["owner_transfer_previous_status"] is None
                and case["branch_id"] == actor.branch_id
                and case["department_id"] == actor.department_id
            )
        ):
            errors.append(
                {"rowNumber": row_number, "code": "CASE_UNAVAILABLE", "message": "Case unavailable"}
            )
            continue
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
                {"rowNumber": row_number, "code": "FINAL_LOCK", "message": "Case is final"}
            )
            continue
        if case["bank_case_number"] is None or case["pipeline_configuration_id"] is None:
            errors.append(
                {"rowNumber": row_number, "code": "NOT_BOOKED", "message": "Case is not booked"}
            )
            continue
        stages = await _valid_stage_set(session, case["pipeline_configuration_id"])
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
        resolved.append((row_number, case, stage, remark))
    return resolved, errors, contexts


async def _record_results(session, batch_id, rows, errors, valid, contexts, *, one_shot: bool):
    failures = {item["rowNumber"]: item for item in errors}
    numbers = sorted({row[0] for row in rows} | set(failures) | set(contexts))
    for number in numbers:
        failure = failures.get(number)
        context = contexts.get(number, {})
        if one_shot:
            status = "Applied" if valid else ("Rejected" if failure else "Skipped")
        else:
            status = "Invalid" if failure else "Valid"
        await session.execute(
            csv_import_row_results.insert().values(
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
            )
        )


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


async def _has_blocking_upload(session: AsyncSession, digest: str) -> bool:
    prior = (
        await session.execute(
            select(csv_import_batches.c.id, csv_import_batches.c.status).where(
                csv_import_batches.c.kind == "bank_stage",
                csv_import_batches.c.content_hash == digest,
            )
        )
    ).all()
    for batch_id, status in prior:
        if status == "Validated":
            continue
        if status != "Rejected":
            return True
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
        if "FINANCIAL_RULE_MISSING" not in codes or any(
            code not in {None, "FINANCIAL_RULE_MISSING"} for code in codes
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
                    if exc.code != "FINANCIAL_RULE_MISSING":
                        raise
                    errors.append(
                        {"rowNumber": row_number, "code": exc.code, "message": exc.message}
                    )
    for row_number, number, stage_name, remark in rows:
        contexts.setdefault(row_number, _context(row_number, number, stage_name, remark))
    return rows, errors, resolved, contexts


async def _apply_resolved(session, actor, batch_id, resolved, now):
    prepared = {}
    for _row_number, case, stage, _ in resolved:
        if stage["final_status"] == "Completed":
            prepared[case["id"]] = await finance_completion.prepare(session, case, now)
    for _, case, stage, remark in resolved:
        next_status = stage["final_status"] or "Booked"
        await session.execute(
            update(cases)
            .where(cases.c.id == case["id"])
            .values(
                current_stage=stage["name"],
                current_status=next_status,
                finalized_at=now if stage["is_final"] else None,
                updated_at=now,
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
            return replay
        await _lock_hash(session, digest)
        if await _has_blocking_upload(session, digest):
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
            batch_id, "Applied" if valid else "Rejected", len(resolved) if valid else 0, errors
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
            return replay
        await _lock_hash(session, digest)
        if await _has_blocking_upload(session, digest):
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
        from app.services import case_import_reads

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
            return replay
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
        if await _has_blocking_upload(session, digest):
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
                        if exc.code != "FINANCIAL_RULE_MISSING":
                            raise
                        errors.append(
                            {"rowNumber": row_number, "code": exc.code, "message": exc.message}
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
            from app.services import case_import_reads

            result = await case_import_reads.detail(session, actor, batch_id)
            await complete(session, record_id, 200, result)
            await session.commit()
            return result
        await _apply_resolved(session, actor, batch_id, resolved, now)
        for row in stored:
            await session.execute(
                update(csv_import_row_results)
                .where(csv_import_row_results.c.id == row["id"])
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
        from app.services import case_import_reads

        result = await case_import_reads.detail(session, actor, batch_id)
        await complete(session, record_id, 200, result)
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        raise
