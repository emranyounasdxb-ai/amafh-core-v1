"""Current organization read model for the Owner and Managing Director."""

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import designations, employees, team_memberships, teams
from app.errors import ApiError
from app.policies import Actor
from app.services.organization import dubai_today


async def read(session: AsyncSession, actor: Actor) -> dict:
    if actor.designation not in {"Owner", "Managing Director"}:
        raise ApiError(403, "FORBIDDEN", "Access denied")

    statement = (
        select(
            employees.c.id,
            employees.c.full_name,
            designations.c.name.label("designation"),
            employees.c.reporting_manager_id,
            employees.c.avatar_file_id,
            teams.c.id.label("team_id"),
            teams.c.leader_employee_id.label("team_leader_id"),
        )
        .select_from(
            employees.join(designations, designations.c.id == employees.c.designation_id)
            .outerjoin(
                team_memberships,
                and_(
                    team_memberships.c.employee_id == employees.c.id,
                    team_memberships.c.end_date.is_(None),
                    team_memberships.c.start_date <= dubai_today(),
                ),
            )
            .outerjoin(
                teams,
                and_(
                    teams.c.id == team_memberships.c.team_id,
                    teams.c.active.is_(True),
                ),
            )
        )
        .where(employees.c.status == "Active")
        .order_by(designations.c.name, employees.c.full_name, employees.c.id)
    )
    return {
        "employees": [
            {
                "id": row["id"],
                "fullName": row["full_name"],
                "designation": row["designation"],
                "reportingManagerId": row["reporting_manager_id"],
                "avatarFileId": row["avatar_file_id"],
                "teamId": row["team_id"],
                "teamLeaderId": row["team_leader_id"],
            }
            for row in (await session.execute(statement)).mappings()
        ]
    }
