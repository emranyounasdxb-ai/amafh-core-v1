import type {
  AttendanceDayRecord,
  AttendanceStatus,
  DateOnly,
  StatusTone,
} from "../../../design-system";
import { addDays, addMonths, dubaiTodayDateOnly } from "../../../design-system";
import { isUuid } from "../../../app/presentation/labels";

export type AttendanceRecord = {
  id: string;
  employeeId: string;
  systemEmployeeCode: string;
  employeeName: string;
  branchId: string;
  attendanceDate: DateOnly;
  checkInTime: string | null;
  checkOutTime: string | null;
  status: "Present" | "Absent" | string;
  isLate: boolean;
  csvImportBatchId: string | null;
  importedAt: string | null;
  officeStartTime: string | null;
  officeEndTime: string | null;
  workedMinutes: number | null;
  requiredMinutes: number | null;
  lateMinutes: number | null;
};

export type AttendancePage = {
  items: AttendanceRecord[];
  total: number;
  page: number;
  pageSize: number;
  presentCount: number;
  absentCount: number;
  lateCount: number;
  workedMinutes: number;
  averageWorkedMinutes: number | null;
  sundayOffCount: number | null;
};

export type AttendanceEmployee = {
  id: string;
  fullName: string;
  systemEmployeeCode: string;
  companyEmployeeCode: string;
  designation: string | null;
  avatarFileId: string | null;
};

export type AttendanceImportResult = {
  batchId: string;
  branchId: string;
  attendanceDate: DateOnly | null;
  status: string;
  presentCount: number;
  absentCount: number;
  lateCount: number;
  appliedCount: number;
  errors: {
    rowNumber: number;
    column: string | null;
    code: string;
    message: string;
  }[];
};

export type AttendanceImportBatch = {
  batchId: string;
  branchId: string | null;
  attendanceDate: DateOnly | null;
  status: string;
  dataRowCount: number | null;
  appliedCount: number | null;
  errorCount: number | null;
  createdAt: string;
};

export type AttendanceImportRow = {
  rowNumber: number;
  status: string;
  errorCode: string | null;
  errorDetail: string | null;
  columnName: string | null;
};

export function monthStart(date: DateOnly): DateOnly {
  return `${date.slice(0, 7)}-01`;
}

export function monthEnd(date: DateOnly): DateOnly {
  return addDays(addMonths(monthStart(date), 1), -1);
}

export function currentMonth(): DateOnly {
  return monthStart(dubaiTodayDateOnly());
}

export function clockTime(value: string | null | undefined) {
  return value ? value.slice(0, 5) : undefined;
}

export function formatDuration(minutes: number | null | undefined) {
  if (minutes == null || minutes < 0) return "";
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest}m`;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
}

export function formatDurationFull(minutes: number | null | undefined) {
  if (minutes == null || minutes < 0) return "";
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  const parts = [
    hours ? `${hours} ${hours === 1 ? "hour" : "hours"}` : "",
    rest || !hours ? `${rest} ${rest === 1 ? "minute" : "minutes"}` : "",
  ].filter(Boolean);
  return parts.join(" ");
}

export function dayStatus(record: AttendanceRecord): AttendanceStatus {
  if (record.status === "Absent") return "absent";
  return record.isLate ? "late" : "present";
}

export function toDayRecord(record: AttendanceRecord): AttendanceDayRecord {
  return {
    date: record.attendanceDate,
    status: dayStatus(record),
    checkIn: clockTime(record.checkInTime),
    checkOut: clockTime(record.checkOutTime),
    worked: formatDuration(record.workedMinutes) || undefined,
    late: formatDuration(record.lateMinutes) || undefined,
  };
}

export function importStatusTone(status: string): StatusTone {
  if (status === "Applied") return "success";
  if (status === "Rejected") return "danger";
  return "neutral";
}

export function employeeLabel(employee: AttendanceEmployee | undefined) {
  const name = employee?.fullName?.trim();
  return name && !isUuid(name) ? name : "Assigned employee";
}

export function employeeCodeLabel(employee: AttendanceEmployee | undefined) {
  const code = (
    employee?.companyEmployeeCode ||
    employee?.systemEmployeeCode ||
    ""
  ).trim();
  return code && !isUuid(code) ? code : "";
}

const ROW_MESSAGES: Record<string, string> = {
  INVALID_HEADER: "The header must match the five template columns in order.",
  CSV_ROW_LIMIT: "The file exceeds 5,000 data rows.",
  CSV_SIZE_LIMIT: "The file exceeds 5 MB.",
  MALFORMED_ROW: "This row must contain five values.",
  MALFORMED_CSV: "The file is not a valid UTF-8 CSV.",
  REQUIRED_VALUE: "A required value is missing.",
  DUPLICATE_EMPLOYEE: "This employee appears more than once.",
  INVALID_DATE: "Use the date format YYYY-MM-DD.",
  MULTIPLE_DATES: "The file must cover a single attendance date.",
  INVALID_TIME: "Use a 24-hour time such as 09:00.",
  TIME_ORDER_INVALID: "Check-out must be later than check-in.",
  EMPTY_FILE: "At least one employee row is required.",
  ATTENDANCE_DATE_ALREADY_APPLIED:
    "Attendance for this Branch and date is already applied.",
  OFFICE_TIMING_MISSING:
    "No Office Timing is effective for this Branch and date.",
  EMPLOYEE_UNAVAILABLE:
    "This employee code is not available for this Branch and date.",
};

export function rowMessage(code: string | null | undefined) {
  return (code && ROW_MESSAGES[code]) || "This row could not be accepted.";
}

const COMMAND_MESSAGES: Record<string, string> = {
  BRANCH_REQUIRED: "Select a Branch before uploading.",
  BRANCH_UNAVAILABLE: "The selected Branch is not available.",
  ATTENDANCE_CONFLICT:
    "Another upload for this Branch and date finished first. Review import history.",
  FORBIDDEN: "Uploading attendance is outside your authorized Branch.",
};

export function commandMessage(code: string | undefined) {
  return (
    (code && COMMAND_MESSAGES[code]) ||
    "The upload could not be completed. Check the file and try again."
  );
}
