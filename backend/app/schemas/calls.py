"""Calls request bodies. Phone numbers stay out of the URL."""

from pydantic import BaseModel, ConfigDict, Field


class SearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str
    customerNumber: str = Field(max_length=80)
    page: int | None = None
    pageSize: int | None = None
