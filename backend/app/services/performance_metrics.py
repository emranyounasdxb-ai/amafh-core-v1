"""Derive employee activity and target progress from retained source facts."""

from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.schemas.performance import PerformanceFilters
from app.services.performance_delay import count_delayed, stage_start
from app.services.performance_math import (
    DUBAI,
    achievement_percentage,
    assignment_on,
    dubai_date,
    target_denominator,
    target_on,
)
from app.services.performance_records import PerformanceRecords, load
from app.services.performance_scope import PerformanceScope
from app.whole_numbers import whole_text


def _owner_at(rows: list[dict], when: datetime, fallback: UUID) -> UUID | None:
    matches = [
        row
        for row in rows
        if row["started_at"] <= when and (row["ended_at"] is None or when < row["ended_at"])
    ]
    if matches:
        return max(matches, key=lambda row: (row["started_at"], str(row["id"])))[
            "owner_employee_id"
        ]
    return fallback if not rows else None


def _status_at(events: list[dict], as_of: date, fallback: str) -> str:
    prior = [row for row in events if dubai_date(row["occurred_at"]) <= as_of]
    if not prior:
        return fallback
    return max(prior, key=lambda row: (row["occurred_at"], str(row["id"])))["status"]


def _in_range(day: date, start: date, end: date) -> bool:
    return start <= day <= end


def _allowed(
    scope: PerformanceScope,
    employee_id: UUID,
    day: date,
    records: PerformanceRecords,
    filters: PerformanceFilters,
) -> bool:
    return scope.activity_allowed(
        employee_id,
        day,
        records.assignments,
        records.memberships,
        records.leaderships,
        filters,
    )


async def derive_with_denominator(
    session: AsyncSession,
    scope: PerformanceScope,
    employee: dict,
    filters: PerformanceFilters,
) -> tuple[dict, dict[str, Decimal]]:
    cache: dict[tuple, tuple[dict, dict[str, Decimal]]] | None = session.info.get(
        "performance_metrics_cache"
    )
    key = (
        scope.actor.employee_id,
        scope.actor.designation,
        scope.actor.branch_id,
        scope.actor.department_id,
        scope.team_id,
        scope.finance_report,
        employee["id"],
        filters.model_dump_json(),
    )
    if cache is not None and key in cache:
        return cache[key]
    start = filters.startDate or employee["date_of_joining"]
    end = filters.endDate or datetime.now(DUBAI).date()
    if end > datetime.now(DUBAI).date() or start > end:
        raise ApiError(422, "PERFORMANCE_DATE_INVALID", "Date range is unavailable")
    records = await load(session, employee)
    employee_id = employee["id"]
    counts: dict[str, set[UUID]] = {
        "created": set(),
        "booked": set(),
        "completed": set(),
        "rejected": set(),
    }
    in_progress: set[UUID] = set()
    stages: dict[str, int] = {}
    delay_candidates: list[tuple[UUID, date, int]] = []
    for case in records.cases:
        case_id = case["id"]
        product = records.product_codes.get(case["product_type_id"])
        if filters.productCode is not None and filters.productCode != product:
            continue
        if filters.bankId is not None and case["bank_id"] != filters.bankId:
            continue
        created_day = dubai_date(case["created_at"])
        if (
            case["created_by_employee_id"] == employee_id
            and _in_range(created_day, start, end)
            and (_allowed(scope, employee_id, created_day, records, filters))
        ):
            counts["created"].add(case_id)
        owner_rows = records.ownership.get(case_id, [])
        events = records.lifecycle.get(case_id, [])
        for event in events:
            day = dubai_date(event["occurred_at"])
            status = event["status"]
            if status not in {"Booked", "Rejected"} or not _in_range(day, start, end):
                continue
            if (
                _owner_at(owner_rows, event["occurred_at"], case["owner_employee_id"])
                != employee_id
            ):
                continue
            if _allowed(scope, employee_id, day, records, filters):
                counts["booked" if status == "Booked" else "rejected"].add(case_id)
        if created_day > end or (
            case["administratively_voided_at"] is not None
            and (dubai_date(case["administratively_voided_at"]) <= end)
        ):
            continue
        as_of = datetime.combine(end, time.max, tzinfo=DUBAI)
        if _owner_at(owner_rows, as_of, case["owner_employee_id"]) != employee_id:
            continue
        if not _allowed(scope, employee_id, end, records, filters):
            continue
        status = _status_at(events, end, case["current_status"])
        if status in {"Completed", "Rejected"}:
            continue
        in_progress.add(case_id)
        current_stage = stage_start(records.stages.get(case_id, []), end)
        if current_stage is None:
            continue
        stage_name, since = current_stage
        stages[stage_name] = stages.get(stage_name, 0) + 1
        expected = records.expected_stage_days.get((case["pipeline_configuration_id"], stage_name))
        if expected is not None:
            delay_candidates.append((case_id, since, expected))
    achieved = {"CC": Decimal(0), "PF": Decimal(0)}
    target_achieved = {"CC": Decimal(0), "PF": Decimal(0)}
    case_banks = {row["id"]: row["bank_id"] for row in records.cases}
    for result in records.results:
        day = dubai_date(result["completed_at"])
        product = result["product_code"]
        if product not in achieved or (
            filters.productCode is not None and filters.productCode != product
        ):
            continue
        if filters.bankId is not None and case_banks.get(result["case_id"]) != filters.bankId:
            continue
        if not _in_range(day, start, end) or not _allowed(
            scope, employee_id, day, records, filters
        ):
            continue
        value = result["cc_points"] if product == "CC" else result["pf_amount_aed"]
        if value is None:
            value = 0
        amount = Decimal(value)
        achieved[product] += amount
        counts["completed"].add(result["case_id"])
        assignment = assignment_on(records.assignments, day)
        if (
            assignment is not None
            and records.department_products.get(assignment["department_id"]) == product
            and (target_on(records.versions, assignment, day) is not None)
        ):
            target_achieved[product] += amount
    progress = {}
    denominators: dict[str, Decimal] = {}
    for product in ("CC", "PF"):
        denominator = (
            target_denominator(
                start,
                end,
                records.assignments,
                records.versions,
                product,
                records.department_products,
                lambda day: _allowed(scope, employee_id, day, records, filters),
            )
            if filters.productCode is None or filters.productCode == product
            else Decimal(0)
        )
        denominators[product] = denominator
        percentage = achievement_percentage(target_achieved[product], denominator)
        end_assignment = assignment_on(records.assignments, end)
        end_target = target_on(records.versions, end_assignment, end)
        active_on_end = (
            end_target is not None
            and end_assignment is not None
            and (records.department_products.get(end_assignment["department_id"]) == product)
            and _allowed(scope, employee_id, end, records, filters)
        )
        progress[product] = {
            "state": "No Target" if percentage is None else "Configured",
            "achieved": whole_text(target_achieved[product]),
            "achievementPercentage": str(percentage) if percentage is not None else None,
            "activeOnEndDate": active_on_end,
        }
    delayed_count, delayed_state = await count_delayed(session, delay_candidates, end)
    result = {
        "employeeId": str(employee_id),
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "createdCaseCount": len(counts["created"]),
        "bookedCaseCount": len(counts["booked"]),
        "completedCaseCount": len(counts["completed"]),
        "rejectedCaseCount": len(counts["rejected"]),
        "inProgressCaseCount": len(in_progress),
        "inProgressByStage": stages,
        "delayedCaseCount": delayed_count,
        "delayedMetricState": delayed_state,
        "achievedCCPoints": whole_text(achieved["CC"]),
        "achievedPFAed": whole_text(achieved["PF"]),
        "targetProgress": progress,
    }
    outcome = result, denominators
    if cache is not None:
        cache[key] = outcome
    return outcome


async def derive(
    session: AsyncSession,
    scope: PerformanceScope,
    employee: dict,
    filters: PerformanceFilters,
) -> dict:
    result, _ = await derive_with_denominator(session, scope, employee, filters)
    return result
