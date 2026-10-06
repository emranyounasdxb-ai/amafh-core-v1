import { useState } from "react";
import type { AppliedFilter } from "../../../design-system";
import type { Command, Field } from "../../../app/api/commands";
import { useSession } from "../../../app/session/useSession";
import { useArrayTable } from "../../../shared/table/arrayTable";
import {
  filterQuery,
  type ServerColumn,
} from "../../../shared/table/serverTable";
import { SelectFilter } from "../../finance/live/financeCells";
import { stateAction, type SettingsAction } from "./settingsActions";
import { ActiveBadge, Text } from "./settingsCells";
import { canManageSettings } from "./settingsRegistry";
import { SettingsTable } from "./SettingsTable";
import { useNamedRecords } from "./useNamedRecords";

type OrgRecord = {
  id: string;
  name: string;
  active: boolean;
  business_unit_id?: string | null;
  branch_id?: string | null;
  product_type_id?: string | null;
  product_type_code?: string | null;
  operating_city?: string | null;
};

const nameField: Field = { key: "name", label: "Name", required: true, max: 150 };
const businessUnitField: Field = {
  key: "businessUnitId",
  label: "Business unit",
  required: true,
  source: { path: "/business-units", label: "name", where: { active: "true" } },
};
const branchField: Field = {
  key: "branchId",
  label: "Branch",
  required: true,
  source: { path: "/branches", label: "name", where: { active: "true" } },
};
// Office Timings are offered only for Branches classified with an operating city.
const operatingCityField: Field = {
  key: "operatingCity",
  label: "Operating city (Office Timings)",
  options: ["Dubai", "Abu Dhabi"],
};
// CC and PF are the fixed Target product codes enforced by the backend.
const targetProductField: Field = {
  key: "productTypeId",
  label: "Target product",
  source: {
    path: "/catalog/product-types?active=true",
    label: "name",
    paged: true,
    allowed: { code: ["CC", "PF"] },
  },
};

function useManage() {
  const { session } = useSession();
  return canManageSettings(session, "organization.write");
}

function editAction(command: Command, row: OrgRecord): SettingsAction {
  return {
    id: "edit",
    label: "Edit",
    success: "Changes saved.",
    command,
    record: row,
  };
}

const statusColumn: ServerColumn<OrgRecord> = {
  key: "active",
  label: "Status",
  width: 110,
  render: (row) => <ActiveBadge active={row.active} />,
};

export function BusinessUnitSettings() {
  const manage = useManage();
  const [refresh, setRefresh] = useState(0);
  const table = useArrayTable<OrgRecord>(
    "settings-business-units",
    "/business-units",
    "",
    refresh,
  );
  return (
    <SettingsTable
      table={table}
      tableId="settings-business-units"
      ariaLabel="Business units"
      kind="Business unit"
      loadingTitle="Loading business units"
      emptyTitle="No business units"
      emptyDescription="Business units group branches."
      columns={[
        {
          key: "name",
          label: "Business unit",
          width: 260,
          render: (row) => <Text value={row.name} />,
        },
        statusColumn,
      ]}
      rowLabel={(row) => row.name}
      title={(row) => row.name}
      facts={(row) => [
        { label: "Business unit", value: <Text value={row.name} /> },
        { label: "Status", value: <ActiveBadge active={row.active} /> },
      ]}
      create={
        manage
          ? {
              label: "Add Business Unit",
              success: "Business unit added.",
              command: {
                title: "Add Business Unit",
                path: "/business-units",
                fields: [nameField],
              },
            }
          : undefined
      }
      actions={
        manage
          ? (row) => [
              editAction(
                {
                  title: "Edit Business Unit",
                  path: `/business-units/${row.id}`,
                  method: "PATCH",
                  fields: [nameField],
                },
                row,
              ),
              stateAction(
                "business unit",
                `/business-units/${row.id}`,
                row.active,
                "This business unit stops being offered for new branches. Active branches must be deactivated first. History is retained.",
              ),
            ]
          : undefined
      }
      onSaved={() => setRefresh((value) => value + 1)}
    />
  );
}

export function BranchSettings() {
  const manage = useManage();
  const [refresh, setRefresh] = useState(0);
  const table = useArrayTable<OrgRecord>(
    "settings-branches",
    "/branches",
    "",
    refresh,
  );
  const units = useNamedRecords("/business-units", refresh);
  const unitFact = (row: OrgRecord) => (
    <Text value={units.label(row.business_unit_id)} />
  );
  const cityFact = (row: OrgRecord) => (
    <Text value={row.operating_city || "Not assigned"} />
  );
  return (
    <SettingsTable
      table={table}
      tableId="settings-branches"
      ariaLabel="Branches"
      kind="Branch"
      loadingTitle="Loading branches"
      emptyTitle="No branches"
      emptyDescription="Branches belong to a business unit."
      columns={[
        {
          key: "name",
          label: "Branch",
          width: 220,
          render: (row) => <Text value={row.name} />,
        },
        {
          key: "business_unit_id",
          label: "Business unit",
          width: 220,
          render: unitFact,
        },
        {
          key: "operating_city",
          label: "Operating city",
          width: 150,
          render: cityFact,
        },
        statusColumn,
      ]}
      rowLabel={(row) => row.name}
      title={(row) => row.name}
      facts={(row) => [
        { label: "Branch", value: <Text value={row.name} /> },
        { label: "Business unit", value: unitFact(row) },
        { label: "Operating city", value: cityFact(row) },
        { label: "Status", value: <ActiveBadge active={row.active} /> },
      ]}
      create={
        manage
          ? {
              label: "Add Branch",
              success: "Branch added.",
              command: {
                title: "Add Branch",
                path: "/branches",
                fields: [nameField, businessUnitField, operatingCityField],
              },
            }
          : undefined
      }
      actions={
        manage
          ? (row) => [
              editAction(
                {
                  title: "Edit Branch",
                  path: `/branches/${row.id}`,
                  method: "PATCH",
                  fields: [nameField, businessUnitField, operatingCityField],
                },
                row,
              ),
              stateAction(
                "branch",
                `/branches/${row.id}`,
                row.active,
                "This branch stops being offered for new selections. Its active departments and employees must be moved first. History is retained.",
              ),
            ]
          : undefined
      }
      onSaved={() => setRefresh((value) => value + 1)}
    />
  );
}

export function DepartmentSettings() {
  const manage = useManage();
  const [refresh, setRefresh] = useState(0);
  const [branchId, setBranchId] = useState("");
  const table = useArrayTable<OrgRecord>(
    "settings-departments",
    "/departments",
    filterQuery({ branchId }),
    refresh,
  );
  const branches = useNamedRecords("/branches", refresh);
  const products = useNamedRecords("/catalog/product-types", refresh);
  const branchFact = (row: OrgRecord) => (
    <Text value={branches.label(row.branch_id)} />
  );
  const productFact = (row: OrgRecord) => (
    <Text
      value={
        row.product_type_id ? products.label(row.product_type_id) : "Not assigned"
      }
    />
  );
  const applied: AppliedFilter[] = branchId
    ? [
        {
          id: "branch",
          label: "Branch",
          field: "Branch",
          value: branches.label(branchId, "Selected branch"),
          onRemove: () => setBranchId(""),
        },
      ]
    : [];
  const name = (row: OrgRecord) =>
    `${row.name} · ${branches.label(row.branch_id)}`;
  return (
    <SettingsTable
      table={table}
      tableId="settings-departments"
      ariaLabel="Departments"
      kind="Department"
      loadingTitle="Loading departments"
      emptyTitle="No departments"
      emptyDescription="Departments belong to a branch. Targets use the department's Target product."
      filters={
        <SelectFilter
          id="settings-department-branch"
          label="Branch"
          placeholder="All branches"
          value={branchId}
          options={branches.options()}
          loading={branches.loading}
          onChange={setBranchId}
        />
      }
      applied={applied}
      onClearFilters={() => setBranchId("")}
      columns={[
        {
          key: "name",
          label: "Department",
          width: 220,
          render: (row) => <Text value={row.name} />,
        },
        { key: "branch_id", label: "Branch", width: 160, render: branchFact },
        {
          key: "product_type_id",
          label: "Target product",
          width: 170,
          render: productFact,
        },
        statusColumn,
      ]}
      rowLabel={name}
      title={name}
      facts={(row) => [
        { label: "Department", value: <Text value={row.name} /> },
        { label: "Branch", value: branchFact(row) },
        { label: "Target product", value: productFact(row) },
        { label: "Status", value: <ActiveBadge active={row.active} /> },
      ]}
      create={
        manage
          ? {
              label: "Add Department",
              success: "Department added.",
              command: {
                title: "Add Department",
                path: "/departments",
                fields: [nameField, branchField, targetProductField],
              },
            }
          : undefined
      }
      actions={
        manage
          ? (row) => [
              editAction(
                {
                  title: "Edit Department",
                  path: `/departments/${row.id}`,
                  method: "PATCH",
                  fields: [nameField, targetProductField],
                },
                row,
              ),
              stateAction(
                "department",
                `/departments/${row.id}`,
                row.active,
                "This department stops being offered for new selections. Its active employees and teams must be moved first. Targets and history are retained.",
              ),
            ]
          : undefined
      }
      onSaved={() => setRefresh((value) => value + 1)}
    />
  );
}
