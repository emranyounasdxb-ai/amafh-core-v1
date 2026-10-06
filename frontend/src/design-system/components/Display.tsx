import { useState, type ReactNode } from "react";
import { DsIcon } from "../icons";
import { CompactDate, CompactDateTime } from "./CompactDate";
import { MonetaryAmount } from "./MonetaryAmount";
import { Button } from "./Button";
import { ExportButton } from "./Export";
import { IconButton } from "./IconButton";
import { Tooltip } from "./Tooltip";
import { cx } from "../lib/cx";

export function TruncatedText({ value }: { value: string }) {
  return (
    <Tooltip content={value}>
      <span className="ds-truncate">{value}</span>
    </Tooltip>
  );
}

export function EmptyValue() {
  return <span className="ds-empty-value">—</span>;
}

export function FormatValue({
  value,
  kind = "text",
}: {
  value?: string | number | null;
  kind?: "text" | "currency" | "percent" | "date" | "datetime";
}) {
  if (value == null || value === "") return <EmptyValue />;
  if (kind === "currency") return <MonetaryAmount value={value} />;
  if (kind === "percent") return <span className="ds-numeric">{value}%</span>;
  if (kind === "date") return <CompactDate value={value} />;
  if (kind === "datetime") return <CompactDateTime value={value} />;
  return <span>{value}</span>;
}

export function ProgressBar({
  value,
  label,
  max = 100,
  tone = "brand",
}: {
  value: number;
  label: string;
  max?: number;
  tone?: "brand" | "success" | "warning" | "danger";
}) {
  const pct = max <= 0 ? 0 : (value / max) * 100;
  const clamped = Math.max(0, Math.min(100, pct));
  return (
    <div
      className={cx("ds-progress", `ds-progress--${tone}`)}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={Math.round(value)}
    >
      <span style={{ width: `${clamped}%` }} />
    </div>
  );
}

export function Tag({
  children,
  onRemove,
}: {
  children: ReactNode;
  onRemove?: () => void;
}) {
  return (
    <span className="ds-chip">
      {children}
      {onRemove ? (
        <button type="button" aria-label="Remove" onClick={onRemove}>
          ×
        </button>
      ) : null}
    </span>
  );
}

export function CopyButton({
  value,
  label = "Copy",
}: {
  value: string;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <IconButton
      label={copied ? "Copied" : label}
      variant="ghost"
      size="compact"
      onClick={async () => {
        await navigator.clipboard.writeText(value);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1200);
      }}
    >
      <DsIcon name="copy" size={16} />
    </IconButton>
  );
}

export function FileItem({
  name,
  meta,
  onDownload,
}: {
  name: string;
  meta?: string;
  onDownload?: () => void;
}) {
  return (
    <div className="ds-file-item">
      <div>
        <strong>{name}</strong>
        {meta ? <p>{meta}</p> : null}
      </div>
      {onDownload ? (
        <ExportButton label="Download" size="compact" onClick={onDownload} />
      ) : null}
    </div>
  );
}

export function PreviewPlaceholder({
  title = "Preview unavailable",
  description = "A document preview will appear here when a file is selected.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div className="ds-preview">
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

export function ListItem({
  title,
  meta,
  action,
}: {
  title: ReactNode;
  meta?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="ds-list-item">
      <div>
        <strong>{title}</strong>
        {meta ? <p>{meta}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function SearchResultsList({
  items,
  empty,
}: {
  items: { id: string; title: string; meta?: string; onSelect?: () => void }[];
  empty?: ReactNode;
}) {
  if (!items.length) return <>{empty}</>;
  return (
    <div className="ds-result-list">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className="ds-list-item"
          onClick={item.onSelect}
        >
          <span>
            <strong>{item.title}</strong>
            {item.meta ? <p>{item.meta}</p> : null}
          </span>
        </button>
      ))}
    </div>
  );
}

export function ButtonGroup({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cx("ds-button-group", className)}>{children}</div>;
}

export function PreviousNext({
  onPrevious,
  onNext,
  previousDisabled,
  nextDisabled,
}: {
  onPrevious: () => void;
  onNext: () => void;
  previousDisabled?: boolean;
  nextDisabled?: boolean;
}) {
  return (
    <ButtonGroup>
      <Button
        variant="secondary"
        size="compact"
        disabled={previousDisabled}
        onClick={onPrevious}
      >
        Previous
      </Button>
      <Button
        variant="secondary"
        size="compact"
        disabled={nextDisabled}
        onClick={onNext}
      >
        Next
      </Button>
    </ButtonGroup>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return <span className="ds-spinner" role="status" aria-label={label} />;
}
