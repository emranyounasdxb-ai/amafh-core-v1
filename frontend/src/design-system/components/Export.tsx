import type { ReactNode } from "react";
import { DsIcon } from "../icons";
import { Button, type ButtonSize } from "./Button";
import { Dialog } from "./Dialog";
import { IconButton } from "./IconButton";
import { Menu, type MenuItem } from "./Menu";
import { StatusBadge } from "./StatusBadge";

export type ExportFormat = "csv" | "pdf";
export type ExportScope = "selected" | "filtered" | "all";
export type ExportStatus = "idle" | "preparing" | "success" | "error";

export type ExportOption = {
  id: string;
  format: ExportFormat;
  scope: ExportScope;
  label: string;
  description?: string;
  disabled?: boolean;
};

export function ExportProgress({
  status,
  message,
}: {
  status: ExportStatus;
  message?: ReactNode;
}) {
  if (status === "idle") return null;
  return (
    <p className={`ds-export-status ds-export-status--${status}`} role="status">
      {status === "preparing" ? <span className="ds-spinner" /> : null}
      {message ??
        (status === "preparing"
          ? "Preparing export…"
          : status === "success"
            ? "Export ready."
            : "Export failed.")}
    </p>
  );
}

export function ExportResult({
  status,
  fileName,
  error,
}: {
  status: ExportStatus;
  fileName?: string;
  error?: ReactNode;
}) {
  if (status === "success") {
    return (
      <div className="ds-export-result">
        <StatusBadge tone="success">Completed</StatusBadge>
        <span>{fileName ?? "Export file is ready."}</span>
      </div>
    );
  }
  if (status === "error") {
    return (
      <div className="ds-export-result">
        <StatusBadge tone="danger">Failed</StatusBadge>
        <span>{error ?? "The export could not be prepared."}</span>
      </div>
    );
  }
  return null;
}

export function ExportOption({
  option,
  onSelect,
}: {
  option: ExportOption;
  onSelect?: (option: ExportOption) => void;
}) {
  return (
    <button
      type="button"
      className="ds-export-option"
      disabled={option.disabled}
      onClick={() => onSelect?.(option)}
    >
      <DsIcon name={option.format === "csv" ? "csv" : "pdf"} size={16} />
      <span className="ds-menu__copy">
        <strong>{option.label}</strong>
        {option.description ? <em>{option.description}</em> : null}
      </span>
    </button>
  );
}

export function ExportMenu({
  items,
  trigger,
  label = "Export options",
}: {
  items: MenuItem[];
  trigger: ReactNode;
  label?: string;
}) {
  return (
    <Menu label={label} align="bottom-end" items={items} trigger={trigger} />
  );
}

export function ExportButton({
  label,
  selectedCount = 0,
  iconOnly = false,
  loading = false,
  disabled,
  size = "standard",
  options,
  onSelect,
  onClick,
}: {
  label?: string;
  selectedCount?: number;
  iconOnly?: boolean;
  loading?: boolean;
  disabled?: boolean;
  size?: ButtonSize;
  options?: ExportOption[];
  onSelect?: (option: ExportOption) => void;
  onClick?: () => void;
}) {
  const text =
    label ??
    (selectedCount > 0 ? `Export selected (${selectedCount})` : "Export");
  const items: MenuItem[] = (options ?? []).map((option) => ({
    id: option.id,
    label: option.label,
    description: option.description,
    disabled: option.disabled,
    icon: <DsIcon name={option.format === "csv" ? "csv" : "pdf"} size={16} />,
    onSelect: () => onSelect?.(option),
  }));
  const trigger = iconOnly ? (
    <IconButton
      label={text}
      variant="secondary"
      size={size}
      disabled={disabled}
      loading={loading}
    >
      <DsIcon name="download" size={16} />
    </IconButton>
  ) : (
    <Button
      variant="secondary"
      size={size}
      disabled={disabled}
      loading={loading}
      onClick={items.length ? undefined : onClick}
    >
      <DsIcon name="download" size={16} />
      {text}
    </Button>
  );
  if (!items.length) return trigger;
  return <ExportMenu items={items} trigger={trigger} />;
}

export function ExportDialog({
  open,
  onClose,
  status = "idle",
  fileName,
  error,
  children,
}: {
  open: boolean;
  onClose: () => void;
  status?: ExportStatus;
  fileName?: string;
  error?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="sm"
      title="Export"
      description="Choose a format. Feature pages own the export command."
      footer={
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
      }
    >
      {children}
      <ExportProgress status={status} />
      <ExportResult status={status} fileName={fileName} error={error} />
    </Dialog>
  );
}
