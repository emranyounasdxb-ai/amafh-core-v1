"""Customer and Case lifecycle request contracts."""

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.normalization import display_name, identifier, nationality
from app.whole_numbers import WholeAmount


class CustomerInput(BaseModel):
    type: Literal["Individual", "Company"]
    emiratesId: str | None = Field(default=None, max_length=100)
    passportNumber: str | None = Field(default=None, max_length=100)
    fullName: str | None = Field(default=None, max_length=200)
    nationality: str | None = None
    employer: str | None = Field(default=None, max_length=200)
    companyName: str | None = Field(default=None, max_length=200)
    contactPerson: str | None = Field(default=None, max_length=200)
    tradeLicense: str | None = Field(default=None, max_length=100)
    mobile: str = Field(min_length=1, max_length=40)
    email: EmailStr

    @field_validator("nationality", mode="before")
    @classmethod
    def iso_nationality(cls, value: str | None) -> str | None:
        return nationality(value) if value is not None else None

    @field_validator("emiratesId", "passportNumber", "tradeLicense")
    @classmethod
    def canonical_id(cls, value: str | None) -> str | None:
        return identifier(value) if value is not None else None

    @field_validator("emiratesId")
    @classmethod
    def numeric_emirates_id(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[0-9 -]+", value):
            raise ValueError("Emirates ID may contain only digits, spaces and hyphens")
        return value

    @field_validator("fullName", "employer", "companyName", "contactPerson", "mobile")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return display_name(value) if value is not None else None

    @field_validator("mobile")
    @classmethod
    def numeric_mobile(cls, value: str) -> str:
        if not re.fullmatch(r"\+?[0-9][0-9 ()-]*", value):
            raise ValueError("Mobile number may contain only digits and dialing punctuation")
        return value

    @model_validator(mode="after")
    def required_by_type(self):
        fields = (
            ("emiratesId", "passportNumber", "fullName", "employer", "nationality")
            if self.type == "Individual"
            else ("companyName", "contactPerson", "tradeLicense")
        )
        if any(not getattr(self, field) for field in fields) or not self.mobile:
            raise ValueError("Mandatory Customer identity and contact fields are required")
        if self.type == "Company":
            self.nationality = None
        return self


class CaseCreate(BaseModel):
    confirmedInterest: Literal[True]
    customer: CustomerInput
    productTypeId: UUID
    bankId: UUID
    productVariantId: UUID | None = None
    requestedPfAmount: WholeAmount | None = Field(default=None, gt=0)
    ownerEmployeeId: UUID | None = None


class ApprovalInput(BaseModel):
    coordinatorEmployeeId: UUID


class BookingInput(BaseModel):
    bankCaseNumber: str = Field(min_length=1, max_length=120)

    @field_validator("bankCaseNumber")
    @classmethod
    def clean_number(cls, value: str) -> str:
        normalized = identifier(value)
        if not normalized:
            raise ValueError("Bank Case Number is required")
        return normalized


class OwnerCorrection(BaseModel):
    confirm: Literal[True]
    ownerEmployeeId: UUID | None = None
    bankCaseNumber: str | None = Field(default=None, max_length=120)
    currentStage: str | None = Field(default=None, max_length=150)
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("bankCaseNumber")
    @classmethod
    def clean_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = identifier(value)
        if not normalized:
            raise ValueError("Bank Case Number is required")
        return normalized

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        normalized = display_name(value)
        if not normalized:
            raise ValueError("Reason is required")
        return normalized

    @model_validator(mode="after")
    def one_change(self):
        if (
            sum(
                v is not None
                for v in (self.ownerEmployeeId, self.bankCaseNumber, self.currentStage)
            )
            != 1
        ):
            raise ValueError("Correct exactly one permitted Case field")
        return self


class ConfirmedAction(BaseModel):
    confirm: Literal[True]
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        normalized = display_name(value)
        if not normalized:
            raise ValueError("Reason is required")
        return normalized


class IdentityCorrection(BaseModel):
    confirm: Literal[True]
    emiratesId: str | None = Field(default=None, max_length=100)
    passportNumber: str | None = Field(default=None, max_length=100)
    tradeLicense: str | None = Field(default=None, max_length=100)
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("emiratesId", "passportNumber", "tradeLicense")
    @classmethod
    def clean_identity(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = identifier(value)
        if not normalized:
            raise ValueError("Identity value is required")
        return normalized

    @field_validator("emiratesId")
    @classmethod
    def numeric_emirates_id(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[0-9 -]+", value):
            raise ValueError("Emirates ID may contain only digits, spaces and hyphens")
        return value

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        normalized = display_name(value)
        if not normalized:
            raise ValueError("Reason is required")
        return normalized
