"""Calls request bodies. Phone numbers stay out of the URL."""

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class SearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str
    customerNumber: str = Field(max_length=80)
    page: int | None = None
    pageSize: int | None = None


class NumberSuggestionsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str
    prefix: str = Field(max_length=32)


class CallsAccessUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    granted: StrictBool
    revision: int = Field(ge=0, strict=True)
