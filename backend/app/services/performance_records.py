"""Read retained source facts for one employee's derived performance."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.cases import (
    case_lifecycle_history,
    case_ownership_history,
    case_stage_history,
    cases,
    pipeline_stages,
    product_types,
)
from app.db.finance import case_financial_results
from app.db.operations import targets
from app.db.organization import (
    assignment_history,
    team_leader_history,
    team_memberships,
)
from app.services.department_products import department_products


@dataclass
class PerformanceRecords:
    assignments: list[dict]
    memberships: list[dict]
    leaderships: list[dict]
    versions: list[dict]
    cases: list[dict]
    ownership: dict[UUID, list[dict]]
    lifecycle: dict[UUID, list[dict]]
    stages: dict[UUID, list[dict]]
    results: list[dict]
    product_codes: dict[UUID, str]
    department_products: dict[UUID, str]
    expected_stage_days: dict[tuple[UUID, str], int]


def _group(rows: list[dict], key: str) -> dict[UUID, list[dict]]:
    grouped: dict[UUID, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row[key], []).append(row)
    return grouped


async def load(session: AsyncSession, employee: dict) -> PerformanceRecords:
    employee_id = employee["id"]
    cache: dict[UUID, PerformanceRecords] | None = session.info.get("performance_records_cache")
    if cache is not None and employee_id in cache:
        return cache[employee_id]
    records = await preload(session, [employee])
    return records[employee_id]


async def preload(session: AsyncSession, people: list[dict]) -> dict[UUID, PerformanceRecords]:
    """Fetch a report population's retained facts in batches for one read."""
    cache: dict[UUID, PerformanceRecords] = session.info.get("performance_records_cache", {})
    pending = {person["id"]: person for person in people if person["id"] not in cache}
    if not pending:
        return cache
    ids = list(pending)

    async def rows(statement) -> list[dict]:
        return [dict(row) for row in (await session.execute(statement)).mappings()]

    assignments = _group(
        await rows(select(assignment_history).where(assignment_history.c.employee_id.in_(ids))),
        "employee_id",
    )
    memberships = _group(
        await rows(select(team_memberships).where(team_memberships.c.employee_id.in_(ids))),
        "employee_id",
    )
    leaderships = _group(
        await rows(
            select(team_leader_history).where(team_leader_history.c.leader_employee_id.in_(ids))
        ),
        "leader_employee_id",
    )
    versions = await rows(select(targets))
    owner_case_ids = select(case_ownership_history.c.case_id).where(
        case_ownership_history.c.owner_employee_id.in_(ids)
    )
    financial_case_ids = select(case_financial_results.c.case_id).where(
        case_financial_results.c.credited_owner_employee_id.in_(ids)
    )
    case_rows = await rows(
        select(cases).where(
            or_(
                cases.c.created_by_employee_id.in_(ids),
                cases.c.owner_employee_id.in_(ids),
                cases.c.id.in_(owner_case_ids),
                cases.c.id.in_(financial_case_ids),
            )
        )
    )
    case_ids = [row["id"] for row in case_rows]
    ownership = (
        _group(
            await rows(
                select(case_ownership_history).where(case_ownership_history.c.case_id.in_(case_ids))
            ),
            "case_id",
        )
        if case_ids
        else {}
    )
    lifecycle = (
        _group(
            await rows(
                select(case_lifecycle_history).where(case_lifecycle_history.c.case_id.in_(case_ids))
            ),
            "case_id",
        )
        if case_ids
        else {}
    )
    stages = (
        _group(
            await rows(
                select(case_stage_history).where(case_stage_history.c.case_id.in_(case_ids))
            ),
            "case_id",
        )
        if case_ids
        else {}
    )
    results = _group(
        await rows(
            select(case_financial_results).where(
                case_financial_results.c.credited_owner_employee_id.in_(ids)
            )
        ),
        "credited_owner_employee_id",
    )
    product_codes: dict[UUID, str] = {
        product_id: code
        for product_id, code in (
            await session.execute(select(product_types.c.id, product_types.c.code))
        ).all()
    }
    classified = await department_products(session)
    expected_stage_days = {
        (row["pipeline_configuration_id"], row["name"]): row["expected_business_days"]
        for row in (await session.execute(select(pipeline_stages))).mappings()
    }
    cases_by_employee: dict[UUID, set[UUID]] = {employee_id: set() for employee_id in ids}
    for row in case_rows:
        for field in ("created_by_employee_id", "owner_employee_id"):
            employee_id = row[field]
            if employee_id in cases_by_employee:
                cases_by_employee[employee_id].add(row["id"])
    for case_id, history in ownership.items():
        for row in history:
            employee_id = row["owner_employee_id"]
            if employee_id in cases_by_employee:
                cases_by_employee[employee_id].add(case_id)
    for employee_id, financial_rows in results.items():
        cases_by_employee[employee_id].update(row["case_id"] for row in financial_rows)
    for employee_id, person in pending.items():
        employee_assignments = assignments.get(employee_id) or [
            {
                "id": employee_id,
                "branch_id": person["branch_id"],
                "department_id": person["department_id"],
                "designation_id": person["designation_id"],
                "assignment_start_date": person["date_of_joining"],
                "assignment_end_date": None,
            }
        ]
        cache[employee_id] = PerformanceRecords(
            employee_assignments,
            memberships.get(employee_id, []),
            leaderships.get(employee_id, []),
            versions,
            [row for row in case_rows if row["id"] in cases_by_employee[employee_id]],
            ownership,
            lifecycle,
            stages,
            results.get(employee_id, []),
            product_codes,
            classified,
            expected_stage_days,
        )
    return cache
