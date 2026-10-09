import { useState } from "react";
import {
  Button,
  Checkbox,
  DataTable,
  Dialog,
  DownloadTemplateAction,
  FileUpload,
  ImportProgress,
  ImportValidationSummary,
  InlineNotice,
  Pagination,
  TruncatedText,
} from "../../../design-system";
import { download } from "../../../app/api/download";
import { ApiFailure } from "../../../app/api/http";
import { useResource } from "../../../app/api/useResource";
import { useSession } from "../../../app/session/useSession";
import { useConnectedColumnLayout } from "../../../shared/table/useConnectedColumnLayout";
import styles from "./EmployeesPage.module.css";

type Column = { field: string; label: string; required: boolean };
type References = {
  columns: Column[];
  branches: { id: string; name: string; active: boolean }[];
  departments: { name: string; branch_id: string; active: boolean }[];
  userTypes: { name: string }[];
  managers: { code: string; name: string }[];
};
type RowError = { rowNumber: number; column: string; message: string };
type ImportRow = {
  rowNumber: number;
  values: Record<string, string>;
  errors: RowError[];
};
type Review = {
  totalRows: number;
  validRows: number;
  invalidRows: number;
  canImport: boolean;
  rows: ImportRow[];
  errors: RowError[];
};

export function EmployeeImportDialog({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const { api } = useSession();
  const references = useResource<References>("/employees/import/references");
  const [files, setFiles] = useState<FileList | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [busy, setBusy] = useState<"validating" | "importing" | null>(null);
  const [error, setError] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [page, setPage] = useState(1);
  const layout = useConnectedColumnLayout<ImportRow>(
    "employee-import-preview",
    [
      { key: "row", label: "CSV row", width: 90, fixed: true },
      ...(references.data?.columns ?? []).map((column) => ({
        key: column.label,
        label: column.label,
        width: column.field === "fullName" ? 200 : 170,
      })),
      { key: "errors", label: "Validation", width: 300, fixed: true },
    ],
  );
  const file = files?.[0];
  const ready =
    review?.canImport &&
    confirmed &&
    !busy &&
    Boolean(references.data) &&
    !references.error;

  async function validate() {
    if (!file || busy) return;
    setError("");
    setConfirmed(false);
    setReview(null);
    setPage(1);
    if (file.size > 5_000_000) {
      setError("Maximum file size is 5 MB (5,000,000 bytes).");
      return;
    }
    const body = new FormData();
    body.append("file", file);
    setBusy("validating");
    try {
      setReview(
        await api.request<Review>("/employees/import/validate", {
          method: "POST",
          body,
        }),
      );
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Validation failed. Retry safely.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function importEmployees() {
    if (!ready || !file) return;
    const body = new FormData();
    body.append("file", file);
    setBusy("importing");
    setError("");
    try {
      const result = await api.request<{ createdCount: number }>(
        "/employees/import/confirm",
        {
          method: "POST",
          body,
          headers: { "Idempotency-Key": key },
        },
      );
      onSaved(
        `${result.createdCount} employee profiles imported as Pending Setup. No login accounts were created.`,
      );
    } catch (failure) {
      const details =
        failure instanceof ApiFailure
          ? Object.entries(failure.fieldErrors).flatMap(([field, messages]) =>
              messages.map(
                (message) =>
                  `${field.replace(/^rows\.(\d+)\./, "CSV row $1 · ")}: ${message}`,
              ),
            )
          : [];
      setError(
        [
          failure instanceof Error
            ? failure.message
            : "Import failed. Retry safely.",
          ...details,
        ].join(" "),
      );
      if (
        failure instanceof ApiFailure &&
        failure.status >= 400 &&
        failure.status < 500
      ) {
        setConfirmed(false);
        const rowErrors = Object.entries(failure.fieldErrors).flatMap(
          ([field, messages]) => {
            const match = /^rows\.(\d+)\.(.+)$/.exec(field);
            return match
              ? messages.map((message) => ({
                  rowNumber: Number(match[1]),
                  column: match[2],
                  message,
                }))
              : [];
          },
        );
        setReview((current) => {
          if (!current) return null;
          const rows = current.rows.map((row) => ({
            ...row,
            errors: [
              ...row.errors,
              ...rowErrors.filter((item) => item.rowNumber === row.rowNumber),
            ],
          }));
          const invalidRows = rows.filter((row) => row.errors.length).length;
          return {
            ...current,
            rows,
            invalidRows,
            validRows: current.totalRows - invalidRows,
            canImport: false,
          };
        });
      }
    } finally {
      setBusy(null);
    }
  }

  return (
    <Dialog
      open
      title="Import Employees"
      size="xl"
      busy={Boolean(busy)}
      onClose={onClose}
      description="Validate and review the entire CSV before creating employee profiles."
      footer={
        <>
          <Button
            variant="secondary"
            disabled={Boolean(busy)}
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            disabled={
              !file ||
              Boolean(busy) ||
              !references.data ||
              Boolean(references.error)
            }
            onClick={() => void validate()}
            loading={busy === "validating"}
          >
            Validate CSV
          </Button>
          <Button
            disabled={!ready}
            loading={busy === "importing"}
            onClick={() => void importEmployees()}
          >
            Import {review?.totalRows ?? ""} employees
          </Button>
        </>
      }
    >
      <div className={styles.importBody}>
        <DownloadTemplateAction
          label="Download CSV Template"
          onClick={() => {
            void download(api, "/employees/import/template").catch(
              (failure: unknown) => {
                setError(
                  failure instanceof Error
                    ? failure.message
                    : "Template download failed.",
                );
              },
            );
          }}
        />
        <InlineNotice tone="info" title="CSV instructions">
          Dates: YYYY-MM-DD. Nationality: ISO alpha-2 (AE, IN, PK). Gender: Male
          or Female. Marital status: Single or Married. Keep mobile, Company
          Employee Code, passport and Emirates ID columns as text in
          spreadsheets to preserve leading zeros. Emirates ID may be formatted
          or unformatted. Do not enter System Employee Codes or account
          credentials. Optional Branch and Department must be supplied together.
          Reporting Manager must be an eligible existing Active employee.
        </InlineNotice>
        {references.error ? (
          <InlineNotice tone="error">
            References unavailable: {references.error}. Close and reopen to
            retry.
          </InlineNotice>
        ) : references.loading ? (
          <p role="status">Loading authorized reference values…</p>
        ) : references.data ? (
          <details>
            <summary>Fields and available organization references</summary>
            <div className={styles.importReferences}>
              <p>
                Required:{" "}
                {references.data.columns
                  .filter((column) => column.required)
                  .map((column) => column.label)
                  .join(", ")}
                .
              </p>
              <p>
                Optional:{" "}
                {references.data.columns
                  .filter((column) => !column.required)
                  .map((column) => column.label)
                  .join(", ")}
                .
              </p>
              <p>
                User Types:{" "}
                {references.data.userTypes
                  .map((role) => role.name)
                  .join(", ") || "None"}
                .
              </p>
              <p>
                Branches:{" "}
                {references.data.branches
                  .map(
                    (branch) =>
                      `${branch.name}${branch.active ? "" : " (inactive)"}`,
                  )
                  .join(", ") || "None"}
                .
              </p>
              <p>
                Departments (use the name in the Department column):{" "}
                {references.data.departments
                  .map(
                    (department) =>
                      `${department.name} · ${references.data?.branches.find((branch) => branch.id === department.branch_id)?.name ?? "Unavailable Branch"}${department.active ? "" : " (inactive; not eligible)"}`,
                  )
                  .join("; ") || "None"}
                .
              </p>
              <p>
                Reporting Managers (use Company Employee Code):{" "}
                {references.data.managers
                  .map((manager) => `${manager.code} · ${manager.name}`)
                  .join("; ") || "None"}
                .
              </p>
            </div>
          </details>
        ) : null}
        <FileUpload
          id="employee-import-csv"
          label="Employee CSV"
          accept=".csv,text/csv"
          files={files}
          busy={Boolean(busy)}
          hint="UTF-8 CSV, optional BOM; up to 5 MB and 5,000 employee rows."
          onChange={(next) => {
            setFiles(next);
            setReview(null);
            setConfirmed(false);
            setError("");
            setKey(crypto.randomUUID());
            setPage(1);
          }}
        />
        <ImportProgress
          phase={busy ?? "select"}
          message={
            busy === "validating"
              ? "Validating every employee row; no records are being created…"
              : "Creating the complete batch…"
          }
        />
        {error ? (
          <InlineNotice tone="error" title="Unable to complete import">
            {error}
          </InlineNotice>
        ) : null}
        {review ? (
          <>
            <p>{review.totalRows} employee rows reviewed</p>
            <ImportValidationSummary
              valid={review.validRows}
              errors={review.invalidRows}
            />
            {review.errors.map((item, index) => (
              <InlineNotice key={index} tone="error">
                CSV row {item.rowNumber} · {item.column}: {item.message}
              </InlineNotice>
            ))}
            <div className={styles.importTable}>
              <DataTable
                tableId="employee-import-preview"
                ariaLabel="Employee import review"
                stackOnNarrow={false}
                rows={review.rows.slice((page - 1) * 25, page * 25)}
                rowKey={(row) => String(row.rowNumber)}
                columns={layout.columns.map((column) => ({
                  key: column.key,
                  header: column.label,
                  width: `${column.width}px`,
                  fixed: column.fixed,
                  render: (row: ImportRow) =>
                    column.key === "row" ? (
                      row.rowNumber
                    ) : column.key === "errors" ? (
                      row.errors.length ? (
                        <ul className={styles.importErrors}>
                          {row.errors.map((item, index) => (
                            <li key={index}>
                              {item.column}: {item.message}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        "Valid"
                      )
                    ) : (
                      <TruncatedText value={row.values[column.key] || "—"} />
                    ),
                }))}
                onColumnResize={layout.resize}
                onColumnReorder={layout.move}
              />
            </div>
            {review.rows.length > 25 ? (
              <Pagination
                page={page}
                pageCount={Math.ceil(review.rows.length / 25)}
                onPageChange={setPage}
              />
            ) : null}
            {review.canImport ? (
              <Checkbox
                id="employee-import-confirm"
                checked={confirmed}
                disabled={Boolean(busy)}
                onChange={(event) => setConfirmed(event.currentTarget.checked)}
                label={`I reviewed all ${review.totalRows} rows and confirm creating Pending Setup profiles only.`}
              />
            ) : (
              <InlineNotice tone="warning">
                Import is disabled. Correct the CSV and validate it again; no
                employees have been created.
              </InlineNotice>
            )}
          </>
        ) : null}
      </div>
    </Dialog>
  );
}
