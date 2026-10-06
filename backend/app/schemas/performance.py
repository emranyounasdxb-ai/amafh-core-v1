"""Validated Target, holiday, performance and ranking contracts."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.whole_numbers import WholeAmount, WholeCount


class TargetInput(BaseModel):
    branchId: UUID
    departmentId: UUID
    designationId: UUID
    effectiveDate: date
    targetPoints: WholeCount | None = Field(default=None, gt=0)
    targetAmountAed: WholeAmount | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def exactly_one_value(self):
        if (self.targetPoints is None) == (self.targetAmountAed is None):
            raise ValueError("Exactly one Target value is required")
        return self


class TargetResponse(BaseModel):
    id: UUID
    branchId: UUID
    departmentId: UUID
    designationId: UUID
    effectiveDate: date
    targetPoints: int | None
    targetAmountAed: Decimal | None
    active: bool
    inactiveFromDate: date | None
    supersededByTargetId: UUID | None


class TargetPage(BaseModel):
    items: list[TargetResponse]
    total: int
    page: int
    pageSize: int


class HolidayInput(BaseModel):
    holidayDate: date
    name: str = Field(min_length=1, max_length=200)
    sourceReference: str = Field(min_length=1, max_length=1000)


class HolidayYearInput(BaseModel):
    applicableYear: int = Field(ge=1900, le=9999)
    sourceReference: str = Field(min_length=1, max_length=1000)


class PerformanceFilters(BaseModel):
    startDate: date | None = None
    endDate: date | None = None
    branchId: UUID | None = None
    departmentId: UUID | None = None
    teamId: UUID | None = None
    designationId: UUID | None = None
    productCode: Literal["CC", "PF"] | None = None
    bankId: UUID | None = None

    @model_validator(mode="after")
    def valid_range(self):
        if (self.startDate is None) != (self.endDate is None):
            raise ValueError("Both date bounds are required")
        if (
            self.startDate is not None
            and self.endDate is not None
            and self.startDate > self.endDate
        ):
            raise ValueError("Date range is invalid")
        return self


class RankingConfirmationInput(BaseModel):
    selectedEmployeeId: UUID
