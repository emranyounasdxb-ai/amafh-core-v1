export type HolidayRow = {
  name: string;
  startDate: string;
  endDate: string;
  sourceReference: string;
};

export type ExpandedHoliday = {
  row: number;
  holidayDate: string;
  name: string;
  sourceReference: string;
};

function dateValue(value: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  if (value.startsWith("0000-")) return null;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(date.getTime()) &&
    date.toISOString().slice(0, 10) === value
    ? date.getTime()
    : null;
}

/** UTC date-only expansion matches backend inclusive ranges, without DST shifts. */
export function reviewHolidayRows(rows: HolidayRow[]) {
  const errors: Record<string, string[]> = {};
  const dates: ExpandedHoliday[] = [];
  const seen = new Map<string, number>();
  const error = (key: string, message: string) => {
    (errors[key] ??= []).push(message);
  };
  if (!rows.length || rows.length > 366)
    error("rows", "Enter between 1 and 366 holiday rows");
  rows.forEach((row, index) => {
    const prefix = `rows.${index}`;
    if (!row.name.trim()) error(`${prefix}.name`, "Holiday name is required");
    if (row.name.length > 200)
      error(`${prefix}.name`, "Use at most 200 characters");
    if (!row.sourceReference.trim())
      error(
        `${prefix}.sourceReference`,
        "Official source reference is required",
      );
    if (row.sourceReference.length > 1000)
      error(`${prefix}.sourceReference`, "Use at most 1000 characters");
    const start = dateValue(row.startDate),
      end = dateValue(row.endDate);
    if (start === null)
      error(`${prefix}.startDate`, "Enter a valid start date");
    if (end === null) error(`${prefix}.endDate`, "Enter a valid end date");
    if (start === null || end === null) return;
    if (end < start) {
      error(`${prefix}.endDate`, "End date must be on or after start date");
      return;
    }
    const count = (end - start) / 86400000 + 1;
    if (count > 366) {
      error(
        `${prefix}.endDate`,
        "Each holiday range may contain at most 366 dates",
      );
      return;
    }
    for (let day = start; day <= end; day += 86400000) {
      const holidayDate = new Date(day).toISOString().slice(0, 10);
      const previous = seen.get(holidayDate);
      if (previous !== undefined) {
        error(
          `${prefix}.startDate`,
          `${holidayDate} also occurs in row ${previous + 1}`,
        );
        error(
          `rows.${previous}.startDate`,
          `${holidayDate} also occurs in row ${index + 1}`,
        );
      }
      seen.set(holidayDate, index);
      dates.push({
        row: index + 1,
        holidayDate,
        name: row.name.trim(),
        sourceReference: row.sourceReference.trim(),
      });
    }
  });
  if (dates.length > 3660)
    error("rows", "A batch may contain at most 3660 expanded dates");
  return { errors, dates };
}
