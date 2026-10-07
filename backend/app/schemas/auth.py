"""Authentication API contract."""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    """A malformed email gets the generic credential failure rather than a field error."""

    email: str = Field(min_length=1, max_length=254)
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def trim_email(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class PasswordChange(BaseModel):
    token: str = Field(min_length=30, max_length=128)
    password: str = Field(max_length=128)


class LinkRequest(BaseModel):
    employeeId: UUID


class CurrentUser(BaseModel):
    employeeId: str
    displayName: str
    avatarFileId: str | None = None
    designation: str
    branchId: str | None
    departmentId: str | None
    teamId: str | None
    permissions: list[str]
    csrfToken: str | None = None
