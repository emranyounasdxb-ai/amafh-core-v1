"""Sort complete, already-authorized computed rows before pagination."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any


def metric_value(row: dict, key: str) -> Any:
    if key == "targetProgress":
        progress = row.get("targetProgress") or {}
        values = []
        for product in ("CC", "PF"):
            item = progress.get(product) or {}
            percentage = item.get("achievementPercentage")
            values.append(Decimal(str(percentage)) if percentage is not None else None)
        if all(value is None for value in values):
            return None
        return tuple(value if value is not None else Decimal("-Infinity") for value in values)
    value = row.get(key)
    if value is None:
        return None
    if key in {
        "achievedCCPoints",
        "achievedPFAed",
        "achievementPercentage",
        "achievedValue",
    }:
        return Decimal(str(value))
    if isinstance(value, str):
        return value.casefold()
    return value


def sort_rows(
    rows: list[dict],
    key: str,
    direction: str,
    *,
    value: Callable[[dict, str], Any] = metric_value,
    identity: str = "employeeId",
) -> list[dict]:
    """Keep nulls last and a stable identifier as the secondary order."""
    stable = sorted(rows, key=lambda row: str(row.get(identity) or row.get("id") or ""))
    present = [row for row in stable if value(row, key) is not None]
    missing = [row for row in stable if value(row, key) is None]
    present.sort(key=lambda row: value(row, key), reverse=direction == "desc")
    return present + missing
