import type { SelectOption } from "../../design-system";
import { Avatar } from "../../design-system";
import { createElement } from "react";
import { recordImageSrc, type ImageRecord } from "../../app/api/recordImages";
import { RecordImage } from "../../shared/media/RecordImage";
import { choices } from "../../app/api/choices";
import type { ApiClient } from "../../app/api/http";
import type { DataRecord, NamedRecord } from "../../app/api/models";
import { useResource } from "../../app/api/useResource";
import { readableLabel } from "../../app/presentation/labels";
import { useSession } from "../../app/session/useSession";
import { namedLabel } from "../employees/live/employeePresentation";
import { useEmployeeLabels } from "../finance/live/financeLabels";
import {
  teamChoicePath,
  type PanelFilter,
  type ReportCatalogItem,
} from "./reportPresentation";

type Department = NamedRecord & { branch_id?: string };

const loadChoices = (api: ApiClient, path: string, signal: AbortSignal) =>
  choices<DataRecord>(api, path, signal);

function named(rows: DataRecord[] | null, field = "name"): SelectOption[] {
  return (rows ?? []).flatMap((row) => {
    const label = readableLabel(row[field], "");
    return label ? [{ value: String(row.id), label }] : [];
  });
}

const EMPLOYEE_KEYS = [
  "employeeId",
  "ownerEmployeeId",
  "caseOwnerEmployeeId",
  "currentEmployeeId",
];

export function useReportSources(
  definition: ReportCatalogItem | undefined,
  rows: DataRecord[],
  summary: DataRecord | undefined,
) {
  const { session } = useSession();
  const keys = new Set([
    ...(definition?.filters ?? []),
    ...(definition?.columns.map((column) => column.key) ?? []),
  ]);
  const branches = useResource<NamedRecord[]>(
    keys.has("branchId") || keys.has("departmentId") ? "/branches" : null,
  );
  const departments = useResource<Department[]>(
    keys.has("departmentId") ? "/departments" : null,
  );
  const banks = useResource<DataRecord[]>(
    keys.has("bankId") ? "/catalog/banks" : null,
    0,
    loadChoices,
    "choices",
  );
  const filters = new Set(definition?.filters ?? []);
  const designations = useResource<DataRecord[]>(
    filters.has("designationId") ? "/designations" : null,
  );
  const teams = useResource<DataRecord[]>(
    filters.has("teamId") ? teamChoicePath(session?.designation) : null,
    0,
    loadChoices,
    "choices",
  );
  const employees = useResource<DataRecord[]>(
    filters.has("employeeId") ? "/employee-labels" : null,
    0,
    loadChoices,
    "choices",
  );
  const winner =
    typeof summary?.winnerEmployeeId === "string"
      ? summary.winnerEmployeeId
      : null;
  const people = useEmployeeLabels([
    ...rows.flatMap((row) =>
      EMPLOYEE_KEYS.map((key) =>
        typeof row[key] === "string" ? (row[key] as string) : null,
      ),
    ),
    winner,
  ]);

  const pending = (resource: { data: unknown; loading: boolean }) =>
    !resource.data && resource.loading;
  const branchLabel = (id: unknown) =>
    typeof id !== "string" || !id
      ? ""
      : pending(branches)
        ? "Loading…"
        : namedLabel(branches.data, id);
  const departmentLabel = (id: unknown) =>
    typeof id !== "string" || !id
      ? ""
      : pending(departments)
        ? "Loading…"
        : namedLabel(departments.data, id);
  const bankLabel = (id: unknown) => {
    if (typeof id !== "string" || !id) return "";
    if (pending(banks)) return "Loading…";
    const name = banks.data?.find((row) => String(row.id) === id)?.name;
    return readableLabel(name, "Unavailable");
  };

  const options = (key: PanelFilter, branchId: string): SelectOption[] => {
    if (key === "branchId") return named(branches.data as DataRecord[] | null);
    if (key === "departmentId")
      return (departments.data ?? [])
        .filter((row) => !branchId || row.branch_id === branchId)
        .map((row) => ({
          value: row.id,
          label: readableLabel(row.name),
          description: namedLabel(branches.data, row.branch_id ?? null),
        }));
    if (key === "designationId") return named(designations.data);
    if (key === "teamId") return named(teams.data);
    if (key === "bankId")
      return (banks.data ?? []).flatMap((row) => {
        const label = readableLabel(row.name, "");
        const src = recordImageSrc("banks", row as ImageRecord);
        return label
          ? [
              {
                value: String(row.id),
                label,
                leading: src
                  ? createElement(RecordImage, { src, label })
                  : undefined,
              },
            ]
          : [];
      });
    if (key === "employeeId")
      return (employees.data ?? []).flatMap((row) => {
        const label = readableLabel(row.fullName, "");
        if (!label) return [];
        const code = readableLabel(
          row.companyEmployeeCode || row.employeeCode,
          "",
        );
        return [
          {
            value: String(row.id),
            label,
            leading: recordImageSrc("employee", row as ImageRecord)
              ? createElement(Avatar, {
                  name: label,
                  src: recordImageSrc("employee", row as ImageRecord),
                  size: "sm",
                })
              : undefined,
            ...(code ? { description: code } : {}),
          },
        ];
      });
    return [];
  };
  const loading = (key: PanelFilter) => {
    const resource =
      key === "branchId"
        ? branches
        : key === "departmentId"
          ? departments
          : key === "designationId"
            ? designations
            : key === "teamId"
              ? teams
              : key === "bankId"
                ? banks
                : key === "employeeId"
                  ? employees
                  : null;
    return Boolean(resource && pending(resource));
  };
  const departmentBranch = (id: string) =>
    departments.data?.find((row) => row.id === id)?.branch_id ?? "";

  return {
    people,
    branchLabel,
    departmentLabel,
    bankLabel,
    options,
    loading,
    departmentBranch,
  };
}

export type ReportSources = ReturnType<typeof useReportSources>;
