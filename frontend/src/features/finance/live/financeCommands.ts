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

const ruleFields: Field[] = [
  bankField,
  offeredProductField,
  variantField,
  {
    key: "pfAmountMin",
    label: "PF minimum AED",
    type: "decimal",
    show: (v) => !v.productVariantId,
  },
  {
    key: "pfAmountMax",
    label: "PF maximum AED",
    type: "decimal",
    show: (v) => !v.productVariantId,
  },
  {
    key: "ccPoints",
    label: "CC whole points",
    type: "number",
    show: (v) => Boolean(v.productVariantId),
  },
  { key: "commissionAed", label: "Commission AED", type: "decimal" },
  effectiveField,
];

export function createRuleCommand(): Command {
  return {
    title: "Add Financial Rule",
    path: "/finance/rules",
    fields: ruleFields,
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
