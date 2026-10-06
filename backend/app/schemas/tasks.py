"""Typed Task queues, retained history, and command payloads."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Priority = Literal["Low", "Normal", "High", "Urgent"]
Status = Literal["Open", "In Progress", "Completed", "Cancelled"]
RelatedType = Literal[
    "case",
    "customer",
    "employee",
    "asset",
    "attendance",
    "attendance_import",
    "finance_result",
    "clawback",
    "payment",
]


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    assigneeEmployeeId: UUID
    priority: Priority
    dueAt: datetime
    relatedType: RelatedType | None = None
    relatedId: UUID | None = None

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            raise ValueError("Title is required")
        return value

    @field_validator("dueAt")
    @classmethod
    def aware_due(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Due time requires a timezone offset")
        return value

    @model_validator(mode="after")
    def related_pair(self) -> TaskCreate:
        if (self.relatedType is None) != (self.relatedId is None):
            raise ValueError("Related Type and ID must be supplied together")
        return self


class TaskStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["Open", "In Progress", "Completed"]


class TaskReassignInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assigneeEmployeeId: UUID
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            raise ValueError("Reason is required")
        return value


class TaskReasonInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            raise ValueError("Reason is required")
        return value


class TaskReopenInput(TaskReasonInput):
    dueAt: datetime

    @field_validator("dueAt")
    @classmethod
    def aware_due(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Due time requires a timezone offset")
        return value


class TaskDueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dueAt: datetime

    @field_validator("dueAt")
    @classmethod
    def aware_due(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Due time requires a timezone offset")
        return value


class TaskItem(BaseModel):
    id: UUID
    title: str
    description: str | None
    creatorEmployeeId: UUID
    assigneeEmployeeId: UUID
    branchId: UUID
    departmentId: UUID
    teamId: UUID | None
    priority: Priority
    status: Status
    dueAt: datetime
    completedAt: datetime | None
    archivedAt: datetime | None
    isOverdue: bool
    relatedType: RelatedType | None
    relatedId: UUID | None
    relatedUnavailable: bool
    createdAt: datetime
    updatedAt: datetime


class TaskPage(BaseModel):
    items: list[TaskItem]
    total: int
    page: int
    pageSize: int


class TaskHistoryItem(BaseModel):
    id: UUID
    taskId: UUID
    action: str
    actorEmployeeId: UUID
    reason: str | None
    beforeValues: dict | None
    afterValues: dict
    createdAt: datetime


class TaskHistoryPage(BaseModel):
    items: list[TaskHistoryItem]
    total: int
    page: int
    pageSize: int


class TaskRelatedDestination(BaseModel):
    path: str


class TaskRelatedOption(BaseModel):
    id: UUID
    label: str
    subtitle: str | None = None


class TaskRelatedOptionPage(BaseModel):
    items: list[TaskRelatedOption]
    total: int
    page: int
    pageSize: int
