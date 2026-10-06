import { formatMoneyCompact, formatMoneyFull } from "./money";

export type CompactFormatOptions = {
  locale?: string;
  compactDecimals?: number;
  fullDecimals?: number;
};

const UNITS = [
  { value: 1e12, suffix: "T" },
  { value: 1e9, suffix: "B" },
  { value: 1e6, suffix: "M" },
  { value: 1e3, suffix: "K" },
] as const;

function finite(value: number) {
  return Number.isFinite(value);
}

export function formatFullNumber(
  value: number,
  options: CompactFormatOptions = {},
): string {
  if (!finite(value)) return "—";
  const { locale = "en-US", fullDecimals = 0 } = options;
  return new Intl.NumberFormat(locale, {
    useGrouping: true,
    minimumFractionDigits: fullDecimals,
    maximumFractionDigits: fullDecimals,
  }).format(value);
}

export function formatCompactNumber(
  value: number,
  options: CompactFormatOptions = {},
): string {
  if (!finite(value)) return "—";
  const { locale = "en-US", compactDecimals = 2 } = options;
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  const unit = UNITS.find((item) => abs >= item.value);
  if (!unit) {
    return new Intl.NumberFormat(locale, {
      useGrouping: true,
      maximumFractionDigits: compactDecimals,
      minimumFractionDigits: 0,
    }).format(value);
  }
  const body = new Intl.NumberFormat(locale, {
    useGrouping: false,
    maximumFractionDigits: compactDecimals,
    minimumFractionDigits: 0,
  }).format(abs / unit.value);
  return `${sign}${body}${unit.suffix}`;
}

export function formatCompactAmount(
  value: number,
  options: CompactFormatOptions & { currency: string },
): string {
  if (options.currency === "AED") {
    return formatMoneyCompact(value);
  }
  return `${options.currency} ${formatCompactNumber(value, options)}`;
}

export function formatFullAmount(
  value: number,
  options: CompactFormatOptions & { currency: string },
): string {
  if (options.currency === "AED") {
    return formatMoneyFull(value);
  }
  return `${options.currency} ${formatFullNumber(value, {
    ...options,
    fullDecimals: Number.isInteger(value) ? 0 : (options.fullDecimals ?? 2),
  })}`;
}

export function formatCompactPercent(
  value: number,
  options: CompactFormatOptions = {},
): string {
  return `${formatCompactNumber(value, options)}%`;
}

export function formatFullPercent(
  value: number,
  options: CompactFormatOptions = {},
): string {
  return `${formatFullNumber(value, options)}%`;
}
