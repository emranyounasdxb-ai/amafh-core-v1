"""Resolve CC points from a rule and the immutable Case salary snapshot."""

from decimal import Decimal

from app.errors import ApiError


def resolve_points(rule, salary) -> int | None:
    slabs = rule["cc_salary_points"]
    if not slabs:
        return rule["cc_points"]
    if salary is None:
        raise ApiError(422, "CC_SALARY_MISSING", "Case has no retained salary for CC points")
    amount = Decimal(str(salary))
    for slab in slabs:
        if Decimal(slab["salaryMin"]) <= amount <= Decimal(slab["salaryMax"]):
            return slab["points"]
    raise ApiError(
        422,
        "CC_SALARY_RULE_MISSING",
        "No salary points range matches this Case. Configure a matching Financial Rule.",
    )
