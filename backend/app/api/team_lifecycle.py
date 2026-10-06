"""Audited Team lifecycle mutations for Owner and MD."""

from uuid import UUID

from fastapi import APIRouter

from app.api.dependencies import CsrfActor, Db
from app.schemas.organization import NamedUpdate, TeamLeaderReassignment
from app.services import team_lifecycle

router = APIRouter(tags=["teams"])


@router.patch("/teams/{team_id}", status_code=204)
async def rename_team(team_id: UUID, item: NamedUpdate, actor: CsrfActor, db: Db):
    await team_lifecycle.rename(db, actor, team_id, item.name)


@router.post("/teams/{team_id}/deactivate", status_code=204)
async def deactivate_team(team_id: UUID, actor: CsrfActor, db: Db):
    await team_lifecycle.deactivate(db, actor, team_id)


@router.post("/teams/{team_id}/reassign-leader", status_code=204)
async def reassign_team_leader(
    team_id: UUID, item: TeamLeaderReassignment, actor: CsrfActor, db: Db
):
    await team_lifecycle.reassign_leader(
        db, actor, team_id, item.leaderEmployeeId, item.effectiveDate
    )
