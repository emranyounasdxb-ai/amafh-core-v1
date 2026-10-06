"""Recipient-only notification contracts."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationItem(BaseModel):
    id: UUID
    kind: str
    message: str
    availableOn: date
    createdAt: datetime
    readAt: datetime | None


class NotificationPage(BaseModel):
    items: list[NotificationItem]
    total: int
    page: int
    pageSize: int


class UnreadCount(BaseModel):
    count: int


class MarkAllResult(BaseModel):
    markedCount: int


class NotificationDestination(BaseModel):
    path: str
