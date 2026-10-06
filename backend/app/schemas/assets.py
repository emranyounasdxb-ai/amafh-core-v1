"""Typed Asset inventory, command, history, and report contracts."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.normalization import display_name, identifier

Category = Literal["Mobile Phone", "SIM Card", "PC", "Laptop", "Other"]
AssetStatus = Literal["Available", "Issued", "Needs Maintenance", "Maintenance", "Damaged"]
ReturnCondition = Literal["Available", "Needs Maintenance", "Damaged"]


class AssetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branchId: UUID | None = None
    category: Category
    brand: str = Field(min_length=1, max_length=150)
    model: str = Field(min_length=1, max_length=150)
    serialNumber: str = Field(min_length=1, max_length=150)
    mobileNumber: str | None = Field(default=None, max_length=40)
    operatorProvider: str | None = Field(default=None, max_length=150)

    @field_validator("brand", "model", "operatorProvider", mode="before")
    @classmethod
    def clean_display(cls, value: str | None) -> str | None:
        return display_name(value) if value is not None else None

    @field_validator("serialNumber", "mobileNumber", mode="before")
    @classmethod
    def clean_identifier(cls, value: str | None) -> str | None:
        return identifier(value) if value is not None else None

    @model_validator(mode="after")
    def sim_fields(self) -> AssetCreate:
        if self.category == "SIM Card":
            if not self.mobileNumber or not self.operatorProvider:
                raise ValueError("SIM Card requires Mobile Number and Operator/Provider")
        elif self.mobileNumber is not None or self.operatorProvider is not None:
            raise ValueError("SIM fields are only permitted for SIM Card")
        return self


class AssetIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employeeId: UUID
    issueDate: date


class AssetReturn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    returnDate: date
    reason: str = Field(min_length=1, max_length=2000)
    condition: ReturnCondition

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return display_name(value)


class AssetMaintenanceStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    startDate: date
    notes: str = Field(min_length=1, max_length=2000)

    @field_validator("notes", mode="before")
    @classmethod
    def clean_notes(cls, value: str) -> str:
        return display_name(value)


class AssetMaintenanceComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completionDate: date
    resultingStatus: Literal["Available", "Damaged"]
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("notes", mode="before")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        return display_name(value) if value is not None else None


class AssetDamage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    damageDate: date
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return display_name(value)


class AssetResponse(BaseModel):
    id: UUID
    assetCode: str
    branchId: UUID
    category: str = Field(max_length=80)
    brand: str
    model: str
    serialNumber: str
    mobileNumber: str | None
    operatorProvider: str | None
    status: str = Field(max_length=30)
    currentEmployeeId: UUID | None
    createdAt: datetime


class AssetPage(BaseModel):
    items: list[AssetResponse]
    total: int
    page: int
    pageSize: int
    availableCount: int
    issuedCount: int
    maintenanceCount: int
    damagedCount: int


class AssetAssignmentResponse(BaseModel):
    id: UUID
    assetId: UUID
    employeeId: UUID
    issueDate: date
    returnDate: date | None
    returnReason: str | None
    conditionOnReturn: str | None
    durationDays: int | None
    issuedByEmployeeId: UUID | None
    returnedByEmployeeId: UUID | None


class AssetMaintenanceResponse(BaseModel):
    id: UUID
    assetId: UUID
    startDate: date
    completionDate: date | None
    resultingStatus: str | None
    notes: str | None
    completionNotes: str | None
    durationDays: int | None
    startedByEmployeeId: UUID | None
    completedByEmployeeId: UUID | None


class AssetHistoryResponse(BaseModel):
    id: UUID
    assetId: UUID
    branchId: UUID
    action: str
    previousStatus: str | None
    newStatus: str
    effectiveDate: date
    employeeId: UUID | None
    actorEmployeeId: UUID
    reason: str | None


class AssetDetail(BaseModel):
    asset: AssetResponse


class AssignmentPage(BaseModel):
    items: list[AssetAssignmentResponse]
    total: int
    page: int
    pageSize: int


class MaintenancePage(BaseModel):
    items: list[AssetMaintenanceResponse]
    total: int
    page: int
    pageSize: int


class HistoryPage(BaseModel):
    items: list[AssetHistoryResponse]
    total: int
    page: int
    pageSize: int


class EmployeeIssueCount(BaseModel):
    employeeId: UUID
    issuedCount: int


class EmployeeIssuePage(BaseModel):
    items: list[EmployeeIssueCount]
    total: int
    page: int
    pageSize: int


class AssetReport(BaseModel):
    inventory: AssetPage
    issuedByEmployee: EmployeeIssuePage
    issueReturnHistory: AssignmentPage
