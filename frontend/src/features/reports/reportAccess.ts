import type { Designation } from "../../access";

const generalReports = [
  "executive-summary",
  "case-pipeline",
  "bank-product",
  "customer-portfolio",
  "employee-performance",
];
const financeReports = [
  "finance-summary",
  "payment-register",
  "clawback-history",
];

export function canAccessReport(
  designation: Designation,
  reportId: string,
): boolean {
  if (designation === "Owner" || designation === "Managing Director")
    return true;
  if (designation === "Finance") {
    return [...generalReports, ...financeReports].includes(reportId);
  }
  if (designation === "Sales Manager") {
    return [...generalReports, ...financeReports].includes(reportId);
  }
  return false;
}
