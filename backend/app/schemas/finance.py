"""Validated Phase 3 Finance command contracts."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.normalization import display_name, identifier
from app.whole_numbers import WholeAmount, WholeCount


class FinancialRuleInput(BaseModel):
    bankId: UUID
    productTypeId: UUID
    productVariantId: UUID | None = None
    pfAmountMin: WholeAmount | None = Field(default=None, gt=0)
    pfAmountMax: WholeAmount | None = Field(default=None, gt=0)
    ccPoints: WholeCount | None = Field(default=None, gt=0)
    commissionAed: WholeAmount | None = Field(default=None, ge=0)
    effectiveDate: date

    @model_validator(mode="after")
    def one_product_context(self):
        if self.productVariantId is not None:
            if self.pfAmountMin is not None or self.pfAmountMax is not None:
                raise ValueError("CC rules cannot have a PF slab")
            if self.ccPoints is None and self.commissionAed is None:
                raise ValueError("CC rules require points and/or commission")
        elif (
            self.pfAmountMin is None
            or self.pfAmountMax is None
            or self.pfAmountMin > self.pfAmountMax
            or self.ccPoints is not None
            or self.commissionAed is None
        ):
            raise ValueError("PF rules require a valid slab and financial value")
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
