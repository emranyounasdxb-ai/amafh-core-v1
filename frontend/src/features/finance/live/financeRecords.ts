import type { ApiClient } from "../../../app/api/http";
import type { DataRecord, Page } from "../../../app/api/models";
import { isUuid } from "../../../app/presentation/labels";

export type FinanceView =
  | "completed-cases"
  | "wallets"
  | "clawbacks"
  | "payments"
  | "rules";

export const VIEW_LABEL: Record<FinanceView, string> = {
  "completed-cases": "Completed cases",
  wallets: "Points wallets",
  clawbacks: "Clawbacks",
  payments: "Payments",
  rules: "Financial rules",
};

export function financeViews(ledgers: boolean): FinanceView[] {
  return ledgers
    ? ["completed-cases", "wallets", "clawbacks", "payments", "rules"]
    : ["completed-cases", "clawbacks", "payments"];
}

export type ClawbackRecord = {
  id: string;
  case_id: string;
  case_owner_employee_id: string;
  amount_aed: string;
  clawback_date: string;
  reason: string;
  created_by_employee_id: string;
  created_at: string;
  internal_case_id?: string;
  branch_id?: string | null;
  department_id?: string | null;
};

export type CompletedCaseRecord = {
  id: string;
  case_id: string;
  financial_rule_id: string;
  credited_owner_employee_id: string;
  product_code: string;
  completed_at: string;
  cc_points: number | null;
  commission_aed: string | null;
  pf_amount_aed: string | null;
  rule_effective_date: string;
  created_at: string;
  internal_case_id: string;
  branch_id: string | null;
  department_id: string | null;
  current_owner_employee_id: string | null;
};

export type CompletedCaseDetail = CompletedCaseRecord & {
  clawback: ClawbackRecord | null;
};

export type WalletRecord = {
  id: string;
  employee_id: string;
  created_at: string;
  balance_points: number;
};

export type WalletTransaction = {
  id: string;
  wallet_id: string;
  case_id: string;
  points_credited: number;
  occurred_at: string;
};

export type WalletDetail = {
  walletId: string;
  employeeId: string;
  balancePoints: number;
  transactions: Page<WalletTransaction>;
};

export type PaymentRecord = {
  id: string;
  employee_id: string;
  payment_type: string;
  amount_aed: string;
  payment_month: string;
  payment_date: string;
  created_by_employee_id: string;
  created_at: string;
  branch_id: string | null;
  department_id: string | null;
};

export type FinancialRuleRecord = {
  id: string;
  bank_id: string;
  product_type_id: string;
  product_variant_id: string | null;
  pf_amount_min: string | null;
  pf_amount_max: string | null;
  cc_points: number | null;
  commission_aed: string | null;
  effective_date: string;
  active: boolean;
  superseded_by_rule_id: string | null;
  created_at: string;
};

export type CatalogKind = "banks" | "product-types" | "product-variants";

function lookupIds(path: string) {
  return (new URLSearchParams(path.split("?")[1] || "").get("ids") || "")
    .split(",")
    .filter(Boolean);
}

function readable(value: unknown) {
  const text = typeof value === "string" ? value.trim() : "";
  return text && !isUuid(text) ? text : "";
}

export function catalogLookupPath(
  entries: { kind: CatalogKind; id: string | null | undefined }[],
) {
  const unique = [
    ...new Set(
      entries
        .filter((entry) => entry.id)
        .map((entry) => `${entry.kind}:${entry.id}`),
    ),
  ].sort();
  return unique.length ? `/catalog/lookup?ids=${unique.join(",")}` : null;
}

// Reads individually authorized catalog records; inaccessible ids are omitted.
export async function readCatalogLookup(
  api: ApiClient,
  path: string,
  signal: AbortSignal,
): Promise<Record<string, string>> {
  const rows = await Promise.all(
    lookupIds(path).map(async (entry) => {
      const [kind, id] = entry.split(":");
      try {
        const record = await api.request<DataRecord>(
          `/catalog/${kind}/${encodeURIComponent(id)}`,
          { signal },
        );
        const name = readable(record.name);
        return name ? ([id, name] as const) : null;
      } catch {
        return null;
      }
    }),
  );
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");
  return Object.fromEntries(
    rows.filter((row): row is readonly [string, string] => Boolean(row)),
  );
}

export function caseLookupPath(ids: (string | null | undefined)[]) {
  const unique = [
    ...new Set(ids.filter((id): id is string => Boolean(id))),
  ].sort();
  return unique.length
    ? `/finance/completed-cases?lookup=cases&ids=${unique.join(",")}`
    : null;
}

// Resolves Case IDs through the scoped completed-case read; inaccessible ids are omitted.
export async function readCaseLookup(
  api: ApiClient,
  path: string,
  signal: AbortSignal,
): Promise<Record<string, string>> {
  const rows = await Promise.all(
    lookupIds(path).map(async (id) => {
      try {
        const record = await api.request<CompletedCaseRecord>(
          `/finance/completed-cases/${encodeURIComponent(id)}`,
          { signal },
        );
        const label = readable(record.internal_case_id);
        return label ? ([id, label] as const) : null;
      } catch {
        return null;
      }
    }),
  );
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");
  return Object.fromEntries(
    rows.filter((row): row is readonly [string, string] => Boolean(row)),
  );
}

export function caseLabel(value: string | null | undefined) {
  return readable(value) || "Related case";
}
