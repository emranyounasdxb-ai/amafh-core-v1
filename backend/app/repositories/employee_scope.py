"""Shared current Employee read scope for details and notification navigation."""

from sqlalchemy import false, select

from app.db.organization import designations, employees, team_memberships, teams
from app.policies import EMPLOYEE_SCOPE, Actor


def employee_query(actor: Actor):
    query = select(*employees.c, designations.c.name.label("designation")).join(
        designations, employees.c.designation_id == designations.c.id
    )
    scope = EMPLOYEE_SCOPE.get(actor.designation, "none")
    if scope == "branch":
        query = query.where(employees.c.branch_id == actor.branch_id)
    elif scope == "department":
        query = query.where(
            employees.c.branch_id == actor.branch_id,
            employees.c.department_id == actor.department_id,
        )
    elif scope == "team":
        team_ids = select(teams.c.id).where(
            teams.c.leader_employee_id == actor.employee_id, teams.c.active.is_(True)
        )
        members = select(team_memberships.c.employee_id).where(
            team_memberships.c.team_id.in_(team_ids), team_memberships.c.end_date.is_(None)
        )
        query = query.where((employees.c.id == actor.employee_id) | employees.c.id.in_(members))
    elif scope == "own":
        query = query.where(employees.c.id == actor.employee_id)
    elif scope != "all":
        query = query.where(false())
    return query
