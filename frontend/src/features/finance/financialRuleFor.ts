import type { CaseRow } from "../cases/model/CaseRow";
import { caseAmount } from "../performance/caseAmount.ts";
import type { FinancialRule } from "./FinancialRule";

export function financialRuleFor(
  caseItem: CaseRow,
  rules: FinancialRule[],
  completedIso: string,
) {
  const amount = caseAmount(caseItem);
  return rules
    .filter(
      (rule) =>
        rule.bank === caseItem.bank &&
        rule.product === caseItem.product &&
        rule.effectiveDate <= completedIso &&
        (rule.product === "CC"
          ? rule.variantOrSlab === caseItem.variant
          : amount >= (rule.minimum ?? Infinity) &&
            amount <= (rule.maximum ?? -Infinity)),
    )
    .sort((left, right) =>
      right.effectiveDate.localeCompare(left.effectiveDate),
    )[0];
}
