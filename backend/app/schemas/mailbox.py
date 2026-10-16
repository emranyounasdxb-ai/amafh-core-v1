"""Mailbox inputs. The server chooses the address, host and sender."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MailboxConnect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=256)


class SignatureUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    html: str = Field(max_length=100_000)


class MailMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to: list[str] = Field(default_factory=list, max_length=50)
    cc: list[str] = Field(default_factory=list, max_length=50)
    bcc: list[str] = Field(default_factory=list, max_length=50)
    subject: str = ""
    html: str = ""
    attachmentIds: list[UUID] = Field(default_factory=list, max_length=20)
    keptAttachmentIndexes: list[int] = Field(default_factory=list, max_length=20)
    previousRef: str | None = None
    attemptId: UUID | None = None
    inReplyTo: str | None = None
    references: str | None = None
