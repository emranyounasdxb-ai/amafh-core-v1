import type { DateOnly, StatusTone } from "../../design-system";

export type WalletKind =
  | "salary_payment"
  | "commission_payment"
  | "commission_earned"
  | "clawback";

export type WalletSummary = {
  periodFrom: string;
  periodTo: string;
  salaryPaidAed: string;
  commissionEarnedAed: string;
  commissionPaidAed: string;
  clawbacksAed: string;
};

export type WalletTransaction = {
  kind: WalletKind;
  id: string;
  date: string;
  amountAed: string | null;
  paymentMonth: string | null;
  caseReference: string | null;
  caseId: string | null;
  productName: string | null;
  bankName: string | null;
  reason: string | null;
  recordedAt: string | null;
};

export type WalletPage = {
  periodFrom: string;
  periodTo: string;
  items: WalletTransaction[];
  total: number;
  page: number;
  pageSize: number;
};

export type WalletDetail = {
  kind: WalletKind;
  id: string;
  paymentType?: string;
  amountAed?: string | null;
  paymentMonth?: string | null;
  paymentDate?: string | null;
  recordedAt?: string | null;
  caseReference?: string | null;
  caseId?: string | null;
  productCode?: string | null;
  productName?: string | null;
  productVariantName?: string | null;
  bankName?: string | null;
  completedOn?: string | null;
  completedAt?: string | null;
  commissionAed?: string | null;
  ccPoints?: number | null;
  pfAmountAed?: string | null;
  ruleEffectiveDate?: string | null;
  clawbackDate?: string | null;
  reason?: string | null;
};

export type WalletPeriod = { start: DateOnly; end: DateOnly };

export const KIND_LABEL: Record<WalletKind, string> = {
  salary_payment: "Salary payment",
  commission_payment: "Commission payment",
  commission_earned: "Commission earned",
  clawback: "Clawback",
};

export const KIND_OPTIONS = (Object.keys(KIND_LABEL) as WalletKind[]).map(
  (value) => ({ value, label: KIND_LABEL[value] }),
);

export const KIND_STATUS: Record<WalletKind, { label: string; tone: StatusTone }> = {
  salary_payment: { label: "Paid", tone: "success" },
  commission_payment: { label: "Paid", tone: "success" },
  commission_earned: { label: "Credited", tone: "brand" },
  clawback: { label: "Recorded", tone: "warning" },
};

export function isWalletKind(value: string): value is WalletKind {
  return value in KIND_LABEL;
}

export function transactionDescription(row: WalletTransaction): string {
  if (row.kind === "salary_payment") return "Salary payment recorded by Finance";
  if (row.kind === "commission_payment")
    return "Commission payment recorded by Finance";
  if (row.kind === "commission_earned")
    return [row.productName, row.bankName].filter(Boolean).join(" · ") ||
      "Completed Case commission";
  return row.reason || "Clawback recorded by Finance";
}
