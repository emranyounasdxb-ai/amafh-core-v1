import "./tokens/tokens.css";
import "./styles/foundations.css";
import "./styles/components.css";
import "./styles/patterns.css";
import "./styles/overlays-forms.css";
import "./styles/charts-stages.css";
import "./styles/sidebar.css";
import "./styles/attendance-performance.css";

export { dsTokens } from "./tokens/tokens";
export type { DsColorToken } from "./tokens/tokens";
export { cx } from "./lib/cx";
export {
  formatCompactAmount,
  formatCompactNumber,
  formatCompactPercent,
  formatFullAmount,
  formatFullNumber,
  formatFullPercent,
} from "./lib/compactNumber";
export type { CompactFormatOptions } from "./lib/compactNumber";
export {
  AED_CODE,
  UAE_DIRHAM_SIGN,
  formatMoneyCompact,
  formatMoneyCompactNumber,
  formatMoneyFull,
  formatMoneyNumber,
  formatMoneyPlain,
  isMoneyField,
  moneyDisplaySymbol,
  parseMoneyValue,
  prefersUaeDirhamSign,
} from "./lib/money";
export {
  addDays,
  addMonths,
  compareDateOnly,
  dubaiTodayDateOnly,
  formatCompactDateRange,
  formatDateOnly,
  formatDateOnlyFull,
  formatMonthYear,
  formatMonthYearFull,
  isDateOnly,
  parseDateOnly,
  toDateOnly,
  weekdayJs,
  weekdayLabels,
  weekdayMondayIndex,
  weekdayOffset,
} from "./lib/dateOnly";
export type { DateOnly, DateParts } from "./lib/dateOnly";
export {
  formatDubaiTimestamp,
  formatDubaiTimestampFull,
  isLikelyDateOnly,
} from "./lib/dubaiTime";
export {
  isDateOnlyField,
  isRecordDateField,
  isTimestampField,
} from "./lib/recordDates";
export { resolveTableAlign } from "./lib/tableAlign";
export type { TableAlign, TableColumnKind } from "./lib/tableAlign";
export { useDebouncedValue } from "./lib/useDebouncedValue";
export {
  countryOptions,
  countryRecords,
  nationalityOptions,
  searchCountryRecords,
} from "./data/countries";
export type { CountryRecord } from "./data/countries";
export * from "./components";
export * from "./patterns";
export { DsIcon, dsIconGuide, dsIconMap, DS_ICON_STROKE } from "./icons";
export type { DsIconName, DsIconSize } from "./icons";
