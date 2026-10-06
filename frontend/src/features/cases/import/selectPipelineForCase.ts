import type { CaseRow } from "../model/CaseRow";
import type { PipelineStageSet } from "./validateBankStageCsv";

const normalized = (value: string) => value.trim().toLocaleLowerCase("en");

export function selectPipelineForCase(
  caseItem: CaseRow,
  pipelines: readonly PipelineStageSet[],
): PipelineStageSet | undefined {
  const caseDate = new Date(caseItem.date);
  const caseIso = Number.isNaN(caseDate.getTime())
    ? ""
    : caseDate.toISOString().slice(0, 10);
  return pipelines
    .filter(
      (item) =>
        normalized(item.bank) === normalized(caseItem.bank) &&
        normalized(item.product) === normalized(caseItem.product) &&
        (!item.effectiveDate || (caseIso && item.effectiveDate <= caseIso)),
    )
    .sort((left, right) =>
      (right.effectiveDate ?? "").localeCompare(left.effectiveDate ?? ""),
    )[0];
}
