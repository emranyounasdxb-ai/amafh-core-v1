import type { CaseRow } from "../cases/model/CaseRow";

export function caseAmount(caseItem: CaseRow) {
  return caseItem.product === "PF"
    ? Number(caseItem.variant.replace(/[^0-9.]/g, "")) || 0
    : 0;
}
