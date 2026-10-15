"""Attribute timed facts through immutable assignment-change audit boundaries."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.operations import audit_events
from app.db.query_sets import text_set
from app.services.performance_math import dubai_date

FIELDS = {
    "branch_id": "branchId",
    "department_id": "departmentId",
    "designation_id": "designationId",
    "reporting_manager_id": "reportingManagerId",
}


async def changes_for(session: AsyncSession, employee_ids: list[UUID]) -> dict[UUID, list[dict]]:
    changes: dict[UUID, list[dict]] = {}
    for row in (
        await session.execute(
            select(audit_events).where(
                audit_events.c.action == "employee.assignment_changed",
                audit_events.c.entity_type == "employee",
                text_set(audit_events.c.entity_id, [str(value) for value in employee_ids]),
            )
        )
    ).mappings():
        changes.setdefault(UUID(row["entity_id"]), []).append(dict(row))
    return changes


def _values(source: dict | None) -> tuple | None:
    if source is None or not all(key in source for key in FIELDS.values()):
        return None
    try:
        return tuple(
            UUID(source[key]) if source[key] is not None else None for key in FIELDS.values()
        )
    except ValueError, TypeError, AttributeError:
        return None


def _boundary(events: list[dict]) -> tuple[tuple, tuple] | None:
    edges = set()
    for event in events:
        before, after = _values(event["before_values"]), _values(event["after_values"])
        if before is None or after is None:
            return None
        edges.add((before, after))
    states = {state for edge in edges for state in edge}
    edges = {edge for edge in edges if edge[0] != edge[1]}
    if not edges:
        return (next(iter(states)), next(iter(states))) if len(states) == 1 else None
    starts = {a for a, _ in edges} - {b for _, b in edges}
    ends = {b for _, b in edges} - {a for a, _ in edges}
    if len(starts) != 1 or len(ends) != 1:
        return None
    start, end = next(iter(starts)), next(iter(ends))
    cursor, visited = start, set()
    while cursor != end:
        options = {edge for edge in edges if edge[0] == cursor}
        if len(options) != 1:
            return None
        edge = next(iter(options))
        if edge in visited:
            return None
        visited.add(edge)
        cursor = edge[1]
    reached = {state for edge in visited for state in edge}
    return (start, end) if visited == edges and states <= reached else None


def assignment_at(rows: list[dict], changes: list[dict], when: datetime) -> dict | None:
    day = dubai_date(when)
    grouped: dict[datetime, list[dict]] = {}
    for event in changes:
        if dubai_date(event["occurred_at"]) == day:
            grouped.setdefault(event["occurred_at"], []).append(event)
    boundaries: list[tuple[datetime, tuple, tuple]] = []
    for instant, events in sorted(grouped.items()):
        boundary = _boundary(events)
        if boundary is None or (boundaries and boundaries[-1][2] != boundary[0]):
            return None
        boundaries.append((instant, *boundary))
    if boundaries:
        transitions = {
            (event["occurred_at"], _values(event["before_values"]), _values(event["after_values"]))
            for events in grouped.values()
            for event in events
        }
        closed = [row for row in rows if row["assignment_end_date"] == day]

        def state(row):
            return tuple(row.get(column) for column in FIELDS)

        if len(closed) > len(transitions) or any(
            state(row) not in {edge[1] for edge in transitions} for row in closed
        ):
            return None
        prior = [
            row
            for row in rows
            if row["assignment_start_date"] < day
            and (row["assignment_end_date"] is None or row["assignment_end_date"] >= day)
        ]
        final = [
            row
            for row in rows
            if row["assignment_start_date"] <= day
            and (row["assignment_end_date"] is None or row["assignment_end_date"] > day)
        ]
        if (
            len(prior) > 1
            or len(final) > 1
            or any(state(row) != boundaries[0][1] for row in prior)
            or any(state(row) != boundaries[-1][2] for row in final)
        ):
            return None
        later = next((boundary for boundary in boundaries if boundary[0] > when), None)
        values = later[1] if later else boundaries[-1][2]
        return {
            "assignment_start_date": day,
            "assignment_end_date": None,
            **dict(zip(FIELDS, values, strict=True)),
        }
    # An unproven legacy close has no trustworthy sub-day boundary. Fail closed
    # on that day rather than attributing all its activity to the incoming scope.
    if any(row["assignment_end_date"] == day for row in rows):
        return None
    matches = [
        row
        for row in rows
        if row["assignment_start_date"] <= day
        and (row["assignment_end_date"] is None or day < row["assignment_end_date"])
    ]
    return matches[0] if len(matches) == 1 else None
