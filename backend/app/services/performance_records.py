"""Read retained source facts for one employee's derived performance."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Date, DateTime, Numeric, Text, func, or_, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
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
from app.db.query_sets import uuid_set
from app.schemas.performance import PerformanceFilters
from app.services import performance_compact
from app.services.assignment_activity import changes_for
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
    assignment_changes: list[dict] = dataclass_field(default_factory=list)
    activity_assignments: dict[date | datetime, dict | None] = dataclass_field(default_factory=dict)
    timeline_cache: dict = dataclass_field(default_factory=dict)
    compact_range: tuple[date, date] | None = None
    compact_activity: list[dict] = dataclass_field(default_factory=list)
    target_denominators: dict = dataclass_field(default_factory=dict)


def _group(rows: list[dict], key: str) -> dict[UUID, list[dict]]:
    grouped: dict[UUID, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row[key], []).append(row)
    return grouped


def _json_rows(statement):
    source = statement.subquery()
    return select(
        func.json_agg(func.row_to_json(source.table_valued())).cast(Text)
    ).scalar_subquery()


def _typed_rows(values, statement, typed_cache=None) -> list[dict]:
    """Restore the same UUID/date/Decimal facts from one compact JSON payload."""
    rows = json.loads(values, parse_float=Decimal) if values is not None else []
    for column in statement.selected_columns:
        kind = column.type
        convert: Callable[[Any], Any] | None = None
        if isinstance(kind, PG_UUID):
            convert = UUID
        elif isinstance(kind, DateTime):
            convert = datetime.fromisoformat
        elif isinstance(kind, Date):
            convert = date.fromisoformat
        elif isinstance(kind, Numeric):
            convert = Decimal
        if convert is not None:
            converted = {} if typed_cache is None else typed_cache.setdefault(type(kind), {})
            for row in rows:
                value = row[column.key]
                if value is not None:
                    if value not in converted:
                        converted[value] = convert(value)
                    row[column.key] = converted[value]
    return rows


async def release_read_connection(session: AsyncSession) -> None:
    """Retained API facts need no idle connection during Python calculation."""
    if session.info.get("performance_read_api") is True and session.in_transaction():
        await session.rollback()


async def load(
    session: AsyncSession, employee: dict, filters: PerformanceFilters | None = None
) -> PerformanceRecords:
    employee_id = employee["id"]
    cache: dict[UUID, PerformanceRecords] | None = session.info.get("performance_records_cache")
    if cache is not None and employee_id in cache and _usable(cache[employee_id], filters):
        await release_read_connection(session)
        return cache[employee_id]
    records = await preload(session, [employee], filters)
    return records[employee_id]


def _usable(records: PerformanceRecords, filters: PerformanceFilters | None) -> bool:
    period = getattr(records, "compact_range", None)
    return period is None or (
        filters is not None and period == (filters.startDate, filters.endDate)
    )


async def preload(
    session: AsyncSession, people: list[dict], filters: PerformanceFilters | None = None
) -> dict[UUID, PerformanceRecords]:
    """Fetch a report population's retained facts in batches for one read."""
    cache: dict[UUID, PerformanceRecords] = session.info.get("performance_records_cache", {})
    pending = {
        person["id"]: person
        for person in people
        if person["id"] not in cache or not _usable(cache[person["id"]], filters)
    }
    if not pending:
        await release_read_connection(session)
        return cache
    ids = list(pending)
    assignment_changes = await changes_for(session, ids)

    metadata_statements = {
        "assignments": select(assignment_history).where(
            uuid_set(assignment_history.c.employee_id, ids)
        ),
        "memberships": select(team_memberships).where(
            uuid_set(team_memberships.c.employee_id, ids)
        ),
        "leaderships": select(team_leader_history).where(
            uuid_set(team_leader_history.c.leader_employee_id, ids)
        ),
        "versions": select(targets),
    }
    # Read the same raw histories/target versions in one statement snapshot.
    # Typed restoration preserves UUID/date/Decimal values for policy/math;
    # compact eligibility is still freshly proven by the separate facts query.
    metadata_facts = (
        (
            await session.execute(
                select(
                    *(
                        _json_rows(statement).label(name)
                        for name, statement in metadata_statements.items()
                    )
                )
            )
        )
        .mappings()
        .one()
    )
    metadata_types: dict = {}
    metadata_rows = {
        name: _typed_rows(metadata_facts[name], statement, metadata_types)
        for name, statement in metadata_statements.items()
    }
    assignments = _group(metadata_rows["assignments"], "employee_id")
    memberships = _group(metadata_rows["memberships"], "employee_id")
    leaderships = _group(metadata_rows["leaderships"], "leader_employee_id")
    versions = metadata_rows["versions"]
    # Only a proven constant employee/team scope may use distinct SQL counters.
    # Ambiguous or timed transfer histories retain the complete reference path.
    compact_ids = []
    if filters is not None and filters.startDate is not None and filters.endDate is not None:
        for employee_id, person in pending.items():
            history = assignments.get(employee_id) or [_fallback_assignment(person)]
            if performance_compact.stable_period(
                history,
                memberships.get(employee_id, []),
                leaderships.get(employee_id, []),
                assignment_changes.get(employee_id, []),
                filters.startDate,
                filters.endDate,
            ):
                compact_ids.append(employee_id)
    compact = (
        await performance_compact.read(
            session,
            compact_ids,
            filters.startDate,
            filters.endDate,
            proofs=[
                performance_compact.proof(
                    pending[employee_id],
                    assignments.get(employee_id, []),
                    memberships.get(employee_id, []),
                    leaderships.get(employee_id, []),
                )
                for employee_id in compact_ids
            ],
        )
        if compact_ids
        and filters is not None
        and filters.startDate is not None
        and filters.endDate is not None
        else {}
    )
    ids = [employee_id for employee_id in ids if employee_id not in compact]
    owner_case_ids = select(case_ownership_history.c.case_id).where(
        uuid_set(case_ownership_history.c.owner_employee_id, ids)
    )
    financial_case_ids = select(case_financial_results.c.case_id).where(
        uuid_set(case_financial_results.c.credited_owner_employee_id, ids)
    )
    case_statement = select(
        cases.c.id,
        cases.c.created_by_employee_id,
        cases.c.owner_employee_id,
        cases.c.created_at,
        cases.c.product_type_id,
        cases.c.bank_id,
        cases.c.pipeline_configuration_id,
        cases.c.current_status,
        cases.c.administratively_voided_at,
    ).where(
        or_(
            uuid_set(cases.c.created_by_employee_id, ids),
            uuid_set(cases.c.owner_employee_id, ids),
            cases.c.id.in_(owner_case_ids),
            cases.c.id.in_(financial_case_ids),
        )
    )
    selected_cases = case_statement.cte().prefix_with("MATERIALIZED")
    selected_ids = select(selected_cases.c.id)
    ownership_statement = select(
        case_ownership_history.c.id,
        case_ownership_history.c.case_id,
        case_ownership_history.c.owner_employee_id,
        case_ownership_history.c.started_at,
        case_ownership_history.c.ended_at,
    ).where(case_ownership_history.c.case_id.in_(selected_ids))
    lifecycle_statement = select(
        case_lifecycle_history.c.id,
        case_lifecycle_history.c.case_id,
        case_lifecycle_history.c.status,
        case_lifecycle_history.c.occurred_at,
    ).where(case_lifecycle_history.c.case_id.in_(selected_ids))
    stages_statement = select(
        case_stage_history.c.id,
        case_stage_history.c.case_id,
        case_stage_history.c.stage,
        case_stage_history.c.occurred_at,
    ).where(case_stage_history.c.case_id.in_(selected_ids))
    results_statement = select(
        case_financial_results.c.case_id,
        case_financial_results.c.credited_owner_employee_id,
        case_financial_results.c.product_code,
        case_financial_results.c.completed_at,
        case_financial_results.c.cc_points,
        case_financial_results.c.pf_amount_aed,
    ).where(uuid_set(case_financial_results.c.credited_owner_employee_id, ids))
    # One MVCC statement retains the selected Cases and all their histories/results
    # together, without tens of thousands of SQLAlchemy RowMapping allocations.
    # Compact records already retain the necessary product/stage facts. When
    # every employee is proven eligible, no reference-history bundle is needed.
    facts = (
        (
            (
                await session.execute(
                    select(
                        _json_rows(select(selected_cases)).label("cases"),
                        _json_rows(ownership_statement).label("ownership"),
                        _json_rows(lifecycle_statement).label("lifecycle"),
                        _json_rows(stages_statement).label("stages"),
                        _json_rows(results_statement).label("results"),
                    )
                )
            )
            .mappings()
            .one()
        )
        if ids
        else dict.fromkeys(("cases", "ownership", "lifecycle", "stages", "results"))
    )
    typed_cache: dict = {}
    case_rows = _typed_rows(facts["cases"], case_statement, typed_cache)
    ownership = _group(_typed_rows(facts["ownership"], ownership_statement, typed_cache), "case_id")
    lifecycle = _group(_typed_rows(facts["lifecycle"], lifecycle_statement, typed_cache), "case_id")
    stages = _group(_typed_rows(facts["stages"], stages_statement, typed_cache), "case_id")
    results = _group(
        _typed_rows(facts["results"], results_statement, typed_cache),
        "credited_owner_employee_id",
    )
    product_codes: dict[UUID, str] = (
        {
            product_id: code
            for product_id, code in (
                await session.execute(select(product_types.c.id, product_types.c.code))
            ).all()
        }
        if ids
        else {}
    )
    classified = await department_products(session)
    expected_stage_days = (
        {
            (row["pipeline_configuration_id"], row["name"]): row["expected_business_days"]
            for row in (await session.execute(select(pipeline_stages))).mappings()
        }
        if ids
        else {}
    )
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
    # Traverse the batch once rather than scanning every case for every employee.
    # Keep source order and deduplicate overlapping creator/current/former/credited
    # owner relationships without changing any history used for scope decisions.
    employee_cases: dict[UUID, list[dict]] = {employee_id: [] for employee_id in ids}
    employees_by_case: dict[UUID, set[UUID]] = {}
    for employee_id, owned_ids in cases_by_employee.items():
        for case_id in owned_ids:
            employees_by_case.setdefault(case_id, set()).add(employee_id)
    for row in case_rows:
        for employee_id in employees_by_case.get(row["id"], ()):
            employee_cases[employee_id].append(row)
    timeline_cache: dict = {}
    target_denominators: dict = {}
    indexed_versions: dict[tuple, list[dict]] = {}
    for version in versions:
        target_scope = tuple(
            version[field] for field in ("branch_id", "department_id", "designation_id")
        )
        indexed_versions.setdefault(target_scope, []).append(version)
    for employee_id, person in pending.items():
        employee_assignments = assignments.get(employee_id) or [_fallback_assignment(person)]
        cache[employee_id] = PerformanceRecords(
            employee_assignments,
            memberships.get(employee_id, []),
            leaderships.get(employee_id, []),
            indexed_versions.get(
                tuple(
                    employee_assignments[0][field]
                    for field in ("branch_id", "department_id", "designation_id")
                ),
                [],
            )
            if employee_id in compact
            else versions,
            employee_cases.get(employee_id, []),
            ownership,
            lifecycle,
            stages,
            results.get(employee_id, []),
            product_codes,
            classified,
            expected_stage_days,
            assignment_changes.get(employee_id, []),
            timeline_cache=timeline_cache,
            compact_range=(filters.startDate, filters.endDate)
            if employee_id in compact
            and filters is not None
            and filters.startDate is not None
            and filters.endDate is not None
            else None,
            compact_activity=compact.get(employee_id, []),
            target_denominators=target_denominators,
        )
    await release_read_connection(session)
    return cache


def _fallback_assignment(person: dict) -> dict:
    return {
        "id": person["id"],
        "branch_id": person["branch_id"],
        "department_id": person["department_id"],
        "designation_id": person["designation_id"],
        "assignment_start_date": person["date_of_joining"],
        "assignment_end_date": None,
    }
