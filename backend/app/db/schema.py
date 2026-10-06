"""Import every table into the single migration metadata."""

from . import (  # noqa: F401
    assets,
    attendance,
    cases,
    finance,
    hr_records,
    operations,
    organization,
    performance,
    targets,
    tasks,
)
from .base import metadata

__all__ = ["metadata"]
