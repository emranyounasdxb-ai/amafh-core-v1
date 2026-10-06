import {
  branchField,
  employeeSource,
  reasonField,
  type Command,
  type CommandConfirmation,
  type Field,
} from "../../../app/api/commands";

export const ASSET_CATEGORIES = [
  "Mobile Phone",
  "SIM Card",
  "PC",
  "Laptop",
  "Other",
];

export const ASSET_STATUSES = [
  "Available",
  "Issued",
  "Needs Maintenance",
  "Maintenance",
  "Damaged",
];

export type AssetRecord = {
  id: string;
  assetCode: string;
  branchId: string;
  category: string;
  brand: string;
  model: string;
  serialNumber: string;
  mobileNumber: string | null;
  operatorProvider: string | null;
  status: string;
  currentEmployeeId: string | null;
  createdAt: string;
};

export type AssetAssignment = {
  id: string;
  employeeId: string;
  issueDate: string;
  returnDate: string | null;
  returnReason: string | null;
  conditionOnReturn: string | null;
  durationDays: number | null;
  issuedByEmployeeId: string | null;
  returnedByEmployeeId: string | null;
};

export type AssetMaintenance = {
  id: string;
  startDate: string;
  completionDate: string | null;
  resultingStatus: string | null;
  notes: string | null;
  completionNotes: string | null;
  durationDays: number | null;
  startedByEmployeeId: string | null;
  completedByEmployeeId: string | null;
};

export type AssetHistoryEntry = {
  id: string;
  action: string;
  previousStatus: string | null;
  newStatus: string | null;
  effectiveDate: string;
  employeeId: string | null;
  actorEmployeeId: string | null;
  reason: string | null;
};

const createFields: Field[] = [
  branchField,
  {
    key: "category",
    label: "Category",
    required: true,
    options: ASSET_CATEGORIES,
  },
  { key: "brand", label: "Brand", required: true },
  { key: "model", label: "Model", required: true },
  { key: "serialNumber", label: "Serial Number", required: true },
  {
    key: "mobileNumber",
    label: "Mobile Number",
    required: true,
    show: (v) => v.category === "SIM Card",
  },
  {
    key: "operatorProvider",
    label: "Operator / Provider",
    required: true,
    show: (v) => v.category === "SIM Card",
  },
];

export function createAssetCommand(branchScoped: boolean): Command {
  return {
    title: "Add Asset",
    path: "/assets",
    idempotent: true,
    submitLabel: "Add Asset",
    fields: branchScoped
      ? createFields.filter((field) => field.key !== "branchId")
      : createFields,
  };
}

export type AssetCommandKind =
  | "issue"
  | "return"
  | "maintenance-start"
  | "maintenance-complete"
  | "damage";

export function assetCommandKinds(status: string): AssetCommandKind[] {
  const kinds: AssetCommandKind[] = [];
  if (status === "Available") kinds.push("issue");
  if (status === "Issued") kinds.push("return");
  if (status === "Available" || status === "Needs Maintenance")
    kinds.push("maintenance-start");
  if (status === "Maintenance") kinds.push("maintenance-complete");
  if (status === "Available" || status === "Needs Maintenance")
    kinds.push("damage");
  return kinds;
}

export const ASSET_COMMAND_LABEL: Record<AssetCommandKind, string> = {
  issue: "Issue Asset",
  return: "Return Asset",
  "maintenance-start": "Start maintenance",
  "maintenance-complete": "Complete maintenance",
  damage: "Record damage",
};

export function assetCommand(
  kind: AssetCommandKind,
  asset: AssetRecord,
  confirmation: CommandConfirmation,
): Command {
  const base = `/assets/${encodeURIComponent(asset.id)}`;
  const shared = {
    title: ASSET_COMMAND_LABEL[kind],
    submitLabel: ASSET_COMMAND_LABEL[kind],
    idempotent: true,
    confirmation,
  };
  switch (kind) {
    case "issue":
      return {
        ...shared,
        path: `${base}/issue`,
        fields: [
          {
            key: "employeeId",
            label: "Employee",
            required: true,
            source: {
              ...employeeSource,
              where: { branchId: asset.branchId },
            },
          },
          { key: "issueDate", label: "Issue date", type: "date", required: true },
        ],
      };
    case "return":
      return {
        ...shared,
        path: `${base}/return`,
        fields: [
          {
            key: "returnDate",
            label: "Return date",
            type: "date",
            required: true,
          },
          reasonField,
          {
            key: "condition",
            label: "Condition",
            required: true,
            options: ["Available", "Needs Maintenance", "Damaged"],
          },
        ],
      };
    case "maintenance-start":
      return {
        ...shared,
        path: `${base}/maintenance/start`,
        fields: [
          {
            key: "startDate",
            label: "Start date",
            type: "date",
            required: true,
          },
          { key: "notes", label: "Notes", required: true },
        ],
      };
    case "maintenance-complete":
      return {
        ...shared,
        path: `${base}/maintenance/complete`,
        fields: [
          {
            key: "completionDate",
            label: "Completion date",
            type: "date",
            required: true,
          },
          {
            key: "resultingStatus",
            label: "Result",
            options: ["Available", "Damaged"],
            required: true,
          },
          { key: "notes", label: "Notes" },
        ],
      };
    case "damage":
      return {
        ...shared,
        path: `${base}/damage`,
        fields: [
          {
            key: "damageDate",
            label: "Damage date",
            type: "date",
            required: true,
          },
          reasonField,
        ],
      };
  }
}

export function assetStatusTone(status: string) {
  switch (status) {
    case "Available":
      return "success" as const;
    case "Issued":
      return "brand" as const;
    case "Needs Maintenance":
    case "Maintenance":
      return "warning" as const;
    case "Damaged":
      return "danger" as const;
    default:
      return "neutral" as const;
  }
}
