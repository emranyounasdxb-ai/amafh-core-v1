"""Derive employee activity and target progress from retained source facts."""

from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.schemas.performance import PerformanceFilters
from app.services import performance_budget
from app.services.assignment_activity import assignment_at
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
        if len(matches) == 1:
            return matches[0]["owner_employee_id"]
        return max(matches, key=lambda row: (row["started_at"], str(row["id"])))[
            "owner_employee_id"
        ]
    return fallback if not rows else None


def _status_at(events: list[dict], as_of: date, fallback: str) -> str:
    prior = [row for row in events if dubai_date(row["occurred_at"]) <= as_of]
    if not prior:
        return fallback
    if len(prior) == 1:
        return prior[0]["status"]
    return max(prior, key=lambda row: (row["occurred_at"], str(row["id"])))["status"]


def _in_range(day: date, start: date, end: date) -> bool:
    return start <= day <= end


def _case_timeline(records: PerformanceRecords, case: dict, end: date) -> dict:
    """Actor-independent retained facts, bounded to one as-of date per batch."""
    cache = getattr(records, "timeline_cache", None)
    if cache is not None:
        if cache.get("end") != end:
            cache.clear()
            cache.update(end=end, rows={})
        if case["id"] in cache["rows"]:
            return cache["rows"][case["id"]]
    ownership = records.ownership.get(case["id"], [])
    events = records.lifecycle.get(case["id"], [])
    status = _status_at(events, end, case["current_status"])
    facts = {
        "created": dubai_date(case["created_at"]),
        "voided": dubai_date(case["administratively_voided_at"])
        if case["administratively_voided_at"] is not None
        else None,
        "events": [
            (
                event,
                dubai_date(event["occurred_at"]),
                _owner_at(ownership, event["occurred_at"], case["owner_employee_id"]),
            )
            for event in events
            if event["status"] in {"Booked", "Rejected"}
        ],
        "owner": _owner_at(
            ownership,
            datetime.combine(end, time.max, tzinfo=DUBAI),
            case["owner_employee_id"],
        ),
        "status": status,
        "stage": stage_start(records.stages.get(case["id"], []), end)
        if status not in {"Completed", "Rejected"}
        else None,
    }
    if cache is not None:
        cache["rows"][case["id"]] = facts
    return facts


def _allowed(
    scope: PerformanceScope,
    employee_id: UUID,
    day: date | datetime,
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
        records.assignment_changes,
        getattr(records, "activity_assignments", None),
    )


def _same_branch_cached(
    session: AsyncSession,
    scope: PerformanceScope,
    employee_id: UUID,
    filters: PerformanceFilters,
    cache: dict[tuple, tuple[dict, dict[str, Decimal]]] | None,
) -> tuple[dict, dict[str, Decimal]] | None:
    """Reuse an unrestricted result only when branch restriction adds no boundary."""
    if cache is None or filters.branchId is None:
        return None
    records = session.info.get("performance_records_cache", {}).get(employee_id)
    if records is None or not records.assignments:
        return None
    if any(row.get("branch_id") != filters.branchId for row in records.assignments):
        return None
    branch = str(filters.branchId)
    for event in records.assignment_changes:
        for field in ("before_values", "after_values"):
            values = event.get(field)
            if not isinstance(values, dict) or str(values.get("branchId")) != branch:
                return None
    broad = filters.model_copy(update={"branchId": None})
    return cache.get(performance_budget.metric_key(scope, employee_id, broad))


@performance_budget.bounded
async def derive_with_denominator(
    session: AsyncSession,
    scope: PerformanceScope,
    employee: dict,
    filters: PerformanceFilters,
) -> tuple[dict, dict[str, Decimal]]:
    cache: dict[tuple, tuple[dict, dict[str, Decimal]]] | None = session.info.get(
        "performance_metrics_cache"
    )
    key = performance_budget.metric_key(scope, employee["id"], filters)
    if cache is not None and key in cache:
        return cache[key]
    equivalent = _same_branch_cached(session, scope, employee["id"], filters, cache)
    if equivalent is not None:
        assert cache is not None
        cache[key] = equivalent
        return equivalent
    start = filters.startDate or employee["date_of_joining"]
    end = filters.endDate or datetime.now(DUBAI).date()
    if end > datetime.now(DUBAI).date() or start > end:
        raise ApiError(422, "PERFORMANCE_DATE_INVALID", "Date range is unavailable")
    performance_budget.charge(performance_budget.cost(employee, filters))
    records = await load(session, employee, filters)
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
    as_of = datetime.combine(end, time.max, tzinfo=DUBAI)
    for case in records.cases:
        case_id = case["id"]
        product = records.product_codes.get(case["product_type_id"])
        if filters.productCode is not None and filters.productCode != product:
            continue
        if filters.bankId is not None and case["bank_id"] != filters.bankId:
            continue
        timeline = _case_timeline(records, case, end)
        created_day = timeline["created"]
        if (
            case["created_by_employee_id"] == employee_id
            and _in_range(created_day, start, end)
            and (_allowed(scope, employee_id, case["created_at"], records, filters))
        ):
            counts["created"].add(case_id)
        for event, day, event_owner in timeline["events"]:
            status = event["status"]
            if status not in {"Booked", "Rejected"} or not _in_range(day, start, end):
                continue
            if event_owner != employee_id:
                continue
            if _allowed(scope, employee_id, event["occurred_at"], records, filters):
                counts["booked" if status == "Booked" else "rejected"].add(case_id)
        if created_day > end or (timeline["voided"] is not None and timeline["voided"] <= end):
            continue
        if timeline["owner"] != employee_id:
            continue
        if not _allowed(scope, employee_id, as_of, records, filters):
            continue
        status = timeline["status"]
        if status in {"Completed", "Rejected"}:
            continue
        in_progress.add(case_id)
        current_stage = timeline["stage"]
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
            scope, employee_id, result["completed_at"], records, filters
        ):
            continue
        value = result["cc_points"] if product == "CC" else result["pf_amount_aed"]
        if value is None:
            value = 0
        amount = Decimal(value)
        achieved[product] += amount
        counts["completed"].add(result["case_id"])
        assignment = assignment_at(
            records.assignments, records.assignment_changes, result["completed_at"]
        )
        if (
            assignment is not None
            and records.department_products.get(assignment["department_id"]) == product
            and (target_on(records.versions, assignment, day) is not None)
        ):
            target_achieved[product] += amount
    count_values = {kind: len(values) for kind, values in counts.items()}
    progress_count = len(in_progress)
    delay_weights = None
    if getattr(records, "compact_range", None) == (start, end):
        (
            count_values,
            progress_count,
            stages,
            achieved,
            target_achieved,
            delay_candidates,
            delay_weights,
        ) = _compact_activity(scope, employee_id, filters, records, end)
    progress = {}
    denominators: dict[str, Decimal] = {}
    for product in ("CC", "PF"):
        denominator = (
            _denominator(scope, employee_id, filters, records, start, end, product)
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
    delayed_count, delayed_state = await count_delayed(
        session, delay_candidates, end, weights=delay_weights
    )
    result = {
        "employeeId": str(employee_id),
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "createdCaseCount": count_values["created"],
        "bookedCaseCount": count_values["booked"],
        "completedCaseCount": count_values["completed"],
        "rejectedCaseCount": count_values["rejected"],
        "inProgressCaseCount": progress_count,
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


def _compact_activity(scope, employee_id, filters, records, end):
    counts = dict.fromkeys(("created", "booked", "completed", "rejected"), 0)
    progress_count = 0
    stages: dict[str, int] = {}
    achieved = {"CC": Decimal(0), "PF": Decimal(0)}
    target_achieved = {"CC": Decimal(0), "PF": Decimal(0)}
    candidates: list[tuple[UUID, date, int]] = []
    weights: list[int] = []
    # This proof covers every activity day and the as-of instant. Authorization
    # still runs for the current actor and every requested filter before use.
    if not _allowed(scope, employee_id, end, records, filters):
        return (
            counts,
            progress_count,
            stages,
            achieved,
            target_achieved,
            candidates,
            weights,
        )
    assignment = records.assignments[0]
    for row in records.compact_activity:
        product = row["product_code"]
        if filters.productCode is not None and product != filters.productCode:
            continue
        if filters.bankId is not None and row["bank_id"] != filters.bankId:
            continue
        kind, count = row["kind"], row["count"]
        if kind == "progress":
            progress_count += count
            if row["stage"] is not None:
                stages[row["stage"]] = stages.get(row["stage"], 0) + count
                if row["expected"] is not None:
                    candidates.append((employee_id, row["since"], row["expected"]))
                    weights.append(count)
        elif kind == "completed":
            if product not in achieved:
                continue
            counts[kind] += count
            achieved[product] += row["amount"]
            if (
                records.department_products.get(assignment["department_id"]) == product
                and target_on(records.versions, assignment, row["day"]) is not None
            ):
                target_achieved[product] += row["amount"]
        else:
            counts[kind] += count
    return (
        counts,
        progress_count,
        stages,
        achieved,
        target_achieved,
        candidates,
        weights,
    )


async def derive(
    session: AsyncSession,
    scope: PerformanceScope,
    employee: dict,
    filters: PerformanceFilters,
) -> dict:
    result, _ = await derive_with_denominator(session, scope, employee, filters)
    return result


def _denominator(scope, employee_id, filters, records, start, end, product):
    cache = None
    key = None
    stable = getattr(records, "compact_range", None) == (start, end)
    if stable:
        # Proven assignment/team scope is constant throughout this range.
        # Authorize the current actor/filter before reusing only target math.
        if not _allowed(scope, employee_id, end, records, filters):
            return Decimal(0)
        assignment = records.assignments[0]
        key = tuple(
            assignment[field] for field in ("branch_id", "department_id", "designation_id")
        ) + (start, end, product)
        cache = records.target_denominators
        if key in cache:
            return cache[key]
    value = target_denominator(
        start,
        end,
        records.assignments,
        records.versions,
        product,
        records.department_products,
        lambda day: stable or _allowed(scope, employee_id, day, records, filters),
    )
    if cache is not None:
        cache[key] = value
    return value
