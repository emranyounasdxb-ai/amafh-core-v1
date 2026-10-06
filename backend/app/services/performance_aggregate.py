"""Aggregate scoped employee metrics without exposing Target denominators."""

from decimal import Decimal

from app.services.performance_math import achievement_percentage
from app.whole_numbers import whole_text


def summarize(rows: list[tuple[dict, dict[str, Decimal]]]) -> dict:
    metrics = [item for item, _ in rows]
    counts = {}
    for name in (
        "createdCaseCount",
        "bookedCaseCount",
        "completedCaseCount",
        "rejectedCaseCount",
        "inProgressCaseCount",
    ):
        counts[name] = sum(item[name] for item in metrics)
    if all(item["delayedMetricState"] == "Available" for item in metrics):
        delayed_count = sum(item["delayedCaseCount"] for item in metrics)
        delayed_state = "Available"
    else:
        delayed_count = None
        delayed_state = "Holiday calendar unavailable"
    stages: dict[str, int] = {}
    for item in metrics:
        for stage, count in item["inProgressByStage"].items():
            stages[stage] = stages.get(stage, 0) + count
    progress = {}
    for product in ("CC", "PF"):
        achieved = sum(
            (Decimal(item["targetProgress"][product]["achieved"]) for item in metrics),
            Decimal(0),
        )
        denominator = sum((values[product] for _, values in rows), Decimal(0))
        percentage = achievement_percentage(achieved, denominator)
        progress[product] = {
            "state": "No Target" if percentage is None else "Configured",
            "achieved": whole_text(achieved),
            "achievementPercentage": str(percentage) if percentage is not None else None,
        }
    return {
        **counts,
        "inProgressByStage": stages,
        "delayedCaseCount": delayed_count,
        "delayedMetricState": delayed_state,
        "achievedCCPoints": whole_text(sum(Decimal(item["achievedCCPoints"]) for item in metrics)),
        "achievedPFAed": whole_text(sum(Decimal(item["achievedPFAed"]) for item in metrics)),
        "targetProgress": progress,
    }
