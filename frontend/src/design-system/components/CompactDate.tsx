import { cx } from "../lib/cx";
import {
  formatDateOnly,
  formatDateOnlyFull,
  formatMonthYear,
  formatMonthYearFull,
  isDateOnly,
} from "../lib/dateOnly";
import {
  formatDubaiTimestamp,
  formatDubaiTimestampFull,
} from "../lib/dubaiTime";
import { FullValueTooltip } from "./FullValueTooltip";

function DateFace({
  compact,
  full,
  className,
}: {
  compact: string;
  full: string;
  className?: string;
}) {
  return (
    <FullValueTooltip content={full}>
      <span className={cx("ds-date", className)} aria-label={full}>
        {compact}
      </span>
    </FullValueTooltip>
  );
}

export function CompactDate({
  value,
  className,
}: {
  value: unknown;
  className?: string;
}) {
  if (value == null || value === "") {
    return <span className="ds-empty-value">—</span>;
  }
  const text = String(value);
  if (!isDateOnly(text)) {
    return <span className={cx("ds-date", className)}>{text}</span>;
  }
  return (
    <DateFace
      compact={formatDateOnly(text)}
      full={formatDateOnlyFull(text)}
      className={className}
    />
  );
}

export function CompactDateTime({
  value,
  className,
}: {
  value: unknown;
  className?: string;
}) {
  if (value == null || value === "") {
    return <span className="ds-empty-value">—</span>;
  }
  const text = String(value);
  if (isDateOnly(text)) return <CompactDate value={text} className={className} />;
  const compact = formatDubaiTimestamp(text);
  const full = formatDubaiTimestampFull(text);
  if (compact === text && full === text) {
    return <span className={cx("ds-date", className)}>{text}</span>;
  }
  return <DateFace compact={compact} full={full} className={className} />;
}

export function CompactMonthYear({
  value,
  className,
}: {
  value: unknown;
  className?: string;
}) {
  if (value == null || value === "") {
    return <span className="ds-empty-value">—</span>;
  }
  const text = String(value);
  const compact = formatMonthYear(text);
  const full = formatMonthYearFull(text);
  if (compact === text) {
    return <span className={cx("ds-date", className)}>{text}</span>;
  }
  return <DateFace compact={compact} full={full} className={className} />;
}
