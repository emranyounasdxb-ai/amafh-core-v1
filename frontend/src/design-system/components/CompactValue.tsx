import {
  formatCompactAmount,
  formatCompactNumber,
  formatCompactPercent,
  formatFullAmount,
  formatFullNumber,
  formatFullPercent,
  type CompactFormatOptions,
} from "../lib/compactNumber";
import { FullValueTooltip } from "./FullValueTooltip";
import { MonetaryAmount } from "./MonetaryAmount";

export type MetricValueKind = "number" | "amount" | "percent";
export { FullValueTooltip } from "./FullValueTooltip";

function CompactFace({ compact, full }: { compact: string; full: string }) {
  return (
    <FullValueTooltip content={full}>
      <span className="ds-numeric" aria-label={full}>
        {compact}
      </span>
    </FullValueTooltip>
  );
}

export function CompactNumber({
  value,
  locale,
  compactDecimals = 2,
  fullDecimals = 0,
}: CompactFormatOptions & { value: number }) {
  return (
    <CompactFace
      compact={formatCompactNumber(value, { locale, compactDecimals })}
      full={formatFullNumber(value, { locale, fullDecimals })}
    />
  );
}

export function CompactAmount({
  value,
  currency = "AED",
}: CompactFormatOptions & { value: number; currency?: string }) {
  if (!currency || currency === "AED") return <MonetaryAmount value={value} />;
  const options = { currency };
  return (
    <CompactFace
      compact={formatCompactAmount(value, options)}
      full={formatFullAmount(value, options)}
    />
  );
}

export function MetricValue({
  value,
  kind = "number",
  currency,
  locale,
  compactDecimals,
  fullDecimals,
}: CompactFormatOptions & {
  value: number;
  kind?: MetricValueKind;
  currency?: string;
}) {
  if (kind === "amount") {
    return <CompactAmount value={value} currency={currency ?? "AED"} />;
  }
  if (kind === "percent") {
    return (
      <CompactFace
        compact={formatCompactPercent(value, { locale, compactDecimals })}
        full={formatFullPercent(value, {
          locale,
          fullDecimals: fullDecimals ?? (Number.isInteger(value) ? 0 : 2),
        })}
      />
    );
  }
  return (
    <CompactNumber
      value={value}
      locale={locale}
      compactDecimals={compactDecimals}
      fullDecimals={fullDecimals}
    />
  );
}
