import { useState } from "react";
import {
  CompactDate,
  MonetaryAmount,
  StatusBadge,
  formatDateOnly,
  type AppliedFilter,
} from "../../../design-system";
import {
  designationField,
  effectiveField,
  type Command,
  type Field,
} from "../../../app/api/commands";
import { useSession } from "../../../app/session/useSession";
import {
  filterQuery,
  useServerTable,
} from "../../../shared/table/serverTable";
import { SelectFilter } from "../../finance/live/financeCells";
import type { SettingsAction } from "./settingsActions";
import { Text, WholeNumber } from "./settingsCells";
import { canManageSettings } from "./settingsRegistry";
import { SettingsTable } from "./SettingsTable";
import { useNamedRecords } from "./useNamedRecords";

type TargetRecord = {
  id: string;
  branchId: string;
  departmentId: string;
  designationId: string;
  effectiveDate: string;
  targetPoints: number | null;
  targetAmountAed: string | null;
  active: boolean;
  inactiveFromDate: string | null;
  supersededByTargetId: string | null;
};

const EMPTY = { branchId: "", departmentId: "", designationId: "" };

// The selected department's Target product decides which amount applies.
const targetFields: Field[] = [
  {
    key: "branchId",
    label: "Branch",
    required: true,
    source: { path: "/branches", label: "name", where: { active: "true" } },
  },
  {
    key: "departmentId",
    label: "Department",
    required: true,
    source: {
      path: "/departments",
      label: "name",
      queryFrom: { branchId: "branchId" },
      where: { active: "true" },
      allowed: { product_type_code: ["CC", "PF"] },
    },
    choiceContext: { key: "departmentProduct", from: "product_type_code" },
    clearOnChange: ["targetPoints", "targetAmountAed"],
  },
  designationField,
  effectiveField,
  {
    key: "targetPoints",
    label: "Monthly CC points",
    type: "number",
    required: true,
    show: (values) => values.departmentProduct === "CC",
  },
  {
    key: "targetAmountAed",
    label: "Monthly PF amount (AED)",
    type: "decimal",
    required: true,
    show: (values) => values.departmentProduct === "PF",
  },
];

function TargetStatus({ target }: { target: TargetRecord }) {
  if (target.active) return <StatusBadge tone="success">Active</StatusBadge>;
  return target.supersededByTargetId ? (
    <StatusBadge tone="info">Superseded</StatusBadge>
  ) : (
    <StatusBadge tone="neutral">Inactive</StatusBadge>
  );
}

function TargetAmount({ target }: { target: TargetRecord }) {
  if (target.targetAmountAed !== null)
    return (
      <MonetaryAmount value={target.targetAmountAed} compact={false} align="start" />
    );
  return target.targetPoints !== null ? (
    <span>
      <WholeNumber value={target.targetPoints} /> points
    </span>
  ) : (
    <Text value="" />
  );
}

export function TargetSettings() {
  const { session } = useSession();
  const manage = canManageSettings(session, "target.write");
  const [refresh, setRefresh] = useState(0);
  const [filters, setFilters] = useState(EMPTY);
  const table = useServerTable<TargetRecord>(
    "settings-targets",
    "/targets",
    filterQuery(filters),
    refresh,
  );
  const branches = useNamedRecords("/branches", refresh);
  const departments = useNamedRecords("/departments", refresh);
  const designations = useNamedRecords("/designations");
  const departmentOptions = departments.rows
    .filter((row) => !filters.branchId || row.branch_id === filters.branchId)
    .map((row) => ({ value: String(row.id), label: String(row.name) }));
  const applied = [
    filters.branchId && {
      id: "branch",
      label: "Branch",
      field: "Branch",
      value: branches.label(filters.branchId, "Selected branch"),
      onRemove: () => setFilters((current) => ({ ...current, branchId: "", departmentId: "" })),
    },
    filters.departmentId && {
      id: "department",
      label: "Department",
      field: "Department",
      value: departments.label(filters.departmentId, "Selected department"),
      onRemove: () => setFilters((current) => ({ ...current, departmentId: "" })),
    },
    filters.designationId && {
      id: "designation",
      label: "Designation",
      field: "Designation",
      value: designations.label(filters.designationId, "Selected designation"),
      onRemove: () => setFilters((current) => ({ ...current, designationId: "" })),
    },
  ].filter(Boolean) as AppliedFilter[];
  const name = (row: TargetRecord) =>
    `${departments.label(row.departmentId)} · ${branches.label(row.branchId)} · ${designations.label(row.designationId)}`;
  const rowName = (row: TargetRecord) =>
    `${name(row)} · effective ${formatDateOnly(row.effectiveDate)}`;
  const replaceCommand = (row: TargetRecord): Command => ({
    title: "Replace Target",
    path: `/targets/${row.id}/replace`,
    fields: targetFields,
    confirmation: {
      description:
        "The current target is superseded by the replacement from its effective date. Earlier periods keep the current target.",
      facts: [
        { label: "Current target", value: name(row) },
        { label: "Current effective date", value: formatDateOnly(row.effectiveDate) },
      ],
    },
  });
  const actions = (row: TargetRecord): SettingsAction[] => {
    if (row.supersededByTargetId) return [];
    return row.active
      ? [
          {
            id: "replace",
            label: "Replace target",
            success: "Target replaced.",
            command: replaceCommand(row),
            record: row,
          },
          {
            id: "deactivate",
            label: "Deactivate target",
            success: "Target deactivated.",
            confirm: {
              title: "Deactivate target",
              path: `/targets/${row.id}/deactivate`,
              danger: true,
              message:
                "This target stops applying. Rankings for periods it already covered keep their history.",
            },
          },
        ]
      : [
          {
            id: "activate",
            label: "Activate target",
            success: "Target activated.",
            confirm: {
              title: "Activate target",
              path: `/targets/${row.id}/activate`,
              message:
                "This target applies again from its effective date. Activation is rejected when another active target conflicts.",
            },
          },
        ];
  };
  return (
    <SettingsTable
      table={table}
      tableId="settings-targets"
      ariaLabel="Targets"
      kind="Target"
      loadingTitle="Loading targets"
      emptyTitle="No targets"
      emptyDescription="Targets set monthly CC points or PF amounts for a branch, department, and designation."
      filters={
        <>
          <SelectFilter
            id="settings-target-branch"
            label="Branch"
            placeholder="All branches"
            value={filters.branchId}
            options={branches.options()}
            loading={branches.loading}
            onChange={(branchId) =>
              setFilters((current) => ({
                ...current,
                branchId,
                departmentId:
                  branchId &&
                  departments.rows.find((row) => row.id === current.departmentId)
                    ?.branch_id !== branchId
                    ? ""
                    : current.departmentId,
              }))
            }
          />
          <SelectFilter
            id="settings-target-department"
            label="Department"
            placeholder="All departments"
            value={filters.departmentId}
            options={departmentOptions}
            loading={departments.loading}
            onChange={(departmentId) => setFilters((current) => ({ ...current, departmentId }))}
          />
          <SelectFilter
            id="settings-target-designation"
            label="Designation"
            placeholder="All designations"
            value={filters.designationId}
            options={designations.options()}
            loading={designations.loading}
            onChange={(designationId) => setFilters((current) => ({ ...current, designationId }))}
          />
        </>
      }
      applied={applied}
      onClearFilters={() => setFilters(EMPTY)}
      columns={[
        {
          key: "branchId",
          label: "Branch",
          width: 130,
          render: (row) => <Text value={branches.label(row.branchId)} />,
        },
        {
          key: "departmentId",
          label: "Department",
          width: 170,
          render: (row) => <Text value={departments.label(row.departmentId)} />,
        },
        {
          key: "designationId",
          label: "Designation",
          width: 150,
          render: (row) => <Text value={designations.label(row.designationId)} />,
        },
        {
          key: "effectiveDate",
          label: "Effective",
          width: 120,
          kind: "date",
          render: (row) => <CompactDate value={row.effectiveDate} />,
        },
        {
          key: "target",
          label: "Monthly target",
          width: 160,
          kind: "mixed",
          render: (row) => <TargetAmount target={row} />,
        },
        {
          key: "active",
          label: "Status",
          width: 110,
          render: (row) => <TargetStatus target={row} />,
        },
      ]}
      rowLabel={rowName}
      title={name}
      facts={(row) => [
        { label: "Branch", value: <Text value={branches.label(row.branchId)} /> },
        { label: "Department", value: <Text value={departments.label(row.departmentId)} /> },
        { label: "Designation", value: <Text value={designations.label(row.designationId)} /> },
        { label: "Effective", value: <CompactDate value={row.effectiveDate} /> },
        { label: "Monthly target", value: <TargetAmount target={row} /> },
        { label: "Status", value: <TargetStatus target={row} /> },
        {
          label: "Inactive from",
          value: row.inactiveFromDate ? (
            <CompactDate value={row.inactiveFromDate} />
          ) : (
            <Text value="" />
          ),
        },
      ]}
      create={
        manage
          ? {
              label: "Add Target",
              success: "Target added.",
              command: { title: "Add Target", path: "/targets", fields: targetFields },
            }
          : undefined
      }
      actions={manage ? actions : undefined}
      onSaved={() => setRefresh((value) => value + 1)}
    />
  );
}
