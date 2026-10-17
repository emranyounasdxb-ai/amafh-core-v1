"""Authenticated Calls routes. The four allowed roles are checked on every method."""

import contextlib
from uuid import UUID

from fastapi import APIRouter, Cookie, Request
from fastapi.responses import Response, StreamingResponse

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.audit import record
from app.calls import client as connector_client
from app.calls import stream as stream_mod
from app.calls.catalog import months as list_months
from app.calls.catalog import number_suggestions as suggest_numbers
from app.calls.catalog import search as search_catalog
from app.calls.catalog import status as catalog_status
from app.calls.policy import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    clean_month,
    clean_number_prefix,
    clean_page,
    clean_phone,
    require_calls,
)
from app.calls.stream import (
    acquire_slot,
    byte_stream,
    load_for_stream,
    open_upstream,
    release_slot,
    response_headers,
    upstream_headers,
)
from app.db.session import session_factory
from app.errors import ApiError
from app.schemas.calls import NumberSuggestionsBody, SearchBody
from app.services import auth

router = APIRouter(prefix="/calls", tags=["calls"])


@router.get("/months")
async def months(actor: ActorDep, db: Db):
    require_calls(actor)
    return await list_months(db)


@router.get("/status")
async def status(actor: ActorDep, db: Db):
    require_calls(actor)
    return await catalog_status(db)


@router.post("/search")
async def search(actor: CsrfActor, db: Db, body: SearchBody):
    require_calls(actor)
    month = clean_month(body.month)
    phone = clean_phone(body.customerNumber)
    page = clean_page(body.page, default=1)
    page_size = clean_page(body.pageSize, default=DEFAULT_PAGE_SIZE)
    if page < 1:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Choose a valid page",
            {"page": ["Choose a valid page."]},
        )
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Choose a valid page size",
            {"pageSize": ["Choose a page size up to 50."]},
        )
    result = await search_catalog(db, month, phone, page, page_size)
    await record(
        db,
        actor=actor.employee_id,
        action="calls.search",
        module="calls",
        context={"month": month, "total": result["total"]},
    )
    await db.commit()
    return result


@router.post("/number-suggestions")
async def number_suggestions(actor: CsrfActor, db: Db, body: NumberSuggestionsBody):
    require_calls(actor)
    return await suggest_numbers(db, clean_month(body.month), clean_number_prefix(body.prefix))


async def _transfer(
    recording_id: UUID, request: Request, raw_session: str | None, *, attachment: bool
):
    async with session_factory()() as session:
        actor = await auth.resolve(session, raw_session)
        require_calls(actor)
        if request.method == "GET":
            await record(
                session,
                actor=actor.employee_id,
                action="calls.download_requested" if attachment else "calls.play",
                module="calls",
                entity_type="call_recording",
                entity_id=recording_id,
            )
            await session.commit()
        else:
            await session.rollback()
        user_id = actor.account_id
    if not connector_client.transfer_configured():
        raise ApiError(503, "CALLS_DISABLED", "Calls is not available")
    row = await load_for_stream(recording_id)
    await acquire_slot(user_id)
    upstream = None
    upstream_client = None
    handed = False
    try:
        headers = upstream_headers(request.headers.get("range"), request.headers.get("if-range"))
        upstream_client, upstream = await open_upstream(row, headers, request.method)
        if not await stream_mod.still_allowed(raw_session):
            raise ApiError(401, "UNAUTHENTICATED", "Sign in to continue")
        safe = response_headers(upstream, row["filename"], attachment=attachment)
        status_code = upstream.status_code
        if request.method == "HEAD" or status_code == 416:
            return Response(status_code=status_code, headers=safe)
        response = StreamingResponse(
            byte_stream(upstream, upstream_client, user_id, raw_session),
            status_code=status_code,
            headers=safe,
        )
        handed = True
        upstream = None
        upstream_client = None
        return response
    finally:
        if not handed:
            if upstream is not None:
                with contextlib.suppress(Exception):
                    await upstream.aclose()
            if upstream_client is not None:
                with contextlib.suppress(Exception):
                    await upstream_client.aclose()
            await release_slot(user_id)


@router.api_route("/recordings/{recording_id}/stream", methods=["GET", "HEAD"])
async def stream_recording(
    recording_id: UUID,
    request: Request,
    amafh_session: str | None = Cookie(default=None),
):
    return await _transfer(recording_id, request, amafh_session, attachment=False)


@router.api_route("/recordings/{recording_id}/download", methods=["GET", "HEAD"])
async def download_recording(
    recording_id: UUID,
    request: Request,
    amafh_session: str | None = Cookie(default=None),
):
    return await _transfer(recording_id, request, amafh_session, attachment=True)
