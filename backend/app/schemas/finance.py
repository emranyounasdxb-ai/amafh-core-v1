"""Validated Phase 3 Finance command contracts."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.normalization import display_name, identifier
from app.whole_numbers import NonNegativeWholeAed, WholeAmount, WholeCount


class CCSalaryPoints(BaseModel):
    model_config = {"extra": "forbid"}

    salaryMin: NonNegativeWholeAed
    salaryMax: NonNegativeWholeAed
    points: WholeCount = Field(gt=0, le=2147483647)

    @model_validator(mode="after")
    def ordered_range(self):
        if self.salaryMin > self.salaryMax:
            raise ValueError("Salary minimum must not exceed salary maximum")
        return self


class FinancialRuleInput(BaseModel):
    bankId: UUID
    productTypeId: UUID
    productVariantId: UUID | None = None
    pfAmountMin: WholeAmount | None = Field(default=None, gt=0)
    pfAmountMax: WholeAmount | None = Field(default=None, gt=0)
    ccPoints: WholeCount | None = Field(default=None, gt=0)
    ccSalaryPoints: list[CCSalaryPoints] = Field(default_factory=list, max_length=100)
    commissionAed: WholeAmount | None = Field(default=None, ge=0)
    pfCommissionPer1000: NonNegativeWholeAed | None = None
    effectiveDate: date

    @field_validator("ccSalaryPoints")
    @classmethod
    def distinct_salary_ranges(cls, rows):
        rows = sorted(rows, key=lambda row: row.salaryMin)
        for previous, current in zip(rows, rows[1:], strict=False):
            if current.salaryMin <= previous.salaryMax:
                raise ValueError("Salary ranges must not overlap, including their endpoints")
        return rows

    @model_validator(mode="after")
    def one_product_context(self):
        if self.productVariantId is not None:
            if self.pfCommissionPer1000 is not None:
                raise ValueError("CC rules cannot have a PF commission rate")
            if self.pfAmountMin is not None or self.pfAmountMax is not None:
                raise ValueError("CC rules cannot have a PF slab")
            if self.ccSalaryPoints and self.ccPoints is not None:
                raise ValueError("Choose salary-range points or fixed CC points, not both")
            if self.ccPoints is None and self.commissionAed is None and not self.ccSalaryPoints:
                raise ValueError("CC rules require points and/or commission")
        elif (
            self.pfAmountMin is None
            or self.pfAmountMax is None
            or self.pfAmountMin > self.pfAmountMax
            or self.ccPoints is not None
            or self.ccSalaryPoints
            or self.commissionAed is not None
            or self.pfCommissionPer1000 is None
        ):
            raise ValueError(
                "PF rules require a valid loan range and commission AED per 1,000; no points"
            )
        return self


class ClawbackInput(BaseModel):
    internalCaseId: str = Field(min_length=1, max_length=80)
    amountAed: WholeAmount = Field(gt=0)
    clawbackDate: date
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("internalCaseId")
    @classmethod
    def clean_case_id(cls, value: str) -> str:
        return identifier(value)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        result = display_name(value)
        if not result:
            raise ValueError("Reason is required")
        return result


class PaymentInput(BaseModel):
    employeeId: UUID
    paymentType: Literal["Salary", "Commission"]
    amountAed: WholeAmount = Field(gt=0)
    paymentMonth: date
    paymentDate: date

    @field_validator("paymentMonth")
    @classmethod
    def first_day(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("Payment Month must be the first day of its month")
        return value
