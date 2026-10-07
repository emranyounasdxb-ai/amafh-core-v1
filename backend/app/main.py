"""AMAFH Core private API application."""

from fastapi import FastAPI, Request

from app.api.assets import router as assets_router
from app.api.attendance import router as attendance_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.branding import router as branding_router
from app.api.cases import router as cases_router
from app.api.catalog import router as catalog_router
from app.api.customers import router as customers_router
from app.api.dashboard import router as dashboard_router
from app.api.finance import router as finance_router
from app.api.holiday_calendar import router as holiday_calendar_router
from app.api.hr_records import router as hr_records_router
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


def create_app() -> FastAPI:
    documentation = settings().environment != "production"
    return FastAPI(
        title="AMAFH Core API",
        version="0.1.0",
        openapi_url="/openapi.json" if documentation else None,
        docs_url="/docs" if documentation else None,
        redoc_url="/redoc" if documentation else None,
    )


app = create_app()
app.add_middleware(AuthThrottle)
app.add_middleware(UploadBodyLimit)
install_error_handlers(app)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(catalog_router, prefix="/api/v1")
app.include_router(cases_router, prefix="/api/v1")
app.include_router(customers_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(finance_router, prefix="/api/v1")
app.include_router(holiday_calendar_router, prefix="/api/v1")
app.include_router(hr_records_router, prefix="/api/v1")
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


@app.middleware("http")
async def same_origin_mutations(request: Request, call_next):
    if request.url.path.startswith("/api/v1/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin != str(settings().public_origin).rstrip("/"):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                {"code": "ORIGIN_INVALID", "message": "Invalid request origin", "fieldErrors": {}},
                status_code=403,
            )
    response = await call_next(request)
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
