"""AMAFH Core private API application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.assets import router as assets_router
from app.api.attendance import router as attendance_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.branding import router as branding_router
from app.api.calls import router as calls_router
from app.api.cases import router as cases_router
from app.api.catalog import router as catalog_router
from app.api.customers import router as customers_router
from app.api.dashboard import router as dashboard_router
from app.api.finance import router as finance_router
from app.api.holiday_calendar import router as holiday_calendar_router
from app.api.hr_records import router as hr_records_router
from app.api.mailbox import router as mailbox_router
from app.api.master_lifecycle import router as master_lifecycle_router
from app.api.media import router as media_router
from app.api.my_wallet import router as my_wallet_router
from app.api.notifications import router as notifications_router
from app.api.office_timings import router as office_timings_router
from app.api.organization import router as organization_router
from app.api.performance import router as performance_router
from app.api.permissions import router as permissions_router
from app.api.reports import router as reports_router
from app.api.table_exports import router as table_exports_router
from app.api.targets import router as targets_router
from app.api.tasks import router as tasks_router
from app.api.team_lifecycle import router as team_lifecycle_router
from app.auth_throttle import AuthThrottle
from app.config import settings
from app.errors import install_error_handlers
from app.upload_limits import UploadBodyLimit


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    from app.calls.sync import start_worker as start_calls_worker
    from app.calls.sync import stop_worker as stop_calls_worker
    from app.mail.sync import start_worker, stop_worker

    await start_worker()
    try:
        await start_calls_worker()
        yield
    finally:
        await stop_calls_worker()
        await stop_worker()


def create_app() -> FastAPI:
    documentation = settings().environment != "production"
    return FastAPI(
        title="AMAFH Core API",
        version="0.1.0",
        lifespan=_lifespan,
        openapi_url="/openapi.json" if documentation else None,
        docs_url="/docs" if documentation else None,
        redoc_url="/redoc" if documentation else None,
    )


class SameOriginMutations:
    """Reject cross-origin mutations and mark responses private without buffering bodies."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope.get("method", "GET")
        path = scope.get("path", "")
        if path.startswith("/api/v1/") and method not in {"GET", "HEAD", "OPTIONS"}:
            origin = _header(scope, b"origin")
            if origin != str(settings().public_origin).rstrip("/"):
                response = JSONResponse(
                    {
                        "code": "ORIGIN_INVALID",
                        "message": "Invalid request origin",
                        "fieldErrors": {},
                    },
                    status_code=403,
                    headers={"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"},
                )
                await response(scope, receive, send)
                return

        async def send_headers(message):
            if message["type"] == "http.response.start":
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() not in {b"referrer-policy", b"cache-control"}
                ]
                headers.append((b"referrer-policy", b"no-referrer"))
                headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_headers)


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value.decode("latin-1")
    return None


app = create_app()
app.add_middleware(AuthThrottle)
app.add_middleware(UploadBodyLimit)
app.add_middleware(SameOriginMutations)
install_error_handlers(app)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(calls_router, prefix="/api/v1")
app.include_router(catalog_router, prefix="/api/v1")
app.include_router(cases_router, prefix="/api/v1")
app.include_router(customers_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(finance_router, prefix="/api/v1")
app.include_router(holiday_calendar_router, prefix="/api/v1")
app.include_router(hr_records_router, prefix="/api/v1")
app.include_router(mailbox_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(branding_router, prefix="/api/v1")
app.include_router(assets_router, prefix="/api/v1")
app.include_router(attendance_router, prefix="/api/v1")
app.include_router(organization_router, prefix="/api/v1")
app.include_router(office_timings_router, prefix="/api/v1")
app.include_router(performance_router, prefix="/api/v1")
app.include_router(permissions_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(master_lifecycle_router, prefix="/api/v1")
app.include_router(media_router, prefix="/api/v1")
app.include_router(my_wallet_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(team_lifecycle_router, prefix="/api/v1")
app.include_router(targets_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(table_exports_router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
