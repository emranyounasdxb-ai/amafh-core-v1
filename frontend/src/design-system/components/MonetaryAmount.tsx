import type { ReactNode } from "react";
import { cx } from "../lib/cx";
import {
  formatMoneyCompactNumber,
  formatMoneyFull,
  formatMoneyNumber,
  parseMoneyValue,
} from "../lib/money";
import { FullValueTooltip } from "./FullValueTooltip";
import { UaeDirhamSymbol } from "./UaeDirhamSymbol";

export function MonetaryAmount({
  value,
  compact = true,
  align = "end",
  className,
}: {
  value: unknown;
  compact?: boolean;
  align?: "start" | "end";
  className?: string;
}) {
  const amount = parseMoneyValue(value);
  if (amount == null) return <span className="ds-empty-value">—</span>;
  const full = formatMoneyFull(amount);
  const shown = compact
    ? formatMoneyCompactNumber(amount)
    : formatMoneyNumber(amount);
  return (
    <FullValueTooltip content={full}>
      <span
        className={cx(
          "ds-money",
          "ds-numeric",
          align === "end" && "ds-money--end",
          className,
        )}
        aria-label={full}
      >
        <UaeDirhamSymbol />
        <span className="ds-money__amount">{shown}</span>
      </span>
    </FullValueTooltip>
  );
}

export function MoneyOrLabel({
  value,
  fallback,
  align = "start",
}: {
  value: unknown;
  fallback?: ReactNode;
  align?: "start" | "end";
}) {
  const amount = parseMoneyValue(value);
  if (amount != null) return <MonetaryAmount value={amount} align={align} />;
  if (fallback == null || fallback === "") {
    return <span className="ds-empty-value">—</span>;
  }
  return <>{fallback}</>;
}
