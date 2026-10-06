"""Bounded Attendance CSV reading and deterministic row validation."""

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import date, time

from fastapi import UploadFile

HEADERS = (
    "System Employee Code",
    "Employee Name",
    "Attendance Date",
    "Check-in Time",
    "Check-out Time",
)
MAX_CSV_BYTES = 5_000_000
MAX_DATA_ROWS = 5_000
READ_CHUNK_BYTES = 64 * 1024
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
TIME_PATTERN = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\Z")


@dataclass(frozen=True)
class ParsedRow:
    number: int
    code: str
    attendance_date: date
    check_in: time
    check_out: time


async def read_upload(file: UploadFile) -> tuple[bytes, str, int, bool]:
    """Hash every byte while retaining no more than the approved maximum."""
    digest = hashlib.sha256()
    content = bytearray()
    total = 0
    while chunk := await file.read(READ_CHUNK_BYTES):
        digest.update(chunk)
        total += len(chunk)
        if len(content) < MAX_CSV_BYTES:
            content.extend(chunk[: MAX_CSV_BYTES - len(content)])
    return bytes(content), digest.hexdigest(), total, total > MAX_CSV_BYTES


def _error(number: int, column: str | None, code: str, message: str) -> dict:
    return {"rowNumber": number, "column": column, "code": code, "message": message}


def _date(value: str) -> date | None:
    if not DATE_PATTERN.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _time(value: str) -> time | None:
    if not TIME_PATTERN.fullmatch(value):
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def parse(content: bytes) -> tuple[list[ParsedRow], list[dict], int, date | None]:
    rows: list[ParsedRow] = []
    errors: list[dict] = []
    count = 0
    first_date: date | None = None
    seen: set[str] = set()
    next_number = 1
    try:
        reader = csv.reader(
            io.StringIO(content.decode("utf-8-sig", errors="strict"), newline=""),
            strict=True,
        )
        header = next(reader, None)
        if header != list(HEADERS):
            return (
                [],
                [_error(1, None, "INVALID_HEADER", "Expected the five template columns in order")],
                0,
                None,
            )
        for number, raw in enumerate(reader, start=2):
            next_number = number
            count += 1
            if count > MAX_DATA_ROWS:
                return (
                    [],
                    [_error(number, None, "CSV_ROW_LIMIT", "CSV exceeds 5,000 data rows")],
                    count,
                    None,
                )
            if len(raw) != len(HEADERS):
                errors.append(_error(number, None, "MALFORMED_ROW", "Expected five values"))
                continue
            code, name, raw_date, check_in, check_out = (value.strip() for value in raw)
            invalid = False
            for column, value in zip(
                HEADERS, (code, name, raw_date, check_in, check_out), strict=True
            ):
                if not value:
                    errors.append(
                        _error(number, column, "REQUIRED_VALUE", "Required value missing")
                    )
                    invalid = True
            if invalid:
                continue
            if code in seen:
                errors.append(_error(number, HEADERS[0], "DUPLICATE_EMPLOYEE", "Employee repeated"))
                continue
            seen.add(code)
            parsed_date = _date(raw_date)
            if parsed_date is None:
                errors.append(_error(number, HEADERS[2], "INVALID_DATE", "Use YYYY-MM-DD"))
            elif first_date is None:
                first_date = parsed_date
            elif parsed_date != first_date:
                errors.append(
                    _error(number, HEADERS[2], "MULTIPLE_DATES", "One Attendance Date is required")
                )
            in_time = _time(check_in)
            out_time = _time(check_out)
            if in_time is None:
                errors.append(_error(number, HEADERS[3], "INVALID_TIME", "Use a 24-hour time"))
            if out_time is None:
                errors.append(_error(number, HEADERS[4], "INVALID_TIME", "Use a 24-hour time"))
            if in_time is not None and out_time is not None and out_time <= in_time:
                errors.append(
                    _error(
                        number, HEADERS[4], "TIME_ORDER_INVALID", "Check-out must follow check-in"
                    )
                )
            if parsed_date is not None and in_time is not None and out_time is not None:
                if parsed_date == first_date and out_time > in_time:
                    rows.append(ParsedRow(number, code, parsed_date, in_time, out_time))
        if count == 0:
            errors.append(_error(2, None, "EMPTY_FILE", "At least one employee row is required"))
    except UnicodeDecodeError, csv.Error:
        errors.append(_error(next_number, None, "MALFORMED_CSV", "Invalid UTF-8 CSV"))
    return rows, errors, count, first_date
