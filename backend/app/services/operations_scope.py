"""Shared locked Branch scope for Attendance and Asset operations."""

from uuid import UUID

from app.errors import ApiError
from app.policies import Actor, require


def branch_scope(actor: Actor, permission: str, requested: UUID | None = None) -> UUID | None:
    require(actor, permission)
    if actor.designation == "Admin Staff":
        if actor.branch_id is None or (requested is not None and requested != actor.branch_id):
            raise ApiError(403, "FORBIDDEN", "Branch unavailable")
        return actor.branch_id
    return requested


def required_branch(actor: Actor, permission: str, requested: UUID | None) -> UUID:
    branch = branch_scope(actor, permission, requested)
    if branch is None:
        raise ApiError(422, "BRANCH_REQUIRED", "Select a Branch")
    return branch
