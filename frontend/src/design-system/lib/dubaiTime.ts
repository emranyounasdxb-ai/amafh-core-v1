import {
  formatDateOnly,
  formatDateOnlyFull,
  isDateOnly,
  monthName,
} from "./dateOnly.ts";

export function isLikelyDateOnly(value: string): boolean {
  return isDateOnly(value);
}

function dubaiParts(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Dubai",
    day: "numeric",
    month: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const read = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? "";
  const year = Number(read("year"));
  const month = Number(read("month"));
  const day = Number(read("day"));
  if (!year || !month || !day) return null;
  return {
    year,
    month,
    day,
    hour: read("hour").padStart(2, "0"),
    minute: read("minute").padStart(2, "0"),
  };
}

export function formatDubaiTimestamp(value: string): string {
  if (isLikelyDateOnly(value)) return formatDateOnly(value);
  const parts = dubaiParts(value);
  if (!parts) return value;
  return `${String(parts.day).padStart(2, "0")} ${monthName(parts.month)} ${String(parts.year).slice(-2)}, ${parts.hour}:${parts.minute}`;
}

export function formatDubaiTimestampFull(value: string): string {
  if (isLikelyDateOnly(value)) return formatDateOnlyFull(value);
  const parts = dubaiParts(value);
  if (!parts) return value;
  return `${parts.day} ${monthName(parts.month, "long")} ${parts.year}, ${parts.hour}:${parts.minute} Dubai time`;
}
