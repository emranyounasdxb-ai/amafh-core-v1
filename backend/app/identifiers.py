"""Concurrency-safe, non-recycling business references from DEC-028."""

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.cases import case_id_counters

DUBAI = ZoneInfo("Asia/Dubai")


async def new_system_employee_code(session: AsyncSession) -> str:
    number = await session.scalar(text("SELECT nextval('amafh_employee_code_seq')"))
    assert number is not None
    return f"EMP-{number:06d}"


async def new_bank_code(session: AsyncSession) -> str:
    number = await session.scalar(text("SELECT nextval('amafh_bank_code_seq')"))
    assert number is not None
    return f"BANK-{number:06d}"


async def new_asset_code(session: AsyncSession) -> str:
    number = await session.scalar(text("SELECT nextval('amafh_asset_code_seq')"))
    assert number is not None
    return f"AST-{number:06d}"


async def new_case_id(session: AsyncSession, created_at: datetime) -> str:
    year = created_at.astimezone(DUBAI).year
    statement = (
        insert(case_id_counters)
        .values(id=uuid4(), dubai_year=year, last_value=1)
        .on_conflict_do_update(
            index_elements=[case_id_counters.c.dubai_year],
            set_={"last_value": case_id_counters.c.last_value + 1},
        )
        .returning(case_id_counters.c.last_value)
    )
    number = await session.scalar(statement)
    assert number is not None
    return f"CASE-{year:04d}-{number:06d}"
