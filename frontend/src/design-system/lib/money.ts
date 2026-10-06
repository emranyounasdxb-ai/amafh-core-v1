export const AED_CODE = "AED";
export const UAE_DIRHAM_SIGN = "\u20C3";

const MONEY_FIELD =
  /(^|[A-Z_])(amount|commission|clawback|salary)(Aed)?$/i;
const MONEY_KEYS = new Set([
  "achievedPFAed",
  "amountAed",
  "baseAmount",
  "commissionAmountAed",
  "commissionPaidAed",
  "pfAed",
  "pfAmount",
  "pfAmountAed",
  "requestedPfAmount",
  "salaryPaidAed",
  "targetAmountAed",
  "totalPaidAed",
]);

let dirhamSignSupported: boolean | null = null;

function finite(value: number) {
  return Number.isFinite(value);
}

function measureWidth(text: string, font: string) {
  if (typeof document === "undefined") return 0;
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  if (!context) return 0;
  context.font = font;
  return context.measureText(text).width;
}

export function prefersUaeDirhamSign(fontFamily?: string) {
  if (dirhamSignSupported != null) return dirhamSignSupported;
  if (typeof document === "undefined") return false;
  const family =
    fontFamily ||
    getComputedStyle(document.documentElement).getPropertyValue("--ds-font") ||
    getComputedStyle(document.body).fontFamily ||
    "Manrope, sans-serif";
  const font = `32px ${family}`;
  const signWidth = measureWidth(UAE_DIRHAM_SIGN, font);
  const missingWidth = measureWidth("\uFFFE", font);
  dirhamSignSupported =
    signWidth > 0 && Math.abs(signWidth - missingWidth) > 0.75;
  return dirhamSignSupported;
}

export function moneyDisplaySymbol() {
  return prefersUaeDirhamSign() ? UAE_DIRHAM_SIGN : AED_CODE;
}

export function isMoneyField(key: string) {
  return MONEY_KEYS.has(key) || /Aed$/i.test(key) || MONEY_FIELD.test(key);
}

export function parseMoneyValue(value: unknown): number | null {
  if (value == null || value === "") return null;
  if (typeof value === "number") return finite(value) ? value : null;
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  const compact = trimmed.replace(/\s+/g, "");
  if (/[kmb]$/i.test(compact.replace(/AED|\u20C3/gi, ""))) return null;
  const cleaned = compact
    .replace(/AED/gi, "")
    .replace(new RegExp(UAE_DIRHAM_SIGN, "g"), "")
    .replace(/,/g, "")
    .replace(/^\((.*)\)$/, "-$1");
  if (!/^-?\d+(\.\d+)?$/.test(cleaned)) return null;
  const next = Number(cleaned);
  return finite(next) ? next : null;
}

function groupNumber(value: number, fractionDigits: number) {
  return new Intl.NumberFormat("en-US", {
    useGrouping: true,
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value);
}

function signed(value: number, body: string) {
  return value < 0 ? `-${body}` : body;
}

export function formatMoneyNumber(value: number): string {
  if (!finite(value)) return "—";
  const abs = Math.abs(value);
  const fils = Math.round(abs * 100) % 100;
  if (fils === 0) return signed(value, groupNumber(Math.round(abs), 0));
  return signed(value, groupNumber(Math.round(abs * 100) / 100, 2));
}

export function formatMoneyCompactNumber(value: number): string {
  if (!finite(value)) return "—";
  const abs = Math.abs(value);
  if (abs < 1000) return formatMoneyNumber(value);
  const divisor = abs >= 1e9 ? 1e9 : abs >= 1e6 ? 1e6 : 1e3;
  const suffix = abs >= 1e9 ? "B" : abs >= 1e6 ? "M" : "K";
  const scaled = Math.round((abs / divisor) * 100) / 100;
  const body = new Intl.NumberFormat("en-US", {
    useGrouping: false,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(scaled);
  return `${value < 0 ? "-" : ""}${body}${suffix}`;
}

export function formatMoneyCompact(value: number): string {
  if (!finite(value)) return "—";
  return `${moneyDisplaySymbol()} ${formatMoneyCompactNumber(value)}`;
}

export function formatMoneyFull(value: number): string {
  if (!finite(value)) return "—";
  return `${AED_CODE} ${formatMoneyNumber(value)}`;
}

export function formatMoneyPlain(value: number): string {
  return formatMoneyFull(value);
}
