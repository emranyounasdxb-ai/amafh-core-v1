"""Bound populations without expanding hundreds of SQL placeholders."""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Text, any_, bindparam
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


def uuid_set(column, values: Iterable[UUID]):
    return column == any_(bindparam(None, list(values), type_=ARRAY(PG_UUID(as_uuid=True))))


def text_set(column, values: Iterable[str]):
    return column == any_(bindparam(None, list(values), type_=ARRAY(Text())))
