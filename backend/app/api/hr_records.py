"""Phase 12C HR record routes: packages, documents, visas, letters and certificates."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, File, Form, Header, Response, UploadFile

from app.api.dependencies import ActorDep, CsrfActor, Db
from app.schemas.hr_records import (
    CompanyProfileUpdate,
    DocumentRequirementUpdate,
    HrDocumentPrepare,
    HrDocumentType,
    PackageInput,
    ReasonInput,
    TemplateDraft,
    VisaCreate,
    VisaDocumentAttach,
    VisaTransition,
    VisaUpdate,
)
from app.services import (
    employee_documents,
    employee_packages,
    hr_document_settings,
    hr_documents,
    hr_overview,
    visa_records,
)
from app.services.hr_common import dubai_today

router = APIRouter(tags=["hr-records"])
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key")]
OptionalText = Annotated[str | None, Form()]


def _file(data: bytes, mime: str, filename: str) -> Response:
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.get("/hr/packages")
async def packages_overview(actor: ActorDep, db: Db):
    return await hr_overview.packages_overview(db, actor)


@router.get("/hr/documents")
async def documents_overview(actor: ActorDep, db: Db):
    return await hr_overview.documents_overview(db, actor)


@router.get("/hr/visa-records")
async def visa_overview(actor: ActorDep, db: Db):
    return await hr_overview.visa_overview(db, actor)


@router.get("/hr/hr-documents")
async def hr_documents_overview(
    actor: ActorDep, db: Db, category: Literal["letter", "certificate"] = "letter"
):
    return await hr_overview.hr_documents_overview(db, actor, category)


@router.get("/employees/{employee_id}/packages")
async def list_packages(employee_id: UUID, actor: ActorDep, db: Db):
    return await employee_packages.list_packages(db, actor, employee_id)


@router.get("/employees/{employee_id}/packages/applicable")
async def applicable_package(employee_id: UUID, actor: ActorDep, db: Db, on: date | None = None):
    return {
        "package": await employee_packages.applicable_package(
            db, actor, employee_id, on or dubai_today()
        )
    }


@router.post("/employees/{employee_id}/packages", status_code=201)
async def add_package(
    employee_id: UUID, item: PackageInput, actor: CsrfActor, db: Db, key: IdempotencyKey
):
    return await employee_packages.add_package(db, actor, employee_id, item, key)


@router.get("/employee-document-types")
async def list_document_types(actor: ActorDep, db: Db):
    return await employee_documents.list_types(db, actor)


@router.patch("/employee-document-types/{type_id}")
async def update_document_type(
    type_id: UUID, item: DocumentRequirementUpdate, actor: CsrfActor, db: Db
):
    return await employee_documents.update_requirement(db, actor, type_id, item)


@router.get("/employees/{employee_id}/documents")
async def list_documents(employee_id: UUID, actor: ActorDep, db: Db):
    return await employee_documents.list_documents(db, actor, employee_id)


@router.post("/employees/{employee_id}/documents", status_code=201)
async def upload_document(
    employee_id: UUID,
    actor: CsrfActor,
    db: Db,
    key: IdempotencyKey,
    file: Annotated[UploadFile, File()],
    documentTypeId: Annotated[UUID, Form()],
    documentNumber: OptionalText = None,
    issueDate: OptionalText = None,
    expiryDate: OptionalText = None,
    issuingCountry: OptionalText = None,
    notes: OptionalText = None,
):
    item = employee_documents.parse_metadata(
        {
            "documentNumber": documentNumber,
            "issueDate": issueDate,
            "expiryDate": expiryDate,
            "issuingCountry": issuingCountry,
            "notes": notes,
        }
    )
    return await employee_documents.upload_document(
        db, actor, employee_id, documentTypeId, item, file, key
    )


@router.post("/employee-documents/{series_id}/versions", status_code=201)
async def replace_document(
    series_id: UUID,
    actor: CsrfActor,
    db: Db,
    key: IdempotencyKey,
    file: Annotated[UploadFile, File()],
    replacesVersion: Annotated[int, Form()],
    documentNumber: OptionalText = None,
    issueDate: OptionalText = None,
    expiryDate: OptionalText = None,
    issuingCountry: OptionalText = None,
    notes: OptionalText = None,
):
    item = employee_documents.parse_metadata(
        {
            "documentNumber": documentNumber,
            "issueDate": issueDate,
            "expiryDate": expiryDate,
            "issuingCountry": issuingCountry,
            "notes": notes,
        }
    )
    return await employee_documents.replace_document(
        db, actor, series_id, replacesVersion, item, file, key
    )


@router.post("/employee-documents/{series_id}/withdraw", status_code=204)
async def withdraw_document(series_id: UUID, item: ReasonInput, actor: CsrfActor, db: Db):
    await employee_documents.withdraw_document(db, actor, series_id, item.reason)


@router.get("/employee-document-versions/{version_id}/file")
async def download_document(version_id: UUID, actor: ActorDep, db: Db):
    data, mime, filename = await employee_documents.download_version(db, actor, version_id)
    return _file(data, mime, filename)


@router.get("/employees/{employee_id}/visa-records")
async def list_visa_records(employee_id: UUID, actor: ActorDep, db: Db):
    return await visa_records.list_visa_records(db, actor, employee_id)


@router.post("/employees/{employee_id}/visa-records", status_code=201)
async def create_visa_record(employee_id: UUID, item: VisaCreate, actor: CsrfActor, db: Db):
    return await visa_records.create_visa_record(db, actor, employee_id, item)


@router.patch("/visa-records/{record_id}")
async def update_visa_record(record_id: UUID, item: VisaUpdate, actor: CsrfActor, db: Db):
    return await visa_records.update_visa_record(db, actor, record_id, item)


@router.post("/visa-records/{record_id}/transitions")
async def transition_visa_record(record_id: UUID, item: VisaTransition, actor: CsrfActor, db: Db):
    return await visa_records.transition_visa_record(db, actor, record_id, item)


@router.post("/visa-records/{record_id}/documents", status_code=201)
async def attach_visa_document(record_id: UUID, item: VisaDocumentAttach, actor: CsrfActor, db: Db):
    return await visa_records.attach_document(db, actor, record_id, item)


@router.post("/visa-records/{record_id}/documents/{link_id}/detach", status_code=204)
async def detach_visa_document(record_id: UUID, link_id: UUID, actor: CsrfActor, db: Db):
    await visa_records.detach_document(db, actor, record_id, link_id)


@router.get("/hr-document-settings")
async def read_hr_document_settings(actor: ActorDep, db: Db):
    return await hr_document_settings.read_settings(db, actor)


@router.put("/hr-document-settings/company")
async def update_company_profile(item: CompanyProfileUpdate, actor: CsrfActor, db: Db):
    return await hr_document_settings.update_company(db, actor, item)


@router.post("/hr-document-templates/{document_type}/drafts", status_code=201)
async def draft_template(
    document_type: HrDocumentType, item: TemplateDraft, actor: CsrfActor, db: Db
):
    return await hr_document_settings.draft_template(db, actor, document_type, item)


@router.post("/hr-document-templates/{template_id}/approve")
async def approve_template(template_id: UUID, actor: CsrfActor, db: Db):
    return await hr_document_settings.approve_template(db, actor, template_id)


@router.get("/employees/{employee_id}/hr-documents")
async def list_hr_documents(employee_id: UUID, actor: ActorDep, db: Db):
    return await hr_documents.list_documents(db, actor, employee_id)


@router.post("/employees/{employee_id}/hr-documents", status_code=201)
async def prepare_hr_document(
    employee_id: UUID, item: HrDocumentPrepare, actor: CsrfActor, db: Db, key: IdempotencyKey
):
    return await hr_documents.prepare(db, actor, employee_id, item, key)


@router.post("/hr-documents/{record_id}/issue")
async def issue_hr_document(record_id: UUID, actor: CsrfActor, db: Db):
    return await hr_documents.issue(db, actor, record_id)


@router.post("/hr-documents/{record_id}/approve")
async def approve_hr_document(record_id: UUID, actor: CsrfActor, db: Db):
    return await hr_documents.approve(db, actor, record_id)


@router.post("/hr-documents/{record_id}/cancel", status_code=204)
async def cancel_hr_document(record_id: UUID, item: ReasonInput, actor: CsrfActor, db: Db):
    await hr_documents.cancel(db, actor, record_id, item.reason)


@router.post("/hr-documents/{record_id}/void", status_code=204)
async def void_hr_document(record_id: UUID, item: ReasonInput, actor: CsrfActor, db: Db):
    await hr_documents.void(db, actor, record_id, item.reason)


@router.post("/hr-documents/{record_id}/reissue", status_code=201)
async def reissue_hr_document(record_id: UUID, actor: CsrfActor, db: Db, key: IdempotencyKey):
    return await hr_documents.reissue(db, actor, record_id, key)


@router.get("/hr-documents/{record_id}/preview")
async def preview_hr_document(record_id: UUID, actor: ActorDep, db: Db):
    data = await hr_documents.preview(db, actor, record_id)
    return _file(data, "application/pdf", "DRAFT-preview.pdf")


@router.get("/hr-documents/{record_id}/file")
async def download_hr_document(record_id: UUID, actor: ActorDep, db: Db):
    data, filename = await hr_documents.download(db, actor, record_id)
    return _file(data, "application/pdf", filename)
