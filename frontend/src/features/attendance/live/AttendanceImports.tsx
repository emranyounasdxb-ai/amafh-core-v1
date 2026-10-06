import { useRef, useState } from "react";
import {
  ActionToolbar,
  Button,
  CompactDate,
  CompactDateTime,
  ConfirmationDialog,
  DataTable,
  DateField,
  Dialog,
  DownloadTemplateAction,
  Drawer,
  DropdownSelect,
  EmptyState,
  EmptyValue,
  ErrorState,
  FileUpload,
  FilterToolbar,
  FilterToolbarItem,
  FormField,
  ImportProgress,
  ImportResult,
  InlineNotice,
  LoadingState,
  OfflineState,
  Pagination,
  PermissionDeniedState,
  RecordCount,
  SectionCard,
  StatusBadge,
  StatusSummary,
  TruncatedText,
  dubaiTodayDateOnly,
  type DataTableColumn,
  type DateOnly,
} from "../../../design-system";
import { download } from "../../../app/api/download";
import { ApiFailure } from "../../../app/api/http";
import type { NamedRecord, Page } from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import { useSession } from "../../../app/session/useSession";
import { useTableSelection } from "../../../shared/table/useTableSelection";
import { namedLabel } from "../../employees/live/employeePresentation";
import {
  commandMessage,
  importStatusTone,
  rowMessage,
  type AttendanceImportBatch,
  type AttendanceImportResult,
  type AttendanceImportRow,
} from "./attendancePresentation";
import styles from "./AttendancePage.module.css";

type ResultRow = { id: string; row: number; column: string; message: string };

function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

function Count({ value }: { value: number | null }) {
  return value == null ? (
    <EmptyValue />
  ) : (
    <span className="ds-numeric">{value}</span>
  );
}

const RESULT_COLUMNS: DataTableColumn<ResultRow>[] = [
  { key: "row", header: "Row", width: "80px", kind: "number", render: (row) => <Count value={row.row} /> },
  {
    key: "column",
    header: "Column",
    width: "180px",
    render: (row) =>
      row.column ? <TruncatedText value={row.column} /> : <EmptyValue />,
  },
  {
    key: "message",
    header: "Result",
    width: "360px",
    render: (row) => <TruncatedText value={row.message} />,
  },
];

export function AttendanceImports({
  branchId,
  branchLocked,
  branches,
  onApplied,
}: {
  branchId: string;
  branchLocked: boolean;
  branches: NamedRecord[] | null;
  onApplied: () => void;
}) {
  const { api } = useSession();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadBranch, setUploadBranch] = useState(branchId);
  const [templateDate, setTemplateDate] = useState<DateOnly | "">(
    dubaiTodayDateOnly(),
  );
  const [files, setFiles] = useState<FileList | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [templateError, setTemplateError] = useState("");
  const [result, setResult] = useState<AttendanceImportResult | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [refresh, setRefresh] = useState(0);
  const [openBatch, setOpenBatch] = useState<AttendanceImportBatch | null>(
    null,
  );
  const [rowsPage, setRowsPage] = useState(1);
  const key = useRef(crypto.randomUUID());
  const file = files?.[0] ?? null;

  const historyQuery = new URLSearchParams({
    page: String(page),
    pageSize: String(pageSize),
  });
  if (branchId) historyQuery.set("branchId", branchId);
  if (statusFilter) historyQuery.set("status", statusFilter);
  const history = useResource<Page<AttendanceImportBatch>>(
    `/attendance/imports?${historyQuery}`,
    refresh,
  );
  const batchRows = useResource<Page<AttendanceImportRow>>(
    openBatch
      ? `/attendance/imports/${encodeURIComponent(openBatch.batchId)}/rows?page=${rowsPage}&pageSize=25`
      : null,
  );
  const historySource = new URLSearchParams(historyQuery);
  historySource.delete("page");
  historySource.delete("pageSize");
  const historySelection = useTableSelection<AttendanceImportBatch>(
    "attendance-imports",
    history.data
      ? {
          path: `/attendance/imports?${historySource}`,
          page,
          size: pageSize,
          total: history.data.total,
          busy: history.loading || Boolean(history.error),
        }
      : undefined,
  );
  const rowsSelection = useTableSelection<AttendanceImportRow>(
    "attendance-import-rows",
    openBatch && batchRows.data
      ? {
          path: `/attendance/imports/${encodeURIComponent(openBatch.batchId)}/rows`,
          page: rowsPage,
          size: 25,
          total: batchRows.data.total,
          busy: batchRows.loading || Boolean(batchRows.error),
        }
      : undefined,
  );

  const branchName = (id: string | null) =>
    id ? namedLabel(branches, id) : "";
  const openUpload = () => {
    setUploadBranch(branchId);
    setFiles(null);
    setResult(null);
    setError("");
    setTemplateError("");
    key.current = crypto.randomUUID();
    setUploadOpen(true);
  };
  const selectFiles = (next: FileList | null) => {
    setFiles(next);
    setResult(null);
    setError("");
    key.current = crypto.randomUUID();
  };
  const send = async () => {
    if (!file || !uploadBranch || busy) return;
    const body = new FormData();
    body.append("file", file);
    setBusy(true);
    setError("");
    try {
      const response = await api.request<AttendanceImportResult>(
        `/attendance/imports?branchId=${encodeURIComponent(uploadBranch)}`,
        { method: "POST", body, headers: { "Idempotency-Key": key.current } },
      );
      setResult(response);
      setRefresh((value) => value + 1);
      if (response.status === "Applied") onApplied();
    } catch (failure) {
      setError(
        commandMessage(failure instanceof ApiFailure ? failure.code : undefined),
      );
    } finally {
      setBusy(false);
      setConfirmOpen(false);
    }
  };

  const historyRows = history.data?.items ?? [];
  const historyTotal = history.data?.total ?? 0;
  const rawBatchRows = batchRows.data?.items ?? [];
  const historyColumns: DataTableColumn<AttendanceImportBatch>[] = [
    {
      key: "attendanceDate",
      header: "Attendance date",
      width: "140px",
      kind: "date",
      render: (row) =>
        row.attendanceDate ? (
          <CompactDate value={row.attendanceDate} />
        ) : (
          <EmptyValue />
        ),
    },
    ...(!branchId
      ? [
          {
            key: "branch",
            header: "Branch",
            width: "150px",
            render: (row: AttendanceImportBatch) =>
              row.branchId ? (
                <TruncatedText value={branchName(row.branchId)} />
              ) : (
                <EmptyValue />
              ),
          },
        ]
      : []),
    {
      key: "status",
      header: "Status",
      width: "120px",
      render: (row) => (
        <StatusBadge tone={importStatusTone(row.status)}>
          {row.status}
        </StatusBadge>
      ),
    },
    {
      key: "rows",
      header: "Rows",
      width: "90px",
      kind: "number",
      render: (row) => <Count value={row.dataRowCount} />,
    },
    {
      key: "applied",
      header: "Applied",
      width: "90px",
      kind: "number",
      render: (row) => <Count value={row.appliedCount} />,
    },
    {
      key: "errors",
      header: "Errors",
      width: "90px",
      kind: "number",
      render: (row) => <Count value={row.errorCount} />,
    },
    {
      key: "createdAt",
      header: "Uploaded",
      width: "160px",
      kind: "date",
      render: (row) => <CompactDateTime value={row.createdAt} />,
    },
  ];
  const resultRows: ResultRow[] = (result?.errors ?? []).map((item, index) => ({
    id: `${item.rowNumber}-${index}`,
    row: item.rowNumber,
    column: item.column ?? "",
    message: rowMessage(item.code),
  }));
  const batchResultRows: ResultRow[] = (batchRows.data?.items ?? []).map(
    (item) => ({
      id: String(item.rowNumber),
      row: item.rowNumber,
      column: item.columnName ?? "",
      message:
        item.status === "Rejected"
          ? rowMessage(item.errorCode)
          : item.status === "Skipped"
            ? "Not applied because the file was rejected."
            : "Applied",
    }),
  );
  const batchRowPages = Math.max(
    1,
    Math.ceil((batchRows.data?.total ?? 0) / 25),
  );

  return (
    <SectionCard
      compact
      title="Attendance imports"
      description="Upload one attendance date per CSV. A file with any invalid row is rejected and no record is written."
      actions={
        <ActionToolbar>
          <Button size="compact" onClick={openUpload}>
            Upload Attendance CSV
          </Button>
        </ActionToolbar>
      }
    >
      <div className={styles.importHistory}>
        <FilterToolbar label="Import history filters" className={styles.historyToolbar}>
          <FilterToolbarItem label="Import result" htmlFor="attendance-import-status">
            <DropdownSelect
              id="attendance-import-status"
              compact
              clearable
              placeholder="All import results"
              value={statusFilter}
              options={[
                { value: "Applied", label: "Applied" },
                { value: "Rejected", label: "Rejected" },
              ]}
              onChange={(value) => {
                setStatusFilter(Array.isArray(value) ? (value[0] ?? "") : value);
                setPage(1);
              }}
            />
          </FilterToolbarItem>
          {historyTotal > 0 ? (
            <div className={styles.historyCount}>
              <RecordCount count={historyTotal} />
            </div>
          ) : null}
        </FilterToolbar>
        {historySelection.error ? (
          <InlineNotice tone="error" title="Export failed">
            The import history CSV could not be exported. Refresh and try again.
          </InlineNotice>
        ) : null}
        {historySelection.allowed && historySelection.selectedCount > 0 ? (
          <div className={styles.selection} role="status">
            <span>{`${historySelection.selectedCount} selected`}</span>
            <Button
              variant="secondary"
              size="compact"
              loading={historySelection.working}
              onClick={() => void historySelection.exportCsv()}
            >
              Export selected
            </Button>
          </div>
        ) : null}
        {history.denied ? (
          <PermissionDeniedState description="Import history is outside the current authorized Branch." />
        ) : history.error && !history.data ? (
          isOffline(history.error) ? (
            <OfflineState />
          ) : (
            <ErrorState
              description="Import history could not be loaded."
              retry={history.reload}
            />
          )
        ) : history.loading && !history.data ? (
          <LoadingState title="Loading import history" />
        ) : historyTotal === 0 ? (
          <EmptyState
            title="No attendance imports"
            description={
              statusFilter
                ? "No imports match the selected result."
                : "Uploaded attendance files will appear here."
            }
          />
        ) : (
          <>
            <DataTable
              ariaLabel="Attendance import history"
              density="compact"
              stackOnNarrow={false}
              columns={historyColumns}
              rows={historyRows}
              rowKey={(row) => row.batchId}
              {...(historySelection.allowed
                ? {
                    selectedKeys: historyRows
                      .filter((row, index) => historySelection.checked(row, index))
                      .map((row) => row.batchId),
                    onToggleRow: (key: string) => {
                      const index = historyRows.findIndex((row) => row.batchId === key);
                      if (index >= 0) historySelection.toggleRow(historyRows[index], index);
                    },
                    onToggleAll: historySelection.toggleAll,
                  }
                : {})}
              loading={history.updating}
              onRowActivate={(row) => {
                setRowsPage(1);
                setOpenBatch(row);
              }}
              rowActivateLabel={(row) =>
                `Open import results for ${row.attendanceDate ?? "attendance file"}`
              }
            />
            <Pagination
              page={page}
              pageCount={Math.max(1, Math.ceil(historyTotal / pageSize))}
              onPageChange={setPage}
              pageSize={pageSize}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setPage(1);
              }}
            />
          </>
        )}
      </div>

      <Dialog
        open={uploadOpen}
        title="Upload Attendance CSV"
        description="Download the Branch template for a date, complete check-in and check-out times, then upload the file."
        size="md"
        busy={busy}
        onClose={() => setUploadOpen(false)}
        footer={
          <>
            <Button
              variant="secondary"
              size="compact"
              disabled={busy}
              onClick={() => setUploadOpen(false)}
            >
              Close
            </Button>
            <Button
              size="compact"
              disabled={!file || !uploadBranch || busy}
              loading={busy}
              onClick={() => setConfirmOpen(true)}
            >
              Upload CSV
            </Button>
          </>
        }
      >
        <div className={styles.uploadForm}>
          {branchLocked ? null : (
            <FormField label="Branch" htmlFor="attendance-upload-branch" required>
              <DropdownSelect
                id="attendance-upload-branch"
                compact
                clearable={false}
                placeholder="Select Branch"
                value={uploadBranch}
                options={(branches ?? []).map((branch) => ({
                  value: branch.id,
                  label: branch.name,
                }))}
                disabled={busy}
                onChange={(value) => {
                  setUploadBranch(Array.isArray(value) ? (value[0] ?? "") : value);
                  setResult(null);
                }}
              />
            </FormField>
          )}
          <div className={styles.templateRow}>
            <FormField label="Template date" htmlFor="attendance-template-date">
              <DateField
                id="attendance-template-date"
                compact
                value={templateDate}
                onChange={setTemplateDate}
              />
            </FormField>
            <DownloadTemplateAction
              onClick={() => {
                if (!templateDate || !uploadBranch) {
                  setTemplateError(
                    "Select a Branch and a template date before downloading.",
                  );
                  return;
                }
                setTemplateError("");
                void download(
                  api,
                  `/attendance/template?attendanceDate=${templateDate}&branchId=${encodeURIComponent(uploadBranch)}`,
                ).catch(() =>
                  setTemplateError(
                    "The template could not be downloaded. Check the Branch and date.",
                  ),
                );
              }}
            />
          </div>
          {templateError ? (
            <InlineNotice tone="error" title="Template unavailable">
              {templateError}
            </InlineNotice>
          ) : null}
          <FileUpload
            id="attendance-csv"
            compact
            label="Attendance CSV"
            accept=".csv,text/csv"
            hint="Columns: System Employee Code, Employee Name, Attendance Date, Check-in Time, Check-out Time. Limit 5 MB and 5,000 rows."
            files={files}
            busy={busy}
            onChange={selectFiles}
          />
          <ImportProgress
            phase={busy ? "importing" : "select"}
            message={
              busy
                ? "Validating and applying the complete file. If any row fails, no record is written."
                : undefined
            }
          />
          {error ? (
            <InlineNotice tone="error" title="Upload not completed">
              {error}
            </InlineNotice>
          ) : null}
          {result ? (
            <div className={styles.importResult}>
              <ImportResult
                phase={result.status === "Applied" ? "completed" : "failed"}
                message={
                  result.status === "Applied"
                    ? `${result.appliedCount} attendance records were applied.`
                    : "The complete file was rejected. No attendance record was written."
                }
              />
              {result.attendanceDate ? (
                <p className={styles.support}>
                  Attendance date <CompactDate value={result.attendanceDate} />
                  {uploadBranch ? ` · ${branchName(uploadBranch)}` : ""}
                </p>
              ) : null}
              {result.status === "Applied" ? (
                <StatusSummary
                  items={[
                    { label: "Present", count: result.presentCount, tone: "success" },
                    { label: "Late", count: result.lateCount, tone: "warning" },
                    { label: "Absent", count: result.absentCount, tone: "danger" },
                  ]}
                />
              ) : null}
              {resultRows.length ? (
                <DataTable
                  ariaLabel="Attendance upload row results"
                  density="compact"
                  columns={RESULT_COLUMNS}
                  rows={resultRows}
                  rowKey={(row) => row.id}
                />
              ) : null}
            </div>
          ) : null}
        </div>
      </Dialog>

      <ConfirmationDialog
        open={confirmOpen}
        title="Upload attendance"
        confirmLabel="Upload CSV"
        busy={busy}
        onClose={() => setConfirmOpen(false)}
        onConfirm={() => void send()}
      >
        <p className={styles.support}>
          This applies {file ? file.name : "the selected file"} for{" "}
          {branchName(uploadBranch) || "the selected Branch"}. Employees without
          a row are marked Absent. A date that is already applied cannot be
          overwritten, and any invalid row rejects the complete file.
        </p>
      </ConfirmationDialog>

      <Drawer
        open={Boolean(openBatch)}
        title="Import results"
        size="wide"
        onClose={() => setOpenBatch(null)}
      >
        {openBatch ? (
          <div className={styles.importResult}>
            <p className={`${styles.support} ${styles.drawerMeta}`}>
              {openBatch.attendanceDate ? (
                <CompactDate value={openBatch.attendanceDate} />
              ) : (
                "Attendance file"
              )}
              {openBatch.branchId ? ` · ${branchName(openBatch.branchId)}` : ""}
              {" · Uploaded "}
              <CompactDateTime value={openBatch.createdAt} />
            </p>
            <div className={styles.batchSummary}>
              <StatusBadge tone={importStatusTone(openBatch.status)}>
                {openBatch.status}
              </StatusBadge>
              <StatusSummary
                items={[
                  { label: "Rows", count: openBatch.dataRowCount ?? 0, tone: "neutral" },
                  { label: "Applied", count: openBatch.appliedCount ?? 0, tone: "success" },
                  { label: "Errors", count: openBatch.errorCount ?? 0, tone: "danger" },
                ]}
              />
            </div>
            {rowsSelection.error ? (
              <InlineNotice tone="error" title="Export failed">
                The row results CSV could not be exported. Refresh and try again.
              </InlineNotice>
            ) : null}
            {rowsSelection.allowed && rowsSelection.selectedCount > 0 ? (
              <div className={styles.selection} role="status">
                <span>{`${rowsSelection.selectedCount} selected`}</span>
                <Button
                  variant="secondary"
                  size="compact"
                  loading={rowsSelection.working}
                  onClick={() => void rowsSelection.exportCsv()}
                >
                  Export selected
                </Button>
              </div>
            ) : null}
            {batchRows.error && !batchRows.data ? (
              <ErrorState
                description="Row results could not be loaded."
                retry={batchRows.reload}
              />
            ) : batchRows.loading && !batchRows.data ? (
              <LoadingState title="Loading row results" />
            ) : batchResultRows.length === 0 ? (
              <EmptyState
                title="No row results"
                description="This import retained no row-level results."
              />
            ) : (
              <>
                <DataTable
                  ariaLabel="Import row results"
                  density="compact"
                  columns={RESULT_COLUMNS}
                  rows={batchResultRows}
                  rowKey={(row) => row.id}
                  {...(rowsSelection.allowed
                    ? {
                        selectedKeys: rawBatchRows
                          .filter((row, index) => rowsSelection.checked(row, index))
                          .map((row) => String(row.rowNumber)),
                        onToggleRow: (key: string) => {
                          const index = rawBatchRows.findIndex(
                            (row) => String(row.rowNumber) === key,
                          );
                          if (index >= 0) rowsSelection.toggleRow(rawBatchRows[index], index);
                        },
                        onToggleAll: rowsSelection.toggleAll,
                      }
                    : {})}
                  loading={batchRows.updating}
                />
                <Pagination
                  page={rowsPage}
                  pageCount={batchRowPages}
                  onPageChange={setRowsPage}
                />
              </>
            )}
          </div>
        ) : null}
      </Drawer>
    </SectionCard>
  );
}
