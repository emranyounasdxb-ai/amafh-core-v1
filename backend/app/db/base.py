"""Shared PostgreSQL schema conventions."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, MetaData
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

metadata = MetaData()


def pk() -> Column:
    return Column("id", UUID(as_uuid=True), primary_key=True, default=uuid4)


def created_at() -> Column:
    return Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())


def updated_at() -> Column:
    return Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


def utcnow() -> datetime:
    from datetime import UTC

    return datetime.now(UTC)
