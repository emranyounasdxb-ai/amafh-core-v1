import type { StatusTone } from "../../../design-system";
import type { ApiClient } from "../../../app/api/http";
import type { NamedRecord } from "../../../app/api/models";
import { isUuid } from "../../../app/presentation/labels";

export type EmployeeStatus = "Pending Setup" | "Active" | "Offboarded";

export const EMPLOYEE_STATUSES: EmployeeStatus[] = [
  "Pending Setup",
  "Active",
  "Offboarded",
];

type EmployeeRecord = {
  id: string;
  employeeCode: string | null;
  companyEmployeeCode: string | null;
  fullName: string | null;
  status: string;
  branchId: string | null;
  departmentId: string | null;
  designation: string | null;
};

export type EmployeeListRecord = EmployeeRecord & {
  branchName: string | null;
  departmentName: string | null;
  dateOfJoining: string | null;
  lastWorkingDate?: string | null;
  avatarFileId: string | null;
  reportingManagerId: string | null;
  reportingManagerName: string | null;
  reportingManagerCode: string | null;
};

export type AccountAccessStatus = "Not Provisioned" | "Active" | "Disabled";

export type EmployeeAccountState = {
  id: string;
  loginEmail?: string | null;
  accessStatus: AccountAccessStatus | string;
  locked: boolean;
};

export type EmployeeLabelRecord = EmployeeRecord & {
  avatarFileId: string | null;
};

export type EmployeeDetailRecord = EmployeeRecord & {
  reportingManagerId: string | null;
  dateOfJoining: string | null;
  lastWorkingDate?: string | null;
  mobile: string | null;
  personalEmail: string | null;
  nationality: string | null;
  gender: string | null;
  maritalStatus: string | null;
  passportNumber: string | null;
  emiratesIdNumber: string | null;
  avatarFileId: string | null;
  coverFileId: string | null;
  account?: EmployeeAccountState | null;
};

export type AssignmentHistoryRecord = {
  id: string;
  branch_id: string | null;
  department_id: string | null;
  designation_id: string | null;
  reporting_manager_id: string | null;
  assignment_start_date: string;
  assignment_end_date: string | null;
};

export function canRecordLastWorkingDate(
  designation: string | undefined,
  employee: { status: string; lastWorkingDate?: string | null },
) {
  return (
    designation === "Owner" &&
    employee.status === "Offboarded" &&
    !employee.lastWorkingDate
  );
}

export function employeeStatusTone(status: string | null | undefined): StatusTone {
  if (status === "Active") return "success";
  if (status === "Pending Setup") return "warning";
  return "neutral";
}

export function employeeName(
  employee: { fullName?: string | null } | null | undefined,
  fallback = "Unavailable",
) {
  const name = employee?.fullName?.trim();
  return name && !isUuid(name) ? name : fallback;
}

export function employeeCode(
  employee:
    | { companyEmployeeCode?: string | null; employeeCode?: string | null }
    | null
    | undefined,
) {
  const code = (employee?.companyEmployeeCode || employee?.employeeCode || "")
    .toString()
    .trim();
  return code && !isUuid(code) ? code : "";
}

export function employeeAvatarSrc(
  employee: { id: string; avatarFileId?: string | null } | null | undefined,
) {
  if (!employee?.avatarFileId) return undefined;
  return `/api/v1/employees/${encodeURIComponent(employee.id)}/media/avatar?v=${encodeURIComponent(employee.avatarFileId)}`;
}

export function namedLabel(
  rows: NamedRecord[] | null | undefined,
  id: string | null | undefined,
) {
  if (!id) return "";
  const name = rows?.find((row) => row.id === id)?.name;
  return name && !isUuid(name) ? name : "Unavailable";
}

export function departmentLabel(
  departments: (NamedRecord & { branch_id?: string })[] | null | undefined,
  branches: NamedRecord[] | null | undefined,
  id: string | null | undefined,
) {
  if (!id) return "";
  const department = departments?.find((row) => row.id === id);
  if (!department) return "Unavailable";
  const branch = namedLabel(branches, department.branch_id ?? null);
  return branch && branch !== "Unavailable"
    ? `${department.name} · ${branch}`
    : department.name;
}

// Reads individually authorized Employee records; inaccessible ids are omitted.
export async function readEmployeeLookup(
  api: ApiClient,
  path: string,
  signal: AbortSignal,
): Promise<Record<string, EmployeeLabelRecord>> {
  const ids = (new URLSearchParams(path.split("?")[1] || "").get("ids") || "")
    .split(",")
    .filter(Boolean);
  const rows = await Promise.all(
    ids.map((id) =>
      api
        .request<EmployeeLabelRecord>(
          `/employee-labels/${encodeURIComponent(id)}`,
          {
            signal,
          },
        )
        .catch(() => null),
    ),
  );
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");
  return Object.fromEntries(
    rows
      .filter((row): row is EmployeeLabelRecord => Boolean(row))
      .map((row) => [row.id, row]),
  );
}

export function employeeLookupPath(ids: (string | null | undefined)[]) {
  const unique = [...new Set(ids.filter((id): id is string => Boolean(id)))]
    .sort();
  return unique.length
    ? `/employee-labels?lookup=labels&ids=${unique.join(",")}`
    : null;
}
