import type { NamedRecord } from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import { useSession } from "../../../app/session/useSession";
import {
  employeeCode,
  employeeLookupPath,
  employeeName,
  namedLabel,
  readEmployeeLookup,
  type EmployeeLabelRecord,
} from "../../employees/live/employeePresentation";
import {
  caseLookupPath,
  catalogLookupPath,
  readCaseLookup,
  readCatalogLookup,
  type CatalogKind,
} from "./financeRecords";

export type PersonLabel = { name: string; code: string };

export function useEmployeeLabels(ids: (string | null | undefined)[]) {
  const { session } = useSession();
  const lookup = useResource<Record<string, EmployeeLabelRecord>>(
    employeeLookupPath(ids),
    0,
    readEmployeeLookup,
    "employee-lookup",
  );
  return (
    id: string | null | undefined,
    fallback = "Assigned employee",
  ): PersonLabel => {
    if (!id) return { name: "", code: "" };
    const employee = lookup.data?.[id];
    if (employee)
      return {
        name: employeeName(employee, fallback),
        code: employeeCode(employee),
      };
    if (session?.employeeId === id)
      return { name: session.displayName, code: "" };
    return { name: lookup.loading ? "Loading…" : fallback, code: "" };
  };
}

export function personText(person: PersonLabel) {
  return person.code ? `${person.name} · ${person.code}` : person.name;
}

export function useBranchLabels() {
  const branches = useResource<NamedRecord[]>("/branches");
  return {
    branches: branches.data ?? [],
    label: (id: string | null | undefined) =>
      id && !branches.data && branches.loading
        ? "Loading…"
        : namedLabel(branches.data, id),
  };
}

export function useCatalogLabels(
  entries: { kind: CatalogKind; id: string | null | undefined }[],
) {
  const lookup = useResource<Record<string, string>>(
    catalogLookupPath(entries),
    0,
    readCatalogLookup,
    "catalog-lookup",
  );
  return (id: string | null | undefined) => {
    if (!id) return "";
    return (
      lookup.data?.[id] || (lookup.loading ? "Loading…" : "Unavailable")
    );
  };
}

export function useCaseLabels(ids: (string | null | undefined)[]) {
  const lookup = useResource<Record<string, string>>(
    caseLookupPath(ids),
    0,
    readCaseLookup,
    "finance-case-lookup",
  );
  return (id: string | null | undefined) => {
    if (!id) return "";
    return (
      lookup.data?.[id] || (lookup.loading ? "Loading…" : "Related case")
    );
  };
}
