import {
  bankField,
  effectiveField,
  employeeSource,
  offeredProductField,
  reasonField,
  variantField,
  type Command,
  type CommandConfirmation,
  type Field,
} from "../../../app/api/commands";
import { financialRulePayload } from "./salaryPoints";

const ruleFields: Field[] = [
  bankField,
  {
    ...offeredProductField,
    choiceContext: { key: "financeProductCode", from: "code" },
    clearOnChange: [
      "productVariantId",
      "pfAmountMin",
      "pfAmountMax",
      "pfCommissionPer1000",
      "commissionAed",
      "ccPoints",
      "ccSalaryPoints",
    ],
  },
  {
    ...variantField,
    required: true,
    show: (v) => v.financeProductCode === "CC",
  },
  {
    key: "pfAmountMin",
    label: "Final PF loan minimum (AED)",
    type: "decimal",
    required: true,
    show: (v) => v.financeProductCode === "PF",
  },
  {
    key: "pfAmountMax",
    label: "Final PF loan maximum (AED)",
    type: "decimal",
    required: true,
    show: (v) => v.financeProductCode === "PF",
  },
  {
    key: "ccPointsMode",
    label: "CC points calculation",
    required: true,
    options: ["Salary ranges", "Fixed points"],
    initial: "Salary ranges",
    show: (v) => v.financeProductCode === "CC",
  },
  {
    key: "ccPoints",
    label: "CC whole points",
    type: "number",
    show: (v) =>
      v.financeProductCode === "CC" && v.ccPointsMode === "Fixed points",
  },
  {
    key: "ccSalaryPoints",
    label: "Salary ranges and points",
    initial: [{ salaryMin: "", salaryMax: "", points: "" }],
    show: (v) =>
      v.financeProductCode === "CC" && v.ccPointsMode !== "Fixed points",
  },
  {
    key: "commissionAed",
    label: "Commission AED",
    type: "decimal",
    show: (v) => v.financeProductCode === "CC",
  },
  {
    key: "pfCommissionPer1000",
    label: "Commission AED per AED 1,000 loan",
    type: "decimal",
    required: true,
    nonNegative: true,
    hint: "Final approved/disbursed amount ÷ 1,000 × this rate. Fractions use proportional calculation; the final commission rounds to whole AED.",
    show: (v) => v.financeProductCode === "PF",
  },
  effectiveField,
];

export function createRuleCommand(): Command {
  return {
    title: "Add Financial Rule",
    path: "/finance/rules",
    fields: ruleFields,
    transform: financialRulePayload,
    submitLabel: "Add rule",
  };
}

export function replaceRuleCommand(
  ruleId: string,
  confirmation: CommandConfirmation,
): Command {
  return {
    title: "Replace Financial Rule",
    path: `/finance/rules/${encodeURIComponent(ruleId)}/replace`,
    fields: ruleFields,
    transform: financialRulePayload,
    confirmation,
    submitLabel: "Replace rule",
  };
}

export function ruleStatePath(ruleId: string, active: boolean) {
  return `/finance/rules/${encodeURIComponent(ruleId)}/${active ? "deactivate" : "activate"}`;
}

export function paymentCommand(): Command {
  return {
    title: "Record Payment",
    path: "/finance/payments",
    idempotent: true,
    submitLabel: "Record payment",
    fields: [
      {
        key: "employeeId",
        label: "Employee",
        source: employeeSource,
        required: true,
      },
      {
        key: "paymentType",
        label: "Payment type",
        options: ["Salary", "Commission"],
        required: true,
      },
      {
        key: "amountAed",
        label: "Amount AED",
        type: "decimal",
        required: true,
      },
      {
        key: "paymentMonth",
        label: "Payment month",
        type: "month",
        required: true,
      },
      {
        key: "paymentDate",
        label: "Payment date",
        type: "date",
        required: true,
      },
    ],
  };
}

export function clawbackCommand(): Command {
  return {
    title: "Record Clawback",
    path: "/finance/clawbacks",
    idempotent: true,
    submitLabel: "Record clawback",
    fields: [
      { key: "internalCaseId", label: "Internal Case ID", required: true },
      {
        key: "amountAed",
        label: "Amount AED",
        type: "decimal",
        required: true,
      },
      {
        key: "clawbackDate",
        label: "Clawback date",
        type: "date",
        required: true,
      },
      { ...reasonField, max: 500 },
    ],
  };
}
