"""Resolve a financial activity's retained employee assignment on its business date."""

from sqlalchemy import Date, String, case, cast, func, or_, select
from sqlalchemy.dialects.postgresql import UUID

from app.db.operations import audit_events
from app.db.organization import assignment_history


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
    """Use a later same-day transfer's retained old scope for earlier timed facts."""
    changed = audit_events.alias(f"next_assignment_change_{field}")
    matching = (
        changed.c.action == "employee.assignment_changed",
        changed.c.entity_type == "employee",
        changed.c.entity_id == cast(employee_id, String),
        changed.c.occurred_at > occurred_at,
        func.timezone("Asia/Dubai", changed.c.occurred_at).cast(Date) == activity_day,
    )
    first_change = (
        select(changed.c.id)
        .where(*matching)
        .order_by(changed.c.occurred_at, changed.c.id)
        .limit(1)
        .correlate_except(changed)
        .scalar_subquery()
    )
    audit_field = {"branch_id": "branchId", "department_id": "departmentId"}[field]
    old_value = (
        select(cast(changed.c.before_values[audit_field].as_string(), UUID(as_uuid=True)))
        .where(changed.c.id == first_change)
        .correlate_except(changed)
        .scalar_subquery()
    )
    return case((first_change.is_not(None), old_value), else_=assignment_history.c[field])
