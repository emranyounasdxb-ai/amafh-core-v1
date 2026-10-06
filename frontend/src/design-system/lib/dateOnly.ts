export type DateOnly = `${number}-${number}-${number}` | string;

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

export type DateParts = { year: number; month: number; day: number };

export function parseDateOnly(value: string): DateParts | null {
  const match = value.match(DATE_ONLY);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const utc = new Date(Date.UTC(year, month - 1, day));
  if (
    utc.getUTCFullYear() !== year ||
    utc.getUTCMonth() !== month - 1 ||
    utc.getUTCDate() !== day
  ) {
    return null;
  }
  return { year, month, day };
}

export function isDateOnly(value: string): boolean {
  return parseDateOnly(value) !== null;
}

export function toDateOnly(year: number, month: number, day: number): DateOnly {
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

const MONTH_SHORT = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;
const MONTH_LONG = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;

function pad2(value: number) {
  return String(value).padStart(2, "0");
}

function compactYear(year: number) {
  return pad2(year % 100);
}

export function formatDateOnly(value: string): string {
  const parts = parseDateOnly(value);
  if (!parts) return value;
  return `${pad2(parts.day)} ${MONTH_SHORT[parts.month - 1]} ${compactYear(parts.year)}`;
}

export function formatDateOnlyFull(value: string): string {
  const parts = parseDateOnly(value);
  if (!parts) return value;
  return `${parts.day} ${MONTH_LONG[parts.month - 1]} ${parts.year}`;
}

export function formatMonthYear(value: string): string {
  const parts = parseDateOnly(value) ?? parseYearMonth(value);
  if (!parts) return value;
  return `${MONTH_SHORT[parts.month - 1]} ${compactYear(parts.year)}`;
}

export function formatMonthYearFull(value: string): string {
  const parts = parseDateOnly(value) ?? parseYearMonth(value);
  if (!parts) return value;
  return `${MONTH_LONG[parts.month - 1]} ${parts.year}`;
}

export function monthName(month: number, width: "short" | "long" = "short") {
  const names = width === "long" ? MONTH_LONG : MONTH_SHORT;
  return names[month - 1] ?? "";
}

function parseYearMonth(value: string): DateParts | null {
  const match = value.match(/^(\d{4})-(\d{2})$/);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (month < 1 || month > 12) return null;
  return { year, month, day: 1 };
}

function formatDayMonth(value: string): string {
  const parts = parseDateOnly(value);
  if (!parts) return value;
  return `${pad2(parts.day)} ${MONTH_SHORT[parts.month - 1]}`;
}

export function formatCompactDateRange(start: string, end: string): string {
  const startParts = parseDateOnly(start);
  const endParts = parseDateOnly(end);
  if (!startParts || !endParts) {
    return `${formatDateOnly(start)} – ${formatDateOnly(end)}`;
  }
  if (startParts.year === endParts.year) {
    return `${formatDayMonth(start)} – ${formatDateOnly(end)}`;
  }
  return `${formatDateOnly(start)} – ${formatDateOnly(end)}`;
}

export function dubaiTodayDateOnly(): DateOnly {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Dubai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const part = (name: string) =>
    parts.find((item) => item.type === name)?.value ?? "01";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function compareDateOnly(left: string, right: string): number {
  return left.localeCompare(right);
}

export function addDays(value: DateOnly, amount: number): DateOnly {
  const parts = parseDateOnly(value);
  if (!parts) return value;
  const utc = new Date(
    Date.UTC(parts.year, parts.month - 1, parts.day + amount),
  );
  return toDateOnly(
    utc.getUTCFullYear(),
    utc.getUTCMonth() + 1,
    utc.getUTCDate(),
  );
}

export function addMonths(value: DateOnly, amount: number): DateOnly {
  const parts = parseDateOnly(value);
  if (!parts) return value;
  const utc = new Date(Date.UTC(parts.year, parts.month - 1 + amount, 1));
  const year = utc.getUTCFullYear();
  const month = utc.getUTCMonth() + 1;
  const last = daysInMonth(year, month);
  return toDateOnly(year, month, Math.min(parts.day, last));
}

export function startOfMonth(value: DateOnly): DateOnly {
  const parts = parseDateOnly(value);
  if (!parts) return value;
  return toDateOnly(parts.year, parts.month, 1);
}

export function endOfMonth(value: DateOnly): DateOnly {
  const parts = parseDateOnly(value);
  if (!parts) return value;
  return toDateOnly(
    parts.year,
    parts.month,
    daysInMonth(parts.year, parts.month),
  );
}

export function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

export function weekdayJs(year: number, month: number, day: number): number {
  return new Date(Date.UTC(year, month - 1, day)).getUTCDay();
}

export function weekdayMondayIndex(
  year: number,
  month: number,
  day: number,
): number {
  return (weekdayJs(year, month, day) + 6) % 7;
}

export function weekdayOffset(
  year: number,
  month: number,
  day: number,
  weekStartsOn = 0,
): number {
  return (weekdayJs(year, month, day) - weekStartsOn + 7) % 7;
}

const WEEKDAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function weekdayLabels(weekStartsOn = 0): string[] {
  return Array.from(
    { length: 7 },
    (_, index) => WEEKDAY_SHORT[(weekStartsOn + index) % 7]!,
  );
}

export function isDateDisabled(
  value: DateOnly,
  options?: {
    min?: DateOnly;
    max?: DateOnly;
    disabledDates?: DateOnly[] | ((date: DateOnly) => boolean);
  },
): boolean {
  if (options?.min && compareDateOnly(value, options.min) < 0) return true;
  if (options?.max && compareDateOnly(value, options.max) > 0) return true;
  const disabled = options?.disabledDates;
  if (Array.isArray(disabled)) return disabled.includes(value);
  if (typeof disabled === "function") return disabled(value);
  return false;
}

export function monthLabel(year: number, month: number): string {
  const utc = new Date(Date.UTC(year, month - 1, 1));
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "UTC",
    month: "long",
    year: "numeric",
  }).format(utc);
}

export function lastDaysRange(days: number, today = dubaiTodayDateOnly()) {
  return { start: addDays(today, 1 - days), end: today };
}

export function thisMonthRange(today = dubaiTodayDateOnly()) {
  return { start: startOfMonth(today), end: today };
}
