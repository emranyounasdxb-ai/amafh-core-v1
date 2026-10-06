import { useMemo, useRef, useState } from "react";
import {
  Button,
  CompactDateTime,
  ConfirmationDialog,
  DataTable,
  DownloadTemplateAction,
  EmptyState,
  EmptyValue,
  ErrorState,
  FileUpload,
  ImportProgress,
  ImportResult,
  InlineNotice,
  LoadingState,
  NoResultsState,
  OfflineState,
  PageContainer,
  PageHeader,
  Pagination,
  PermissionDeniedState,
  RecordCount,
  SearchFilterToolbar,
  SectionCard,
  StatusBadge,
  StatusSummary,
  TruncatedText,
  UnavailableState,
  type AppliedFilter,
  type DataTableColumn,
} from "../../../design-system";
import { canImportBankStages } from "../../../access";
import { download } from "../../../app/api/download";
import type { Page } from "../../../app/api/models";
import { ApiFailure } from "../../../app/api/http";
import { useResource } from "../../../app/api/useResource";
import { useSession } from "../../../app/session/useSession";
import {
  VALIDITY_OPTIONS,
  bankStageBatchTone,
  bankStageCategoryTone,
  canConfirmImport,
  categoryOptions,
  formatFileSize,
  mapBankStageRows,
  matchesBankStageSearch,
  matchesValidityFilter,
  readableValue,
  type BankStageBatchDetail,
  type BankStageHistoryItem,
  type BankStageResultRow,
} from "./bankStageUpdatesPresentation";
import styles from "./BankStageUpdatesPage.module.css";

function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

function Cell({ value }: { value: string }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

function DateValue({ value }: { value: string }) {
  return (
    <span className={styles.dateValue}>
      <CompactDateTime value={value} />
    </span>
  );
}

export function BankStageUpdatesPage({
  batchId,
  openBatch,
}: {
  batchId?: string;
  openBatch: (id?: string) => void;
}) {
  const { api, session } = useSession();
  const allowed = Boolean(session && canImportBankStages(session));
  const [files, setFiles] = useState<FileList | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState<"select" | "validating" | "importing">(
    "select",
  );
  const [templateError, setTemplateError] = useState("");
  const [commandError, setCommandError] = useState("");
  const [commandCode, setCommandCode] = useState("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [validity, setValidity] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState(25);
  const [refresh, setRefresh] = useState(0);
  const validateKey = useRef(crypto.randomUUID());
  const applyKey = useRef(crypto.randomUUID());
  const file = files?.[0] ?? null;
  const batch = useResource<BankStageBatchDetail>(
    allowed && batchId
      ? `/case-imports/bank-stage/${encodeURIComponent(batchId)}`
      : null,
    refresh,
  );
  const history = useResource<Page<BankStageHistoryItem>>(
    allowed
      ? `/case-imports/bank-stage?page=${historyPage}&pageSize=${historyPageSize}`
      : null,
    refresh,
  );

  const rows = useMemo(
    () => (batch.data ? mapBankStageRows(batch.data.rowResults) : []),
    [batch.data],
  );
  const filtered = useMemo(
    () =>
      rows.filter(
        (row) =>
          matchesValidityFilter(row, validity) &&
          (!category || row.category === category) &&
          matchesBankStageSearch(row, search),
      ),
    [category, rows, search, validity],
  );
  const visibleRows = filtered.slice((page - 1) * pageSize, page * pageSize);
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const options = categoryOptions(rows);
  const detail = batch.data;
  const confirmReady = canConfirmImport(detail) && !busy && allowed;
  const historyRows = history.data?.items ?? [];
  const historyTotal = history.data?.total ?? 0;
  const historyPageCount = Math.max(
    1,
    Math.ceil(historyTotal / historyPageSize),
  );

  const resultColumns: DataTableColumn<BankStageResultRow>[] = [
    { key: "rowNumber", header: "Row", kind: "number", width: "72px" },
    {
      key: "internalCaseId",
      header: "Case ID",
      kind: "text",
      render: (row) => <Cell value={row.internalCaseId} />,
    },
    {
      key: "bankCaseNumber",
      header: "Bank Case Number",
      kind: "text",
      render: (row) => <Cell value={row.bankCaseNumber} />,
    },
    {
      key: "productLabel",
      header: "Product",
      kind: "text",
      render: (row) => <Cell value={row.productLabel} />,
    },
    {
      key: "currentStage",
      header: "Current stage",
      kind: "text",
      render: (row) => <Cell value={row.currentStage} />,
    },
    {
      key: "requestedStage",
      header: "Requested stage",
      kind: "text",
      render: (row) => <Cell value={row.requestedStage} />,
    },
    {
      key: "category",
      header: "Result",
      kind: "text",
      render: (row) => (
        <StatusBadge tone={bankStageCategoryTone(row.category)}>
          {row.category}
        </StatusBadge>
      ),
    },
    {
      key: "message",
      header: "Message",
      kind: "text",
      render: (row) => <Cell value={row.message} />,
    },
  ];

  const historyColumns: DataTableColumn<BankStageHistoryItem>[] = [
    {
      key: "fileName",
      header: "File",
      kind: "text",
      render: (row) => <Cell value={readableValue(row.fileName)} />,
    },
    {
      key: "uploaderName",
      header: "Uploader",
      kind: "text",
      render: (row) => (
        <Cell value={readableValue(row.uploaderName) || "Assigned employee"} />
      ),
    },
    {
      key: "createdAt",
      header: "Created",
      kind: "datetime",
      render: (row) =>
        row.createdAt ? <DateValue value={row.createdAt} /> : <EmptyValue />,
    },
    {
      key: "validationStatus",
      header: "Validation",
      kind: "text",
      render: (row) => (
        <StatusBadge tone={bankStageBatchTone(row.validationStatus)}>
          {row.validationStatus}
        </StatusBadge>
      ),
    },
    {
      key: "status",
      header: "Import",
      kind: "text",
      render: (row) => (
        <StatusBadge tone={bankStageBatchTone(row.status)}>
          {row.status === "Validated" ? "Not applied" : row.status}
        </StatusBadge>
      ),
    },
    {
      key: "totalCount",
      header: "Rows",
      kind: "number",
    },
    {
      key: "validCount",
      header: "Valid",
      kind: "number",
    },
    {
      key: "invalidCount",
      header: "Invalid",
      kind: "number",
    },
    {
      key: "appliedCount",
      header: "Updated",
      kind: "number",
    },
  ];

  const resetResults = () => {
    setConfirmOpen(false);
    setCommandError("");
    setCommandCode("");
    setCategory("");
    setValidity("");
    setSearch("");
    setPage(1);
    validateKey.current = crypto.randomUUID();
    applyKey.current = crypto.randomUUID();
  };

  const selectFiles = (next: FileList | null) => {
    setFiles(next);
    resetResults();
    if (batchId) openBatch();
  };

  const validateFile = async () => {
    if (!file || busy) return;
    setBusy(true);
    setPhase("validating");
    setCommandError("");
    setCommandCode("");
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await api.request<BankStageBatchDetail>(
        "/case-imports/bank-stage/validations",
        {
          method: "POST",
          body,
          headers: { "Idempotency-Key": validateKey.current },
        },
      );
      setRefresh((value) => value + 1);
      openBatch(response.batchId);
    } catch (failure) {
      const error = failure instanceof ApiFailure ? failure : null;
      setCommandCode(error?.code ?? "");
      setCommandError(
        error?.message ||
          (failure instanceof Error ? failure.message : "Validation failed"),
      );
    } finally {
      setBusy(false);
      setPhase("select");
    }
  };

  const applyBatch = async () => {
    if (!detail || !confirmReady) return;
    setBusy(true);
    setPhase("importing");
    setCommandError("");
    setCommandCode("");
    try {
      await api.request<BankStageBatchDetail>(
        `/case-imports/bank-stage/${encodeURIComponent(detail.batchId)}/apply`,
        {
          method: "POST",
          headers: { "Idempotency-Key": applyKey.current },
        },
      );
      setConfirmOpen(false);
      setRefresh((value) => value + 1);
    } catch (failure) {
      const error = failure instanceof ApiFailure ? failure : null;
      setCommandCode(error?.code ?? "");
      setCommandError(
        error?.message ||
          (failure instanceof Error ? failure.message : "Import failed"),
      );
      setConfirmOpen(false);
    } finally {
      setBusy(false);
      setPhase("select");
    }
  };

  if (!session || !allowed) {
    return (
      <PageContainer>
        <PermissionDeniedState description="Bank Stage Updates are outside the current authorized scope." />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <div className={styles.page} aria-busy={busy || batch.updating}>
        <PageHeader
          title="Bank Stage Updates"
          subtitle="Validate the complete Bank stage CSV, review the retained result, then confirm the all-or-nothing import."
          status={detail?.status}
          statusTone={
            detail?.status ? bankStageBatchTone(detail.status) : "neutral"
          }
        />

        <SectionCard
          compact
          title="Upload"
          description="Each Case is checked against its own assigned Pipeline. Credit Card and Personal Finance stages stay separate."
          actions={
            <DownloadTemplateAction
              onClick={() => {
                setTemplateError("");
                void download(api, "/case-imports/bank-stage/template").catch(
                  (failure: unknown) =>
                    setTemplateError(
                      failure instanceof Error
                        ? failure.message
                        : "Template download failed",
                    ),
                );
              }}
            />
          }
        >
          <div className={styles.upload}>
            <FileUpload
              id="bank-stage-csv"
              compact
              label="Bank stage CSV"
              accept=".csv,text/csv"
              hint="Required columns: Bank Case Number, Latest Stage, Bank Remarks. Limit 5 MB and 5,000 data rows."
              files={files}
              busy={busy}
              onChange={selectFiles}
            />
            {file ? (
              <p className={styles.confirmCopy}>
                {file.name} · {formatFileSize(file.size)}
              </p>
            ) : null}
            <div className={styles.uploadActions}>
              <Button
                size="compact"
                disabled={!file || busy}
                loading={phase === "validating"}
                onClick={() => void validateFile()}
              >
                Validate file
              </Button>
              <Button
                size="compact"
                disabled={!confirmReady}
                loading={phase === "importing"}
                onClick={() => setConfirmOpen(true)}
              >
                Confirm import
              </Button>
            </div>
            <ImportProgress
              phase={
                phase === "validating"
                  ? "validating"
                  : phase === "importing"
                    ? "importing"
                    : "select"
              }
              message={
                phase === "validating"
                  ? "Validating the complete file. No Case is updated."
                  : phase === "importing"
                    ? "Applying the retained batch. If any row fails, no Case is updated."
                    : undefined
              }
            />
          </div>
        </SectionCard>

        {templateError ? (
          <InlineNotice tone="error" title="Template unavailable">
            {templateError}
          </InlineNotice>
        ) : null}
        {commandError ? (
          <InlineNotice
            tone={commandCode === "DUPLICATE_UPLOAD" ? "warning" : "error"}
            title={
              commandCode === "DUPLICATE_UPLOAD"
                ? "Previously processed import"
                : commandCode === "BATCH_INVALID"
                  ? "Batch cannot be imported"
                  : "Request failed"
            }
          >
            {commandError}
          </InlineNotice>
        ) : null}

        {batch.denied && batchId ? (
          <UnavailableState title="Record unavailable" />
        ) : batch.error && !batch.data ? (
          isOffline(batch.error) ? (
            <OfflineState />
          ) : (
            <ErrorState description={batch.error} retry={batch.reload} />
          )
        ) : batch.loading && !batch.data && batchId ? (
          <LoadingState title="Loading validation result" />
        ) : detail ? (
          <>
            <SectionCard compact title="Review" className={styles.summary}>
              <StatusSummary
                items={[
                  {
                    label: "Total",
                    count: detail.totalCount,
                    tone: "neutral",
                  },
                  {
                    label: "Valid",
                    count: detail.validCount,
                    tone: "success",
                  },
                  {
                    label: "Invalid",
                    count: detail.invalidCount,
                    tone: "danger",
                  },
                  {
                    label: "Eligible",
                    count: detail.eligibleCount,
                    tone: "info",
                  },
                  ...(detail.status === "Applied" ||
                  detail.status === "Rejected"
                    ? [
                        {
                          label: "Updated",
                          count: detail.appliedCount,
                          tone: "success" as const,
                        },
                        {
                          label: "Rejected",
                          count: detail.invalidCount,
                          tone: "danger" as const,
                        },
                        {
                          label: "Unchanged",
                          count: detail.unchangedCount,
                          tone: "neutral" as const,
                        },
                      ]
                    : []),
                ]}
              />
              <div className={styles.metaLine}>
                Validation {detail.validationStatus || detail.status}
                {detail.fileName ? ` · ${readableValue(detail.fileName)}` : ""}
                {detail.createdAt ? (
                  <>
                    {" · "}
                    <DateValue value={detail.createdAt} />
                  </>
                ) : null}
              </div>
              {detail.status === "Applied" || detail.status === "Rejected" ? (
                <ImportResult
                  phase={detail.status === "Applied" ? "completed" : "failed"}
                  message={
                    detail.status === "Applied"
                      ? `${detail.appliedCount} Case stages were updated.`
                      : "The complete batch was rejected. No Case was updated."
                  }
                />
              ) : (
                <p className={styles.confirmCopy}>
                  {detail.eligibleCount} Cases are eligible. Confirm import to
                  update stages. A rejected batch updates zero Cases.
                </p>
              )}
            </SectionCard>

            <SearchFilterToolbar
              className={styles.toolbar}
              searchId="bank-stage-result-search"
              searchLabel="Search results"
              searchValue={search}
              onSearchChange={(value) => {
                setSearch(value);
                setPage(1);
              }}
              searchPlaceholder="Search by Case ID, Bank Case Number, stage or result"
              filters={[
                {
                  id: "bank-stage-validity",
                  label: "Rows",
                  value: validity,
                  options: VALIDITY_OPTIONS,
                  onChange: (value) => {
                    setValidity(value === "all" ? "" : value);
                    setPage(1);
                  },
                },
                ...(options.length
                  ? [
                      {
                        id: "bank-stage-result-category",
                        label: "Result",
                        value: category,
                        options: [
                          { value: "", label: "All results" },
                          ...options,
                        ],
                        onChange: (value: string) => {
                          setCategory(value === "all" ? "" : value);
                          setPage(1);
                        },
                      },
                    ]
                  : []),
              ]}
              applied={[
                ...(validity
                  ? [
                      {
                        id: "validity",
                        label: "Rows",
                        field: "Rows",
                        value:
                          VALIDITY_OPTIONS.find(
                            (item) => item.value === validity,
                          )?.label ?? validity,
                        onRemove: () => {
                          setValidity("");
                          setPage(1);
                        },
                      } satisfies AppliedFilter,
                    ]
                  : []),
                ...(category
                  ? [
                      {
                        id: "category",
                        label: "Result",
                        field: "Result",
                        value: category,
                        onRemove: () => {
                          setCategory("");
                          setPage(1);
                        },
                      } satisfies AppliedFilter,
                    ]
                  : []),
              ]}
              onClearFilters={
                validity || category
                  ? () => {
                      setValidity("");
                      setCategory("");
                      setPage(1);
                    }
                  : undefined
              }
              disabled={busy}
            />

            <SectionCard compact className={styles.table}>
              <RecordCount count={filtered.length} />
              {filtered.length === 0 ? (
                <NoResultsState
                  title="No matching rows"
                  description="Nothing in this result matches the current search or filter."
                />
              ) : (
                <>
                  <DataTable
                    ariaLabel="Bank stage validation results"
                    density="compact"
                    columns={resultColumns}
                    rows={visibleRows}
                    rowKey={(row) => row.id}
                  />
                  <Pagination
                    page={page}
                    pageCount={pageCount}
                    onPageChange={setPage}
                    pageSize={pageSize}
                    onPageSizeChange={(size) => {
                      setPageSize(size);
                      setPage(1);
                    }}
                  />
                </>
              )}
            </SectionCard>
          </>
        ) : (
          <EmptyState
            title="No validation result yet"
            description="Choose a CSV and validate it. Import stays unavailable until every row is accepted."
          />
        )}

        <SectionCard
          compact
          title="Import history"
          description="Retained validation and import batches uploaded by the current account."
        >
          {history.denied ? (
            <PermissionDeniedState description="Import history is outside the current authorized scope." />
          ) : history.error && !history.data ? (
            isOffline(history.error) ? (
              <OfflineState />
            ) : (
              <ErrorState description={history.error} retry={history.reload} />
            )
          ) : history.loading && !history.data ? (
            <LoadingState title="Loading import history" />
          ) : historyTotal === 0 ? (
            <EmptyState
              title="No retained batches"
              description="Validated and imported files will appear here."
            />
          ) : (
            <>
              <RecordCount count={historyTotal} />
              <DataTable
                ariaLabel="Bank stage import history"
                density="compact"
                columns={historyColumns}
                rows={historyRows}
                rowKey={(row) => row.batchId}
                onRowActivate={(row) => openBatch(row.batchId)}
                rowActivateLabel={(row) =>
                  `Open ${readableValue(row.fileName) || "import result"}`
                }
              />
              <Pagination
                page={historyPage}
                pageCount={historyPageCount}
                onPageChange={setHistoryPage}
                pageSize={historyPageSize}
                onPageSizeChange={(size) => {
                  setHistoryPageSize(size);
                  setHistoryPage(1);
                }}
              />
            </>
          )}
        </SectionCard>
      </div>

      <ConfirmationDialog
        open={confirmOpen}
        title="Confirm import"
        confirmLabel="Confirm import"
        busy={busy}
        onClose={() => setConfirmOpen(false)}
        onConfirm={() => void applyBatch()}
      >
        <p className={styles.confirmCopy}>
          This updates {detail?.eligibleCount ?? 0} Case stages
          {file
            ? ` from ${file.name}`
            : detail?.fileName
              ? ` from ${readableValue(detail.fileName)}`
              : ""}
          . The retained batch is all-or-nothing. If any Case, Pipeline, stage,
          or permission is no longer valid, the complete batch is rejected and
          no Case is updated.
        </p>
      </ConfirmationDialog>
    </PageContainer>
  );
}
