import type { StatusTone } from "../../../design-system";
import { isUuid } from "../../../app/presentation/labels";

export type BankStageApiRow = {
  rowNumber: number;
  internalCaseId?: string | null;
  bankCaseNumber?: string | null;
  productLabel?: string | null;
  currentStage?: string | null;
  requestedStage?: string | null;
  status: string;
  errorCode?: string | null;
  errorDetail?: string | null;
};

export type BankStageBatchDetail = {
  batchId: string;
  fileName?: string | null;
  uploaderName?: string | null;
  status: string;
  validationStatus?: string | null;
  createdAt: string;
  totalCount: number;
  validCount: number;
  invalidCount: number;
  appliedCount: number;
  unchangedCount: number;
  eligibleCount: number;
  rowResults: BankStageApiRow[];
};

export type BankStageHistoryItem = {
  batchId: string;
  fileName?: string | null;
  uploaderName?: string | null;
  createdAt: string;
  validationStatus: string;
  status: string;
  totalCount: number;
  validCount: number;
  invalidCount: number;
  appliedCount: number;
};

export type BankStageResultRow = {
  id: string;
  rowNumber: number;
  internalCaseId: string;
  bankCaseNumber: string;
  productLabel: string;
  currentStage: string;
  requestedStage: string;
  status: string;
  errorCode: string | null;
  category: string;
  message: string;
};

const CATEGORY_BY_CODE: Record<string, string> = {
  INVALID_HEADER: "Invalid header",
  CSV_ROW_LIMIT: "CSV row limit exceeded",
  MALFORMED_ROW: "Malformed row",
  REQUIRED_VALUE: "Required value missing",
  DUPLICATE_ROW: "Duplicate row",
  EMPTY_FILE: "Empty file",
  MALFORMED_CSV: "Malformed CSV",
  CSV_SIZE_LIMIT: "CSV size limit exceeded",
  CASE_UNAVAILABLE: "Case unavailable",
  CASE_PENDING_APPROVAL: "Case awaits approval",
  FINAL_LOCK: "Case already at a final stage",
  NOT_BOOKED: "Case is not booked",
  INVALID_STAGE: "Stage not part of the assigned Pipeline",
  FINANCIAL_RULE_MISSING: "Financial rule missing",
  DUPLICATE_UPLOAD: "Previously processed import",
};

const VALID_STATUSES = new Set(["Valid", "Applied", "Unchanged", "Skipped"]);
const INVALID_STATUSES = new Set(["Invalid", "Rejected"]);

export function bankStageCategory(
  status: string,
  errorCode: string | null | undefined,
): string {
  if (status === "Valid" || status === "Applied") return "Valid row";
  if (status === "Unchanged") return "Unchanged";
  if (status === "Skipped") return "Skipped";
  if (errorCode && CATEGORY_BY_CODE[errorCode]) return CATEGORY_BY_CODE[errorCode];
  return "Invalid row";
}

export function bankStageCategoryTone(category: string): StatusTone {
  if (category === "Valid row") return "success";
  if (category === "Unchanged" || category === "Skipped") return "neutral";
  if (category === "Previously processed import") return "warning";
  if (category === "Financial rule missing") return "warning";
  return "danger";
}

export function bankStageBatchTone(status: string): StatusTone {
  if (status === "Applied") return "success";
  if (status === "Validated") return "info";
  return "danger";
}

export function safeResultMessage(value: string | null | undefined) {
  const text = String(value ?? "").trim();
  if (!text || isUuid(text)) return "";
  if (/traceback|sqlalchemy|psycopg|internal server|stack trace/i.test(text))
    return "";
  return text;
}

export function readableValue(value: string | null | undefined) {
  const text = String(value ?? "").trim();
  if (!text || isUuid(text)) return "";
  return text;
}

export function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function mapBankStageRows(
  results: readonly BankStageApiRow[],
): BankStageResultRow[] {
  return [...results]
    .sort((left, right) => left.rowNumber - right.rowNumber)
    .map((row) => ({
      id: `row-${row.rowNumber}`,
      rowNumber: row.rowNumber,
      internalCaseId: readableValue(row.internalCaseId),
      bankCaseNumber: readableValue(row.bankCaseNumber),
      productLabel: readableValue(row.productLabel),
      currentStage: readableValue(row.currentStage),
      requestedStage: readableValue(row.requestedStage),
      status: row.status,
      errorCode: row.errorCode ?? null,
      category: bankStageCategory(row.status, row.errorCode),
      message: safeResultMessage(row.errorDetail),
    }));
}

export function categoryOptions(rows: readonly BankStageResultRow[]) {
  const seen = new Set(rows.map((row) => row.category));
  return [...seen].sort().map((category) => ({
    value: category,
    label: category,
  }));
}

export function matchesBankStageSearch(
  row: BankStageResultRow,
  search: string,
) {
  const term = search.trim().toLocaleLowerCase("en");
  if (!term) return true;
  return [
    String(row.rowNumber),
    row.internalCaseId,
    row.bankCaseNumber,
    row.productLabel,
    row.currentStage,
    row.requestedStage,
    row.category,
    row.message,
    row.status,
  ]
    .join(" ")
    .toLocaleLowerCase("en")
    .includes(term);
}

export function matchesValidityFilter(
  row: BankStageResultRow,
  validity: string,
) {
  if (validity === "valid") return VALID_STATUSES.has(row.status);
  if (validity === "invalid") return INVALID_STATUSES.has(row.status);
  return true;
}

export function canConfirmImport(batch: BankStageBatchDetail | null) {
  return Boolean(
    batch &&
      batch.validationStatus === "Validated" &&
      batch.status === "Validated" &&
      batch.invalidCount === 0 &&
      batch.eligibleCount > 0,
  );
}

export const VALIDITY_OPTIONS = [
  { value: "", label: "All rows" },
  { value: "valid", label: "Valid rows" },
  { value: "invalid", label: "Invalid rows" },
];
