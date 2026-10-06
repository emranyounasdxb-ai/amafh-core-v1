import { parseCsv } from "../../../shared/csv/parseCsv.ts";
import type { CaseRow } from "../model/CaseRow";
import { selectPipelineForCase } from "./selectPipelineForCase.ts";

export type PipelineStageSet = {
  bank: string;
  product: string;
  effectiveDate?: string;
  stages: readonly string[];
};
export type BankStageRow = {
  line: number;
  bankRef: string;
  stage: string;
  remarks: string;
};
export type RejectedBankStageRow = BankStageRow & { reasons: string[] };
export type BankStageImportResult = {
  accepted: BankStageRow[];
  rejected: RejectedBankStageRow[];
  duplicates: RejectedBankStageRow[];
  errors: string[];
  valid: boolean;
};

const normalized = (value: string) => value.trim().toLocaleLowerCase("en");
const headerKey = (value: string) => normalized(value).replace(/[\s_-]/g, "");

export function validateBankStageCsv(
  csv: string,
  cases: readonly CaseRow[],
  pipelines: readonly PipelineStageSet[],
): BankStageImportResult {
  const parsed = parseCsv(csv);
  const errors = parsed.errors.map(
    (item) => `Line ${item.line}, column ${item.column}: ${item.reason}`,
  );
  const [header, ...body] = parsed.rows;
  if (!header) errors.push("CSV is empty.");
  const keys = header?.cells.map(headerKey) ?? [];
  const ref = keys.findIndex(
    (key) => key === "bankcasenumber" || key === "bankref",
  );
  const stage = keys.indexOf("stage");
  const remarks = keys.findIndex(
    (key) => key === "remarks" || key === "remark",
  );
  if (ref < 0 || stage < 0 || remarks < 0) {
    errors.push("Header must contain Bank Case Number, Stage, and Remarks.");
  }
  if (new Set(keys).size !== keys.length)
    errors.push("Duplicate CSV header columns are not allowed.");
  if (body.length === 0) errors.push("CSV has no data rows.");

  const accepted: BankStageRow[] = [];
  const rejected: RejectedBankStageRow[] = [];
  const duplicates: RejectedBankStageRow[] = [];
  const seen = new Set<string>();
  for (const row of body) {
    const update = {
      line: row.line,
      bankRef: row.cells[ref]?.trim() ?? "",
      stage: row.cells[stage]?.trim() ?? "",
      remarks: row.cells[remarks]?.trim() ?? "",
    };
    const reasons: string[] = [];
    if (row.cells.length !== keys.length)
      reasons.push(
        `Expected ${keys.length} columns; found ${row.cells.length}`,
      );
    if (!update.bankRef) reasons.push("Bank Case Number is required");
    if (!update.stage) reasons.push("Stage is required");
    if (!update.remarks) reasons.push("Remarks is required");
    const refKey = normalized(update.bankRef);
    if (refKey && seen.has(refKey))
      reasons.push("Duplicate Bank Case Number in this upload");
    if (refKey) seen.add(refKey);
    const matched = cases.find((item) => normalized(item.bankRef) === refKey);
    if (update.bankRef && !matched)
      reasons.push("Bank Case Number does not match a Case");
    if (
      matched &&
      !["Booked", "Case Reopened by Owner"].includes(matched.status)
    ) {
      reasons.push("Case is not an open booked Case");
    }
    if (matched) {
      const pipeline = selectPipelineForCase(matched, pipelines);
      if (!pipeline)
        reasons.push(
          `No configured pipeline for ${matched.bank} / ${matched.product}`,
        );
      else if (
        !pipeline.stages.some(
          (item) => normalized(item) === normalized(update.stage),
        )
      ) {
        reasons.push(
          `Stage is not configured for ${matched.bank} / ${matched.product}`,
        );
      }
    }
    if (reasons.length) {
      const failure = { ...update, reasons };
      rejected.push(failure);
      if (reasons.some((reason) => reason.startsWith("Duplicate")))
        duplicates.push(failure);
    } else {
      accepted.push(update);
    }
  }
  return {
    accepted,
    rejected,
    duplicates,
    errors,
    valid: errors.length === 0 && rejected.length === 0,
  };
}
