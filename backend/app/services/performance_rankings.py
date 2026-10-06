"""Deterministic Target rankings and Owner-only immutable final-tie decisions."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.operations import targets
from app.db.organization import (
    assignment_history,
    employees,
    team_leader_history,
    team_memberships,
)
from app.db.performance import ranking_confirmations
from app.errors import ApiError
from app.policies import Actor
from app.schemas.performance import PerformanceFilters
from app.services.department_products import department_products
from app.services.performance_math import DUBAI, assignment_on, target_on
from app.services.performance_metrics import derive
from app.services.performance_scope import MANAGEMENT_ROLES, resolve, visible_employee_ids
from app.services.public_row_sort import sort_rows


async def _candidate_count(
    session: AsyncSession, actor: Actor, filters: PerformanceFilters, *, finance_report: bool
) -> int:
    """Count the ranking's target-eligible population without deriving Case metrics."""
    allowed_roles = MANAGEMENT_ROLES | {"Sales Manager", "Team Leader", "Sales Executive"}
    if actor.designation not in allowed_roles and not (
        finance_report and actor.designation == "Finance"
    ):
        raise ApiError(403, "FORBIDDEN", "Access denied")
    if filters.startDate is None or filters.endDate is None or filters.productCode is None:
        raise ApiError(422, "RANKING_CONTEXT_REQUIRED", "Period and Product are required")
    if filters.startDate > filters.endDate or filters.endDate > datetime.now(DUBAI).date():
        raise ApiError(422, "PERFORMANCE_DATE_INVALID", "Date range is unavailable")
    scope = await resolve(session, actor, filters, finance_report=finance_report)
    if actor.designation == "Sales Manager" and (
        filters.branchId != actor.branch_id or filters.departmentId != actor.department_id
    ):
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if actor.designation == "Team Leader" and filters.teamId != scope.team_id:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    ids = await visible_employee_ids(session, scope)
    if not ids:
        return 0
    employee_rows = (
        (await session.execute(select(employees).where(employees.c.id.in_(ids)))).mappings().all()
    )
    histories: dict[UUID, list[dict]] = {employee_id: [] for employee_id in ids}
    for row in (
        await session.execute(
            select(assignment_history).where(assignment_history.c.employee_id.in_(ids))
        )
    ).mappings():
        histories[row["employee_id"]].append(dict(row))
    memberships: dict[UUID, list[dict]] = {employee_id: [] for employee_id in ids}
    for row in (
        await session.execute(
            select(team_memberships).where(team_memberships.c.employee_id.in_(ids))
        )
    ).mappings():
        memberships[row["employee_id"]].append(dict(row))
    leaderships: dict[UUID, list[dict]] = {employee_id: [] for employee_id in ids}
    for row in (
        await session.execute(
            select(team_leader_history).where(team_leader_history.c.leader_employee_id.in_(ids))
        )
    ).mappings():
        leaderships[row["leader_employee_id"]].append(dict(row))
    versions = [dict(row) for row in (await session.execute(select(targets))).mappings()]
    products = await department_products(session)
    count = 0
    for employee in employee_rows:
        employee_id = employee["id"]
        assignments = histories[employee_id] or [
            {
                "id": employee_id,
                "branch_id": employee["branch_id"],
                "department_id": employee["department_id"],
                "designation_id": employee["designation_id"],
                "assignment_start_date": employee["date_of_joining"],
                "assignment_end_date": None,
            }
        ]
        assignment = assignment_on(assignments, filters.endDate)
        if assignment is None or not scope.activity_allowed(
            employee_id,
            filters.endDate,
            assignments,
            memberships[employee_id],
            leaderships[employee_id],
            filters,
        ):
            continue
        if products.get(assignment["department_id"]) != filters.productCode:
            continue
        target = target_on(versions, assignment, filters.endDate)
        if target is None:
            continue
        value = (
            target["target_points"] if filters.productCode == "CC" else target["target_amount_aed"]
        )
        if value is not None:
            count += 1
    return count


def _context(filters: PerformanceFilters) -> tuple[str, dict]:
    values = filters.model_dump(mode="json", exclude_none=True)
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest(), values


async def _ranked(
    session: AsyncSession,
    actor: Actor,
    filters: PerformanceFilters,
    *,
    finance_report: bool = False,
) -> tuple[list[dict], list[str]]:
    allowed_roles = MANAGEMENT_ROLES | {"Sales Manager", "Team Leader", "Sales Executive"}
    if actor.designation not in allowed_roles and not (
        finance_report and actor.designation == "Finance"
    ):
        raise ApiError(403, "FORBIDDEN", "Access denied")
    if filters.startDate is None or filters.endDate is None or filters.productCode is None:
        raise ApiError(422, "RANKING_CONTEXT_REQUIRED", "Period and Product are required")
    scope = await resolve(session, actor, filters, finance_report=finance_report)
    if actor.designation == "Sales Manager" and (
        filters.branchId != actor.branch_id or filters.departmentId != actor.department_id
    ):
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if actor.designation == "Team Leader" and filters.teamId != scope.team_id:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    ids = await visible_employee_ids(session, scope)
    rows = (
        (
            await session.execute(
                select(employees)
                .where(employees.c.id.in_(ids))
                .order_by(
                    employees.c.id,
                )
            )
        )
        .mappings()
        .all()
    )
    ranked = []
    for employee in rows:
        metrics = await derive(session, scope, dict(employee), filters)
        progress = metrics["targetProgress"][filters.productCode]
        if progress["state"] != "Configured" or not progress["activeOnEndDate"]:
            continue
        percentage = Decimal(progress["achievementPercentage"])
        achieved = Decimal(progress["achieved"])
        ranked.append(
            {
                "employeeId": str(employee["id"]),
                "employeeName": employee["full_name"],
                "achievementPercentage": str(percentage),
                "completedCaseCount": metrics["completedCaseCount"],
                "achievedValue": str(achieved),
                "_sort": (percentage, metrics["completedCaseCount"], achieved),
            }
        )
    ranked.sort(
        key=lambda item: (
            -item["_sort"][0],
            -item["_sort"][1],
            -item["_sort"][2],
            item["employeeId"],
        )
    )
    for position, item in enumerate(ranked, 1):
        item["rank"] = position
    tied = (
        [item["employeeId"] for item in ranked if item["_sort"] == ranked[0]["_sort"]]
        if ranked
        else []
    )
    for item in ranked:
        item.pop("_sort")
    return ranked, tied


async def read(
    session: AsyncSession,
    actor: Actor,
    filters: PerformanceFilters,
    *,
    page: int,
    page_size: int,
    finance_report: bool = False,
    max_rows: int | None = None,
    sort: str | None = None,
    direction: str = "asc",
) -> dict:
    if sort not in {
        None,
        "rank",
        "employeeId",
        "employeeName",
        "achievementPercentage",
        "completedCaseCount",
        "achievedValue",
    } or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    if max_rows is not None:
        count = await _candidate_count(session, actor, filters, finance_report=finance_report)
        if count > max_rows:
            return {
                "items": [],
                "total": count,
                "page": page,
                "pageSize": page_size,
                "winnerEmployeeId": None,
                "decisionState": "Export limit exceeded",
            }
    ranked, tied = await _ranked(session, actor, filters, finance_report=finance_report)
    key, _ = _context(filters)
    confirmed = (
        (
            await session.execute(
                select(ranking_confirmations).where(
                    ranking_confirmations.c.context_key == key,
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if confirmed is not None and str(confirmed["selected_employee_id"]) not in {
        item["employeeId"] for item in ranked
    }:
        confirmed = None
    selected = str(confirmed["selected_employee_id"]) if confirmed is not None else None
    winner = selected or (ranked[0]["employeeId"] if len(tied) == 1 else None)
    displayed = sort_rows(ranked, sort, direction) if sort is not None else ranked
    return {
        "items": displayed[(page - 1) * page_size : page * page_size],
        "total": len(ranked),
        "page": page,
        "pageSize": page_size,
        "winnerEmployeeId": winner,
        "decisionState": "No eligible employees"
        if not ranked
        else (
            "Confirmed"
            if confirmed is not None
            else ("Owner decision pending" if len(tied) > 1 else "Automatic")
        ),
        "tiedCandidateIds": tied if len(tied) > 1 else [],
        "confirmedByEmployeeId": str(confirmed["confirmed_by_employee_id"])
        if confirmed is not None
        else None,
        "confirmedAt": confirmed["confirmed_at"].isoformat() if confirmed is not None else None,
    }


async def confirm(
    session: AsyncSession,
    actor: Actor,
    filters: PerformanceFilters,
    selected_employee_id: UUID,
) -> dict:
    if actor.designation != "Owner":
        raise ApiError(403, "FORBIDDEN", "Access denied")
    key, _ = _context(filters)
    try:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {
                "key": "ranking:" + key,
            },
        )
        prior = (
            (
                await session.execute(
                    select(ranking_confirmations).where(
                        ranking_confirmations.c.context_key == key,
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        if prior is not None:
            if prior["selected_employee_id"] != selected_employee_id:
                raise ApiError(409, "RANKING_ALREADY_CONFIRMED", "Winner is already confirmed")
            await session.rollback()
            return {
                "winnerEmployeeId": str(selected_employee_id),
                "decisionState": "Confirmed",
                "confirmedAt": prior["confirmed_at"].isoformat(),
            }
        ranked, tied = await _ranked(session, actor, filters)
        if len(tied) < 2 or str(selected_employee_id) not in tied:
            raise ApiError(409, "RANKING_SELECTION_INVALID", "No eligible final tie for selection")
        assert filters.startDate is not None and filters.endDate is not None
        now = datetime.now(DUBAI)
        await session.execute(
            ranking_confirmations.insert().values(
                id=uuid4(),
                context_key=key,
                period_start=filters.startDate,
                period_end=filters.endDate,
                branch_id=filters.branchId,
                department_id=filters.departmentId,
                team_id=filters.teamId,
                designation_id=filters.designationId,
                product_code=filters.productCode,
                eligible_candidate_ids=json.dumps(tied),
                selected_employee_id=selected_employee_id,
                confirmed_by_employee_id=actor.employee_id,
                confirmed_at=now,
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="ranking.winner_confirmed",
            module="performance",
            entity_type="ranking_confirmation",
            after={
                "contextKey": key,
                "periodStart": filters.startDate.isoformat(),
                "periodEnd": filters.endDate.isoformat(),
                "candidateIds": tied,
                "selectedEmployeeId": str(selected_employee_id),
                "confirmedAt": now.isoformat(),
            },
        )
        await session.commit()
        return {
            "winnerEmployeeId": str(selected_employee_id),
            "decisionState": "Confirmed",
            "confirmedAt": now.isoformat(),
        }
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(409, "RANKING_CONFLICT", "Ranking confirmation conflicts") from exc
    except Exception:
        await session.rollback()
        raise
