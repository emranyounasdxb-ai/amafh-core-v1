"""Phase 12C HR record command contracts."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.normalization import display_name, identifier, nationality
from app.whole_numbers import WholeAmount


def _text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = display_name(value)
    return cleaned or None


def _required(value: str) -> str:
    cleaned = display_name(value)
    if not cleaned:
        raise ValueError("A value is required")
    return cleaned


def _multiline(value: str | None) -> str | None:
    if value is None:
        return None
    lines = [" ".join(line.split()) for line in value.replace("\r\n", "\n").split("\n")]
    cleaned = "\n".join(lines).strip()
    return cleaned or None


class PackageInput(BaseModel):
    basicSalaryAed: WholeAmount = Field(gt=0)
    housingAllowanceAed: WholeAmount | None = Field(default=None, ge=0)
    transportAllowanceAed: WholeAmount | None = Field(default=None, ge=0)
    otherAllowanceLabel: str | None = Field(default=None, max_length=80)
    otherAllowanceAed: WholeAmount | None = Field(default=None, ge=0)
    effectiveDate: date
    changeReason: str = Field(min_length=1, max_length=500)

    @field_validator("otherAllowanceLabel", mode="before")
    @classmethod
    def clean_label(cls, value: str | None) -> str | None:
        return _text(value)

    @field_validator("changeReason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return _required(value)

    @model_validator(mode="after")
    def other_allowance_pair(self):
        if (self.otherAllowanceLabel is None) != (self.otherAllowanceAed is None):
            raise ValueError("Other allowance requires both a label and an amount")
        return self


class DocumentMetadata(BaseModel):
    documentNumber: str | None = Field(default=None, max_length=100)
    issueDate: date | None = None
    expiryDate: date | None = None
    issuingCountry: str | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("documentNumber", mode="before")
    @classmethod
    def clean_number(cls, value: str | None) -> str | None:
        return identifier(value) or None if value not in (None, "") else None

    @field_validator("issuingCountry", mode="before")
    @classmethod
    def clean_country(cls, value: str | None) -> str | None:
        return nationality(value) if value not in (None, "") else None

    @field_validator("notes", mode="before")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        return _multiline(value) if value not in (None, "") else None

    @field_validator("issueDate", "expiryDate", mode="before")
    @classmethod
    def blank_date(cls, value):
        return None if value == "" else value

    @model_validator(mode="after")
    def date_order(self):
        if self.issueDate and self.expiryDate and self.expiryDate < self.issueDate:
            raise ValueError("Expiry date cannot be before the issue date")
        return self


class ReasonInput(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return _required(value)


class DocumentRequirementUpdate(BaseModel):
    requiredAtOnboarding: bool


VisaType = Literal["Employment", "Investor/Partner", "Family-sponsored", "Other"]
VisaStatus = Literal[
    "Draft",
    "In Progress",
    "Active",
    "Renewal In Progress",
    "Cancellation In Progress",
    "Cancelled",
]
VISA_TEXT_FIELDS = ("visaNumber", "fileNumber", "workPermitNumber")


class VisaFields(BaseModel):
    visaNumber: str | None = Field(default=None, max_length=80)
    fileNumber: str | None = Field(default=None, max_length=80)
    issueDate: date | None = None
    expiryDate: date | None = None
    workPermitNumber: str | None = Field(default=None, max_length=80)
    workPermitExpiryDate: date | None = None
    medicalFitnessDate: date | None = None
    insuranceExpiryDate: date | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator(*VISA_TEXT_FIELDS, mode="before")
    @classmethod
    def clean_identifier(cls, value: str | None) -> str | None:
        return identifier(value) or None if value not in (None, "") else None

    @field_validator("notes", mode="before")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        return _multiline(value) if value not in (None, "") else None

    @field_validator(
        "issueDate",
        "expiryDate",
        "workPermitExpiryDate",
        "medicalFitnessDate",
        "insuranceExpiryDate",
        mode="before",
    )
    @classmethod
    def blank_date(cls, value):
        return None if value == "" else value


class VisaCreate(VisaFields):
    visaType: VisaType
    sponsor: str = Field(min_length=1, max_length=160)

    @field_validator("sponsor", mode="before")
    @classmethod
    def clean_sponsor(cls, value: str) -> str:
        return _required(value)


class VisaUpdate(VisaFields):
    visaType: VisaType | None = None
    sponsor: str | None = Field(default=None, min_length=1, max_length=160)

    @field_validator("sponsor", mode="before")
    @classmethod
    def clean_sponsor(cls, value: str | None) -> str | None:
        return _required(value) if value is not None else None


class VisaTransition(BaseModel):
    fromStatus: VisaStatus
    toStatus: VisaStatus
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("note", mode="before")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        return _multiline(value) if value not in (None, "") else None


class VisaDocumentAttach(BaseModel):
    documentId: str = Field(min_length=1, max_length=64)


HrDocumentType = Literal[
    "salary_letter",
    "employment_verification",
    "noc",
    "salary_transfer_letter",
    "experience_certificate",
]


class HrDocumentPrepare(BaseModel):
    documentType: HrDocumentType
    addressee: str | None = Field(default=None, max_length=200)
    purpose: str | None = Field(default=None, max_length=500)
    nocPurpose: Literal["Travel", "Bank", "Visa"] | None = None

    @field_validator("addressee", "purpose", mode="before")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return _text(value)

    @model_validator(mode="after")
    def required_context(self):
        if (self.documentType == "noc") != (self.nocPurpose is not None):
            raise ValueError("An NOC requires its purpose category; other documents do not")
        if self.documentType != "experience_certificate" and (
            self.addressee is None or self.purpose is None
        ):
            raise ValueError("Letters require an addressee and a purpose")
        return self


class CompanyProfileUpdate(BaseModel):
    companyLegalName: str | None = Field(default=None, max_length=200)
    companyAddress: str | None = Field(default=None, max_length=500)
    tradeLicenseNumber: str | None = Field(default=None, max_length=80)
    signatoryName: str | None = Field(default=None, max_length=200)
    signatoryDesignation: str | None = Field(default=None, max_length=120)

    @field_validator(
        "companyLegalName",
        "tradeLicenseNumber",
        "signatoryName",
        "signatoryDesignation",
        mode="before",
    )
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return _text(value)

    @field_validator("companyAddress", mode="before")
    @classmethod
    def clean_address(cls, value: str | None) -> str | None:
        return _multiline(value)


class TemplateDraft(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)

    @field_validator("title", mode="before")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return _required(value)

    @field_validator("body", mode="before")
    @classmethod
    def clean_body(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Expected text")
        lines = [line.rstrip() for line in value.replace("\r\n", "\n").split("\n")]
        cleaned = "\n".join(lines).strip()
        if not cleaned:
            raise ValueError("Template wording is required")
        return cleaned


class OffboardInput(BaseModel):
    lastWorkingDate: date


class LastWorkingDateRecord(ReasonInput):
    lastWorkingDate: date
