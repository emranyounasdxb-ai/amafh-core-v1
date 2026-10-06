"""Typed, allowlisted Phase 6 report filters and tabular response."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ReportKind = Literal[
    "case-pipeline",
    "customers",
    "sales-performance",
    "ranking",
    "coordinator-workload",
    "finance-completed",
    "finance-clawbacks",
    "finance-payments",
    "finance-paid-totals",
    "attendance",
    "assets",
    "hr-employees",
    "hr-assignments",
]


class ReportFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: Literal["today", "week", "month", "year", "custom"] = "month"
    startDate: date | None = None
    endDate: date | None = None
    branchId: UUID | None = None
    departmentId: UUID | None = None
    teamId: UUID | None = None
    employeeId: UUID | None = None
    designationId: UUID | None = None
    bankId: UUID | None = None
    productCode: Literal["CC", "PF"] | None = None
    customerType: Literal["Individual", "Company"] | None = None
    status: str | None = Field(None, max_length=50)
    accessStatus: Literal["Not Provisioned", "Active", "Disabled"] | None = None
    category: str | None = Field(None, max_length=80)

    @model_validator(mode="after")
    def date_pair(self):
        if self.period == "custom":
            if self.startDate is None or self.endDate is None:
                raise ValueError("Custom reports require both date bounds")
        elif self.startDate is not None or self.endDate is not None:
            raise ValueError("Explicit dates require the custom period")
        if self.startDate and self.endDate and self.startDate > self.endDate:
            raise ValueError("Date range is invalid")
        return self


class ReportColumn(BaseModel):
    key: str
    heading: str


class ReportCatalogItem(BaseModel):
    report: ReportKind
    title: str
    columns: list[ReportColumn]
    filters: list[str]


class ReportPage(BaseModel):
    report: ReportKind
    title: str
    columns: list[ReportColumn]
    items: list[dict[str, str | int | bool | None]]
    summary: dict[str, str | int | bool | None]
    total: int
    page: int
    pageSize: int
    startDate: date
    endDate: date
    filters: dict[str, str]
