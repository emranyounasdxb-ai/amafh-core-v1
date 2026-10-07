"""Authentication, sessions and manual password-link delivery boundary."""

from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.db.organization import employees, team_memberships, teams
from app.repositories import permissions as permission_rows
from app.schemas.auth import CurrentUser, LinkRequest, LoginRequest, PasswordChange
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])


async def team_context(db: Db, employee_id, designation: str):
    if designation == "Team Leader":
        return await db.scalar(
            select(teams.c.id).where(
                teams.c.leader_employee_id == employee_id, teams.c.active.is_(True)
            )
        )
    if designation == "Sales Executive":
        return await db.scalar(
            select(team_memberships.c.team_id)
            .join(teams, team_memberships.c.team_id == teams.c.id)
            .where(
                team_memberships.c.employee_id == employee_id,
                team_memberships.c.end_date.is_(None),
                teams.c.active.is_(True),
            )
        )
    return None


def public_user(row: dict, team_id, grants: frozenset[str], csrf: str | None = None) -> CurrentUser:
    return CurrentUser(
        employeeId=str(row["employee_id"]),
        displayName=row["full_name"],
        avatarFileId=str(row["avatar_file_id"]) if row["avatar_file_id"] else None,
        designation=row["designation"],
        branchId=str(row["branch_id"]) if row["branch_id"] else None,
        departmentId=str(row["department_id"]) if row["department_id"] else None,
        teamId=str(team_id) if team_id else None,
        permissions=sorted(grants),
        csrfToken=csrf,
    )


@router.post("/login", response_model=CurrentUser)
async def login(payload: LoginRequest, response: Response, db: Db):
    token, csrf, row = await auth.login(db, payload.email, payload.password)
    response.set_cookie(
        "amafh_session",
        token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/api/v1",
    )
    team_id = await team_context(db, row["employee_id"], row["designation"])
    grants = await permission_rows.actor_grants(db, row["designation"])
    return public_user(row, team_id, grants, csrf)


@router.get("/me")
async def me(actor: ActorDep, db: Db):
    team_id = await team_context(db, actor.employee_id, actor.designation)
    avatar_id = await db.scalar(
        select(employees.c.avatar_file_id).where(employees.c.id == actor.employee_id)
    )
    return {
        "employeeId": str(actor.employee_id),
        "displayName": actor.display_name,
        "avatarFileId": str(avatar_id) if avatar_id else None,
        "designation": actor.designation,
        "branchId": str(actor.branch_id) if actor.branch_id else None,
        "departmentId": str(actor.department_id) if actor.department_id else None,
        "teamId": str(team_id) if team_id else None,
        "permissions": sorted(actor.grants),
    }


@router.post("/csrf")
async def csrf(actor: CsrfActor, db: Db):
    return {"csrfToken": await auth.rotate_csrf(db, actor)}


@router.post("/logout", status_code=204)
async def logout(response: Response, actor: CsrfActor, db: Db):
    await auth.logout(db, actor)
    response.delete_cookie(
        "amafh_session", path="/api/v1", secure=True, httponly=True, samesite="lax"
    )


@router.post("/setup-links")
async def setup_link(payload: LinkRequest, actor: CsrfActor, db: Db):
    return {"link": await auth.generate_link(db, actor, payload.employeeId, "setup")}


@router.post("/reset-links")
async def reset_link(payload: LinkRequest, actor: CsrfActor, db: Db):
    return {"link": await auth.generate_link(db, actor, payload.employeeId, "reset")}


@router.post("/setup", status_code=204)
async def setup(payload: PasswordChange, db: Db):
    await auth.complete_link(db, payload.token, payload.password, "setup")


@router.post("/reset", status_code=204)
async def reset(payload: PasswordChange, db: Db):
    await auth.complete_link(db, payload.token, payload.password, "reset")
