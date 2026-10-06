"""Scoped central report catalog, pages, and secure exports."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.dependencies import ActorDep, Db
from app.errors import ApiError
from app.schemas.reports import ReportCatalogItem, ReportFilters, ReportKind, ReportPage
from app.services import report_choices, report_exports, reports
from app.services.report_catalog import CATALOG, available

router = APIRouter(tags=["reports"])
Filters = Annotated[ReportFilters, Depends()]


def _validated_query(request: Request, *, paged: bool) -> None:
    allowed = set(ReportFilters.model_fields)
    if paged:
        allowed.update({"page", "pageSize", "sort", "direction"})
    if set(request.query_params) - allowed or any(
        len(request.query_params.getlist(key)) > 1 for key in request.query_params
    ):
        raise ApiError(422, "REPORT_FILTER_UNSUPPORTED", "Unsupported or repeated report filter")


@router.get("/reports/catalog", response_model=list[ReportCatalogItem])
async def catalog(actor: ActorDep):
    return [
        {
            "report": name,
            "title": definition[0],
            "columns": [{"key": key, "heading": heading} for key, heading in definition[2]],
            "filters": sorted(definition[3]),
        }
        for name, definition in CATALOG.items()
        if available(actor, name)
    ]


@router.get("/reports/choices/teams")
async def team_choices(
    actor: ActorDep,
    db: Db,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
):
    return await report_choices.team_choices(db, actor, page, pageSize)


@router.get("/reports/{kind}", response_model=ReportPage)
async def report_page(
    kind: ReportKind,
    db: Db,
    actor: ActorDep,
    filters: Filters,
    request: Request,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    sort: str | None = None,
    direction: Literal["asc", "desc"] = "asc",
):
    _validated_query(request, paged=True)
    return await reports.read(
        db, actor, kind, filters, page=page, page_size=pageSize, sort=sort, direction=direction
    )


@router.get("/reports/{kind}/exports/{format}")
async def report_export(
    kind: ReportKind,
    format: Literal["csv", "pdf"],
    db: Db,
    actor: ActorDep,
    filters: Filters,
    request: Request,
):
    _validated_query(request, paged=False)
    data, media, filename = await report_exports.export(db, actor, kind, filters, format)
    return Response(
        content=data,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
