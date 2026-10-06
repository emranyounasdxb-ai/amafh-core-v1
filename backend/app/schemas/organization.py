"""Phase 1 organization and employee input contracts."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.normalization import display_name, identifier, nationality


class NamedCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return display_name(value)


class NamedUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=150)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return display_name(value)


OperatingCity = Literal["Dubai", "Abu Dhabi"]


class BranchUpdate(NamedUpdate):
    businessUnitId: UUID | None = None
    operatingCity: OperatingCity | None = None


class BranchCreate(NamedCreate):
    businessUnitId: UUID | None = None
    operatingCity: OperatingCity | None = None


class DepartmentCreate(NamedCreate):
    branchId: UUID
    productTypeId: UUID | None = None


class DepartmentUpdate(NamedUpdate):
    productTypeId: UUID | None = None


class EmployeeCreate(BaseModel):
    companyEmployeeCode: str = Field(min_length=1, max_length=80)
    fullName: str = Field(min_length=1, max_length=200)
    mobile: str = Field(min_length=1, max_length=40)
    personalEmail: EmailStr
    nationality: str = Field(min_length=2, max_length=2)
    gender: str
    maritalStatus: str
    dateOfJoining: date
    passportNumber: str = Field(min_length=1, max_length=100)
    emiratesIdNumber: str | None = None
    designationId: UUID
    branchId: UUID | None = None
    departmentId: UUID | None = None
    reportingManagerId: UUID | None = None

    @field_validator("companyEmployeeCode", "passportNumber", "emiratesIdNumber", mode="before")
    @classmethod
    def clean_identifier(cls, value: str | None) -> str | None:
        return identifier(value) if value is not None else None

    @field_validator("fullName", "mobile", mode="before")
    @classmethod
    def clean_display(cls, value: str) -> str:
        return display_name(value)

    @field_validator("nationality", mode="before")
    @classmethod
    def valid_nationality(cls, value: str) -> str:
        return nationality(value)


class EmployeeProfileUpdate(BaseModel):
    fullName: str | None = Field(default=None, min_length=1, max_length=200)
    mobile: str | None = Field(default=None, min_length=1, max_length=40)
    personalEmail: EmailStr | None = None
    nationality: str | None = Field(default=None, min_length=2, max_length=2)
    gender: str | None = None
    maritalStatus: str | None = None
    passportNumber: str | None = Field(default=None, min_length=1, max_length=100)
    emiratesIdNumber: str | None = None

    @field_validator("passportNumber", "emiratesIdNumber", mode="before")
    @classmethod
    def clean_identifier(cls, value: str | None) -> str | None:
        return identifier(value) if value is not None else None

    @field_validator("fullName", "mobile", mode="before")
    @classmethod
    def clean_display(cls, value: str | None) -> str | None:
        return display_name(value) if value is not None else None

    @field_validator("nationality", mode="before")
    @classmethod
    def valid_nationality(cls, value: str | None) -> str | None:
        return nationality(value) if value is not None else None


class AssignmentChange(BaseModel):
    branchId: UUID
    departmentId: UUID
    designationId: UUID
    reportingManagerId: UUID | None = None
    effectiveDate: date


class TeamCreate(NamedCreate):
    branchId: UUID
    departmentId: UUID
    leaderEmployeeId: UUID


class TeamMemberChange(BaseModel):
    employeeId: UUID
    startDate: date


class TeamLeaderReassignment(BaseModel):
    leaderEmployeeId: UUID
    effectiveDate: date


class UserCreate(BaseModel):
    employeeId: UUID
