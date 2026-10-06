"""User Type permission configuration contract."""

from pydantic import BaseModel, ConfigDict, Field


class PermissionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: str = Field(min_length=1, max_length=64)
    grants: dict[str, bool] = Field(min_length=1, max_length=64)
