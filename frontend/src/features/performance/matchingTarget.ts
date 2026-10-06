import type { EmployeeRow } from "../employees/EmployeeRow";
import type { TargetRule } from "./TargetRule";

export function matchingTarget(
  employee: EmployeeRow,
  rules: TargetRule[],
  asOf: string,
) {
  return rules
    .filter(
      (rule) =>
        rule.branch === employee.branch &&
        rule.department === employee.department &&
        rule.designation === employee.designation &&
        rule.effectiveDate <= asOf,
    )
    .sort((left, right) =>
      right.effectiveDate.localeCompare(left.effectiveDate),
    )[0];
}
