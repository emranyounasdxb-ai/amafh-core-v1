import type { ReactNode } from "react";
import { DsIcon } from "../icons";
import { Button } from "./Button";
import { Dialog } from "./Dialog";
import { IconButton } from "./IconButton";
import { StatusBadge, type StatusTone } from "./StatusBadge";
import { cx } from "../lib/cx";
import { DataTable } from "./DataTable";

export type ImportPhase =
  | "select"
  | "selected"
  | "validating"
  | "warnings"
  | "errors"
  | "ready"
  | "importing"
  | "partial"
  | "completed"
  | "failed";

export type ImportPreviewRow = {
  id: string;
  values: string[];
  status: "valid" | "warning" | "error";
  message?: string;
};

export function DownloadTemplateAction({
  onClick,
  label = "Download CSV template",
}: {
  onClick: () => void;
  label?: string;
}) {
  return (
    <Button variant="ghost" size="compact" onClick={onClick}>
      <DsIcon name="csv" size={16} />
      {label}
    </Button>
  );
}

export function ImportButton({
  label = "Import",
  onClick,
  disabled,
}: {
  label?: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <Button variant="secondary" onClick={onClick} disabled={disabled}>
      <DsIcon name="upload" size={16} />
      {label}
    </Button>
  );
}

export function ImportDropzone({
  accept = ".csv",
  disabled,
  onFiles,
  hint = "CSV up to 5 MB.",
}: {
  accept?: string;
  disabled?: boolean;
  onFiles: (files: FileList | null) => void;
  hint?: string;
}) {
  return (
    <label
      className={cx(
        "ds-import-dropzone",
        disabled && "ds-import-dropzone--disabled",
      )}
    >
      <DsIcon name="upload" size={20} />
      <span>
        <strong>Drop a CSV file</strong>
        <em>{hint}</em>
      </span>
      <span className="ds-file-upload__action">Choose file</span>
      <input
        className="ds-sr-only"
        type="file"
        accept={accept}
        disabled={disabled}
        onChange={(event) => onFiles(event.target.files)}
      />
    </label>
  );
}

export function ImportFileSummary({
  name,
  size,
  onRemove,
}: {
  name: string;
  size?: string;
  onRemove?: () => void;
}) {
  return (
    <div className="ds-import-file">
      <DsIcon name="csv" size={16} />
      <div>
        <strong>{name}</strong>
        {size ? <span>{size}</span> : null}
      </div>
      {onRemove ? (
        <IconButton
          label="Remove file"
          variant="ghost"
          size="compact"
          onClick={onRemove}
        >
          <DsIcon name="close" size={16} />
        </IconButton>
      ) : null}
    </div>
  );
}

export function ImportValidationSummary({
  valid = 0,
  warnings = 0,
  errors = 0,
}: {
  valid?: number;
  warnings?: number;
  errors?: number;
}) {
  return (
    <div className="ds-import-summary">
      <StatusBadge tone="success">{valid} valid</StatusBadge>
      <StatusBadge tone="warning">{warnings} warnings</StatusBadge>
      <StatusBadge tone="danger">{errors} errors</StatusBadge>
    </div>
  );
}

export function ImportPreviewTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: ImportPreviewRow[];
}) {
  const tone: Record<ImportPreviewRow["status"], StatusTone> = {
    valid: "success",
    warning: "warning",
    error: "danger",
  };
  return (
    <div className="ds-import-preview">
      <DataTable
        ariaLabel="Import preview"
        tableId="import-preview"
        stackOnNarrow={false}
        rows={rows}
        rowKey={(row) => row.id}
        columns={[
          ...columns.map((column, index) => ({
            key: `value-${index}`,
            header: column,
            render: (row: ImportPreviewRow) => row.values[index],
          })),
          {
            key: "status",
            header: "Status",
            width: "240px",
            render: (row: ImportPreviewRow) => (
              <div>
                <StatusBadge tone={tone[row.status]}>{row.status}</StatusBadge>
                {row.message ? (
                  <p className="ds-field__hint">{row.message}</p>
                ) : null}
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}

export function ImportProgress({
  phase,
  message,
}: {
  phase: ImportPhase;
  message?: ReactNode;
}) {
  if (phase !== "validating" && phase !== "importing") return null;
  return (
    <p className="ds-export-status" role="status">
      <span className="ds-spinner" />
      {message ?? (phase === "validating" ? "Validating file…" : "Importing…")}
    </p>
  );
}

export function ImportResult({
  phase,
  message,
}: {
  phase: ImportPhase;
  message?: ReactNode;
}) {
  if (phase !== "completed" && phase !== "partial" && phase !== "failed") {
    return null;
  }
  const tone =
    phase === "completed"
      ? "success"
      : phase === "partial"
        ? "warning"
        : "danger";
  const label =
    phase === "completed"
      ? "Completed"
      : phase === "partial"
        ? "Partial"
        : "Failed";
  return (
    <div className="ds-export-result">
      <StatusBadge tone={tone}>{label}</StatusBadge>
      <span>
        {message ??
          (phase === "completed"
            ? "Authorized rows were imported."
            : phase === "partial"
              ? "Some rows were imported. Remaining rows need correction."
              : "The import could not be completed.")}
      </span>
    </div>
  );
}

export function ImportDialog({
  open,
  onClose,
  phase = "select",
  onImport,
  onFiles,
  onRemoveFile,
  onDownloadTemplate,
  fileName,
  fileSize,
  valid,
  warnings,
  errors,
  columns,
  rows,
  accept = ".csv,text/csv",
  ready = false,
}: {
  open: boolean;
  onClose: () => void;
  phase?: ImportPhase;
  onImport: () => void;
  onFiles: (files: FileList | null) => void;
  onRemoveFile?: () => void;
  onDownloadTemplate?: () => void;
  fileName?: string;
  fileSize?: string;
  valid?: number;
  warnings?: number;
  errors?: number;
  columns?: string[];
  rows?: ImportPreviewRow[];
  accept?: string;
  ready?: boolean;
}) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="xl"
      title="Import records"
      description="Accepted type: CSV. Maximum 5 MB. Feature pages own validation and commands."
      busy={phase === "importing" || phase === "validating"}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={onImport} disabled={!ready || phase === "importing"}>
            Import
          </Button>
        </>
      }
    >
      <div className="ds-import-dialog">
        {onDownloadTemplate ? (
          <DownloadTemplateAction onClick={onDownloadTemplate} />
        ) : null}
        {fileName ? (
          <ImportFileSummary
            name={fileName}
            size={fileSize}
            onRemove={onRemoveFile}
          />
        ) : (
          <ImportDropzone accept={accept} onFiles={onFiles} />
        )}
        <ImportProgress phase={phase} />
        {fileName ? (
          <ImportValidationSummary
            valid={valid}
            warnings={warnings}
            errors={errors}
          />
        ) : null}
        {columns && rows?.length ? (
          <ImportPreviewTable columns={columns} rows={rows} />
        ) : null}
        <ImportResult phase={phase} />
      </div>
    </Dialog>
  );
}
