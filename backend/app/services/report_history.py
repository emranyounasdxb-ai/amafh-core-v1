"""Resolve a financial activity's retained employee assignment on its business date."""

from sqlalchemy import Date, String, case, cast, exists, func, or_, select
from sqlalchemy.dialects.postgresql import UUID

from app.db.operations import audit_events
from app.db.organization import assignment_history
from app.services.assignment_scope_sql import timed_assignment


def assignment_id_on(employee_id, activity_day):
    dated = assignment_history.alias("dated_assignment")
    return (
        select(dated.c.id)
        .where(
            dated.c.employee_id == employee_id,
            dated.c.assignment_start_date <= activity_day,
            or_(
                dated.c.assignment_end_date.is_(None),
                dated.c.assignment_end_date > activity_day,
            ),
        )
        .order_by(dated.c.assignment_start_date.desc(), dated.c.id.desc())
        .limit(1)
        .scalar_subquery()
    )


def scope_value_on(employee_id, activity_day, occurred_at, field: str):
    """Resolve timed scope before Finance authorization, totals and pagination."""
    changed = audit_events.alias(f"next_assignment_change_{field}")
    matching = (
        changed.c.action == "employee.assignment_changed",
        changed.c.entity_type == "employee",
        changed.c.entity_id == cast(employee_id, String),
        func.timezone("Asia/Dubai", changed.c.occurred_at).cast(Date) == activity_day,
    )
    audited = exists(select(changed.c.id).where(*matching).correlate_except(changed))
    audit_field = {"branch_id": "branchId", "department_id": "departmentId"}[field]
    timed_value = cast(
        timed_assignment(employee_id, activity_day, occurred_at)[audit_field].as_string(),
        UUID(as_uuid=True),
    )
    retained = assignment_history.alias()
    unproven_close = exists(
        select(retained.c.id)
        .where(
            retained.c.employee_id == employee_id, retained.c.assignment_end_date == activity_day
        )
        .correlate_except(retained)
    )
    population = (
        select(func.count())
        .select_from(retained)
        .where(
            retained.c.employee_id == employee_id,
            retained.c.assignment_start_date <= activity_day,
            or_(
                retained.c.assignment_end_date.is_(None),
                retained.c.assignment_end_date > activity_day,
            ),
        )
        .correlate_except(retained)
        .scalar_subquery()
    )
    dated = case(((population == 1) & ~unproven_close, assignment_history.c[field]), else_=None)
    return case((audited, timed_value), else_=dated)
