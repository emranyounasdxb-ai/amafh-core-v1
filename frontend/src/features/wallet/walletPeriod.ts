import {
  addDays,
  addMonths,
  dubaiTodayDateOnly,
  type DateOnly,
} from "../../design-system";
import type { WalletPeriod } from "./walletRecords";

export function monthPeriod(month: string): WalletPeriod {
  const start = `${month.slice(0, 7)}-01` as DateOnly;
  return { start, end: addDays(addMonths(start, 1), -1) };
}

export function currentMonthPeriod(today = dubaiTodayDateOnly()): WalletPeriod {
  return monthPeriod(today);
}

/** The `YYYY-MM` month when the period covers exactly one calendar month. */
export function periodMonth(period: WalletPeriod): string {
  const month = monthPeriod(period.start);
  return month.start === period.start && month.end === period.end
    ? period.start.slice(0, 7)
    : "";
}
