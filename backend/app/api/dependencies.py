"""Request-local authenticated actor and CSRF enforcement."""

from typing import Annotated

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.errors import ApiError
from app.policies import Actor
from app.services import auth

Db = Annotated[AsyncSession, Depends(get_session)]


async def current_actor(
    request: Request, db: Db, amafh_session: str | None = Cookie(default=None)
) -> Actor:
    # A table export invokes existing GET routes with the already authenticated actor.
    # Only the server can attach this object to an internal ASGI request scope.
    export_actor = request.scope.get("state", {}).get("_table_export_actor")
    if isinstance(export_actor, Actor):
        return export_actor
    return await auth.resolve(db, amafh_session)


ActorDep = Annotated[Actor, Depends(current_actor)]


async def csrf_actor(actor: ActorDep, x_csrf_token: str | None = Header(default=None)) -> Actor:
    if not auth.csrf_matches(actor, x_csrf_token):
        raise ApiError(403, "CSRF_INVALID", "Invalid form token")
    return actor


CsrfActor = Annotated[Actor, Depends(csrf_actor)]
