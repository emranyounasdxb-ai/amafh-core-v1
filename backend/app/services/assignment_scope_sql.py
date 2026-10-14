"""Resolve proven timed assignment chains inside scope-filtered SQL queries."""

from sqlalchemy import Date, String, and_, case, cast, exists, func, literal, select
from sqlalchemy.dialects.postgresql import JSONB

from app.db.operations import audit_events
from app.db.organization import assignment_history
from app.services.assignment_activity import FIELDS

UUID_PATTERN = "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


def _tuple(values):
    normalized: list[object] = []
    checks = []
    for key in FIELDS.values():
        text = values[key].as_string()
        valid_uuid = text.op("~")(UUID_PATTERN)
        checks.append(and_(values.op("?")(key), (text.is_(None) | valid_uuid)))
        normalized.extend((key, case((valid_uuid, func.lower(text)), else_=None)))
    return func.jsonb_build_object(*normalized), and_(*checks)


def timed_assignment(employee_id, activity_day, occurred_at):
    """Return a four-field JSON object, or NULL for unproven same-day history.

    Each instant must have a complete acyclic chain of distinct transitions.
    Adjacent instants must connect. Neither audit UUID nor insertion order is
    treated as assignment order. The recursive walk cannot repeat a state, and
    a boundary is accepted only after visiting every distinct edge.
    """
    changed = audit_events.alias()
    raw = (
        select(
            changed.c.occurred_at.label("instant"),
            cast(changed.c.before_values, JSONB).label("before_values"),
            cast(changed.c.after_values, JSONB).label("after_values"),
        )
        .where(
            changed.c.action == "employee.assignment_changed",
            changed.c.entity_type == "employee",
            changed.c.entity_id == cast(employee_id, String),
            func.timezone("Asia/Dubai", changed.c.occurred_at).cast(Date) == activity_day,
        )
        .correlate_except(changed)
        .cte()
    )
    before, before_valid = _tuple(raw.c.before_values)
    after, after_valid = _tuple(raw.c.after_values)
    parsed = select(
        raw.c.instant,
        before.label("before_scope"),
        after.label("after_scope"),
        and_(before_valid, after_valid).label("valid"),
    ).cte()
    edges = (
        select(parsed.c.instant, parsed.c.before_scope, parsed.c.after_scope)
        .where(parsed.c.valid, parsed.c.before_scope != parsed.c.after_scope)
        .distinct()
        .cte()
    )
    predecessor = edges.alias()
    outgoing = edges.alias()
    roots = select(
        edges.c.instant,
        edges.c.before_scope.label("start_scope"),
        edges.c.after_scope.label("end_scope"),
        func.jsonb_build_array(edges.c.before_scope, edges.c.after_scope).label("visited"),
        literal(1).label("depth"),
    ).where(
        select(func.count())
        .select_from(outgoing)
        .where(
            outgoing.c.instant == edges.c.instant,
            outgoing.c.before_scope == edges.c.before_scope,
        )
        .scalar_subquery()
        == 1,
        ~exists(
            select(predecessor.c.instant).where(
                predecessor.c.instant == edges.c.instant,
                predecessor.c.after_scope == edges.c.before_scope,
            )
        ),
    )
    walk = roots.cte(recursive=True)
    successor = edges.alias()
    continuations = edges.alias()
    walk = walk.union_all(
        select(
            walk.c.instant,
            walk.c.start_scope,
            successor.c.after_scope,
            walk.c.visited.op("||")(func.jsonb_build_array(successor.c.after_scope)),
            walk.c.depth + 1,
        )
        .select_from(
            walk.join(
                successor,
                (successor.c.instant == walk.c.instant)
                & (successor.c.before_scope == walk.c.end_scope),
            )
        )
        .where(
            ~walk.c.visited.op("@>")(func.jsonb_build_array(successor.c.after_scope)),
            select(func.count())
            .select_from(continuations)
            .where(
                continuations.c.instant == successor.c.instant,
                continuations.c.before_scope == successor.c.before_scope,
            )
            .scalar_subquery()
            == 1,
        )
    )
    counted = edges.alias()
    complete = select(walk.c.instant, walk.c.start_scope, walk.c.end_scope, walk.c.visited).where(
        walk.c.depth
        == select(func.count())
        .select_from(counted)
        .where(counted.c.instant == walk.c.instant)
        .scalar_subquery()
    )
    nonempty = edges.alias()
    noops = (
        select(
            parsed.c.instant,
            parsed.c.before_scope.label("start_scope"),
            parsed.c.after_scope.label("end_scope"),
            func.jsonb_build_array(parsed.c.before_scope).label("visited"),
        )
        .where(
            parsed.c.valid,
            parsed.c.before_scope == parsed.c.after_scope,
            ~exists(select(nonempty.c.instant).where(nonempty.c.instant == parsed.c.instant)),
        )
        .distinct()
    )
    boundaries = complete.union_all(noops).cte()
    ordered = select(
        boundaries,
        func.lag(boundaries.c.end_scope)
        .over(order_by=boundaries.c.instant)
        .label("previous_scope"),
    ).cte()
    transitions = (
        select(parsed.c.instant, parsed.c.before_scope, parsed.c.after_scope).distinct().cte()
    )
    retained = assignment_history.alias()
    history_scope = func.jsonb_build_object(
        *[
            value
            for column, key in FIELDS.items()
            for value in (key, cast(retained.c[column], String))
        ]
    )
    closed = (
        retained.c.employee_id == employee_id,
        retained.c.assignment_end_date == activity_day,
    )
    closed_count = (
        select(func.count())
        .select_from(retained)
        .where(*closed)
        .correlate_except(retained)
        .scalar_subquery()
    )
    prior = (
        retained.c.employee_id == employee_id,
        retained.c.assignment_start_date < activity_day,
        retained.c.assignment_end_date.is_(None) | (retained.c.assignment_end_date >= activity_day),
    )
    first_scope = (
        select(boundaries.c.start_scope).order_by(boundaries.c.instant).limit(1).scalar_subquery()
    )
    last_scope = (
        select(boundaries.c.end_scope)
        .order_by(boundaries.c.instant.desc())
        .limit(1)
        .scalar_subquery()
    )
    final = (
        retained.c.employee_id == employee_id,
        retained.c.assignment_start_date <= activity_day,
        retained.c.assignment_end_date.is_(None) | (retained.c.assignment_end_date > activity_day),
    )
    safe = and_(
        ~exists(select(parsed.c.instant).where(parsed.c.valid.is_not(True))),
        select(func.count(func.distinct(raw.c.instant))).scalar_subquery()
        == select(func.count(func.distinct(boundaries.c.instant))).scalar_subquery(),
        ~exists(
            select(boundaries.c.instant).group_by(boundaries.c.instant).having(func.count() != 1)
        ),
        # Every retained close must have evidence, even if another close that
        # day has a valid audit. Otherwise that audit would hide a legacy gap.
        closed_count <= select(func.count()).select_from(transitions).scalar_subquery(),
        ~exists(
            select(retained.c.id)
            .where(
                *closed,
                ~exists(
                    select(parsed.c.instant)
                    .where(parsed.c.before_scope == history_scope)
                    .correlate_except(parsed)
                ),
            )
            .correlate_except(retained)
        ),
        select(func.count())
        .select_from(retained)
        .where(*prior)
        .correlate_except(retained)
        .scalar_subquery()
        <= 1,
        ~exists(
            select(retained.c.id)
            .where(*prior, history_scope != first_scope)
            .correlate_except(retained)
        ),
        select(func.count())
        .select_from(retained)
        .where(*final)
        .correlate_except(retained)
        .scalar_subquery()
        <= 1,
        ~exists(
            select(retained.c.id)
            .where(*final, history_scope != last_scope)
            .correlate_except(retained)
        ),
        # No-op evidence must name a state visited by the proven chain.
        ~exists(
            select(parsed.c.instant).where(
                parsed.c.before_scope == parsed.c.after_scope,
                ~exists(
                    select(boundaries.c.instant)
                    .where(
                        boundaries.c.instant == parsed.c.instant,
                        boundaries.c.visited.op("@>")(
                            func.jsonb_build_array(parsed.c.before_scope)
                        ),
                    )
                    .correlate_except(boundaries)
                ),
            )
        ),
        ~exists(
            select(ordered.c.instant).where(
                ordered.c.previous_scope.is_not(None),
                ordered.c.previous_scope != ordered.c.start_scope,
            )
        ),
    )
    later = (
        select(boundaries.c.start_scope)
        .where(boundaries.c.instant > occurred_at)
        .order_by(boundaries.c.instant)
        .limit(1)
        .scalar_subquery()
    )
    last = (
        select(boundaries.c.end_scope)
        .order_by(boundaries.c.instant.desc())
        .limit(1)
        .scalar_subquery()
    )
    return (
        select(cast(case((safe, func.coalesce(later, last)), else_=None), JSONB))
        .add_cte(raw, parsed, edges, walk, boundaries, ordered, transitions, nest_here=True)
        .scalar_subquery()
    )
