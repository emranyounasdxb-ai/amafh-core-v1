import { useEffect, useState } from "react";
import {
  Button,
  CompactDateTime,
  DropdownSelect,
  EmptyValue,
  ExportButton,
  FilterButton,
  FormField,
  InlineNotice,
  PageContainer,
  PageHeader,
  SearchFilterToolbar,
  StatusBadge,
  TruncatedText,
  useDebouncedValue,
  type AppliedFilter,
} from "../../../design-system";
import { canManageAssets } from "../../../access";
import type { NamedRecord } from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import { CommandFormDialog } from "../../../app/commands/CommandFormDialog";
import {
  readListState,
  saveListState,
} from "../../../app/navigation/listState";
import { useSession } from "../../../app/session/useSession";
import { ServerTableSection } from "../../../shared/table/ServerTableSection";
import type { TableSort } from "../../../shared/table/tableSortState";
import {
  filterQuery,
  useServerTable,
  type ServerColumn,
} from "../../../shared/table/serverTable";
import {
  employeeLookupPath,
  employeeName,
  namedLabel,
  readEmployeeLookup,
  type EmployeeDetailRecord,
} from "../../employees/live/employeePresentation";
import {
  ASSET_CATEGORIES,
  ASSET_STATUSES,
  assetStatusTone,
  createAssetCommand,
  type AssetRecord,
} from "./assetCommands";
import styles from "./AssetsPage.module.css";
import { ResponsiveFilterPanel } from "../../../shared/filters/ResponsiveFilterPanel";

const TABLE_ID = "assets-list";
const EMPTY = { status: "", category: "", branchId: "" };

type AssetsListState = {
  search: string;
  filters: typeof EMPTY;
  page: number;
  size: number;
  sort: TableSort;
};

function Text({ value }: { value: string | null | undefined }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

function single(value: string | string[]) {
  return Array.isArray(value) ? (value[0] ?? "") : value;
}

export function AssetsPage({ open }: { open: (id: string) => void }) {
  const { session } = useSession();
  const employeeId = session?.employeeId;
  const [initial] = useState(() =>
    readListState<AssetsListState>(employeeId, TABLE_ID),
  );
  const [search, setSearch] = useState(initial?.search ?? "");
  const query = useDebouncedValue(search.trim(), 300);
  const [filters, setFilters] = useState(initial?.filters ?? EMPTY);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [notice, setNotice] = useState("");
  const table = useServerTable<AssetRecord>(
    TABLE_ID,
    "/assets",
    filterQuery({ ...filters, search: query }),
    refresh,
    initial,
  );
  useEffect(() => {
    saveListState<AssetsListState>(employeeId, TABLE_ID, {
      search,
      filters,
      page: table.page,
      size: table.size,
      sort: table.sort,
    });
  }, [employeeId, filters, search, table.page, table.size, table.sort]);
  const branches = useResource<NamedRecord[]>("/branches");
  const people = useResource<Record<string, EmployeeDetailRecord>>(
    employeeLookupPath(table.rows.map((row) => row.currentEmployeeId)),
    refresh,
    readEmployeeLookup,
    "employee-lookup",
  );
  if (!session) return null;
  const mayWrite = canManageAssets(session);
  const branchScoped = session.designation === "Admin Staff";
  const showBranch = !branchScoped && (branches.data?.length ?? 0) > 1;
  const assigned = (id: string | null) => {
    if (!id) return "";
    const employee = people.data?.[id];
    if (employee) return employeeName(employee, "Assigned employee");
    if (id === session.employeeId) return session.displayName;
    return people.loading ? "Loading…" : "Assigned employee";
  };
  const set = (patch: Partial<typeof EMPTY>) =>
    setFilters((current) => ({ ...current, ...patch }));
  const applied = [
    filters.status && {
      id: "status",
      label: "Status",
      field: "Status",
      value: filters.status,
      onRemove: () => set({ status: "" }),
    },
    filters.category && {
      id: "category",
      label: "Category",
      field: "Category",
      value: filters.category,
      onRemove: () => set({ category: "" }),
    },
    filters.branchId && {
      id: "branch",
      label: "Branch",
      field: "Branch",
      value: namedLabel(branches.data, filters.branchId),
      onRemove: () => set({ branchId: "" }),
    },
  ].filter(Boolean) as AppliedFilter[];

  const columns: ServerColumn<AssetRecord>[] = [
    {
      key: "assetCode",
      label: "Asset code",
      width: 130,
      render: (row) => <Text value={row.assetCode} />,
    },
    {
      key: "category",
      label: "Category",
      width: 130,
      render: (row) => <Text value={row.category} />,
    },
    {
      key: "brand",
      label: "Brand",
      width: 120,
      render: (row) => <Text value={row.brand} />,
    },
    {
      key: "model",
      label: "Model",
      width: 140,
      render: (row) => <Text value={row.model} />,
    },
    {
      key: "serialNumber",
      label: "Serial number",
      width: 150,
      render: (row) => <Text value={row.serialNumber} />,
    },
    {
      key: "currentEmployeeId",
      label: "Assigned to",
      width: 180,
      render: (row) => <Text value={assigned(row.currentEmployeeId)} />,
    },
    ...(branchScoped
      ? []
      : [
          {
            key: "branchId",
            label: "Branch",
            width: 140,
            render: (row: AssetRecord) => (
              <Text value={namedLabel(branches.data, row.branchId)} />
            ),
          },
        ]),
    {
      key: "status",
      label: "Status",
      width: 150,
      render: (row) => (
        <StatusBadge tone={assetStatusTone(row.status)}>
          {row.status}
        </StatusBadge>
      ),
    },
    {
      key: "createdAt",
      label: "Added",
      width: 150,
      kind: "datetime",
      render: (row) => <CompactDateTime value={row.createdAt} />,
    },
  ];

  return (
    <PageContainer>
      <div className={styles.page}>
        <PageHeader
          title="Assets"
          subtitle="Company assets, assignments, and maintenance"
        />
        <SearchFilterToolbar
          className={styles.toolbar}
          searchId="asset-search"
          searchLabel="Search"
          searchValue={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search by code, serial number, brand or model"
          applied={applied}
          onClearFilters={applied.length ? () => setFilters(EMPTY) : undefined}
          actions={
            <div className={styles.toolbarActions}>
              <FilterButton
                size="compact"
                count={applied.length}
                aria-expanded={filtersOpen}
                aria-controls="asset-filter-card"
                onClick={() => setFiltersOpen((current) => !current)}
              />
              {table.selection.allowed ? (
                <ExportButton
                  size="compact"
                  selectedCount={table.selection.selectedCount}
                  loading={table.selection.working}
                  disabled={!table.selection.selectedCount}
                  onClick={() => void table.selection.exportCsv()}
                />
              ) : null}
              {mayWrite ? (
                <Button size="compact" onClick={() => setCreating(true)}>
                  Add Asset
                </Button>
              ) : null}
            </div>
          }
        />

        {filtersOpen ? (
          <ResponsiveFilterPanel
            id="asset-filter-card"
            label="Asset filters"
            className={styles.filterCard}
            onClose={() => setFiltersOpen(false)}
          >
            <div className={styles.filterGrid}>
              <FormField label="Status" htmlFor="asset-status">
                <DropdownSelect
                  id="asset-status"
                  compact
                  clearable
                  value={filters.status}
                  placeholder="All statuses"
                  options={ASSET_STATUSES.map((value) => ({
                    value,
                    label: value,
                  }))}
                  onChange={(value) => set({ status: single(value) })}
                />
              </FormField>
              <FormField label="Category" htmlFor="asset-category">
                <DropdownSelect
                  id="asset-category"
                  compact
                  clearable
                  value={filters.category}
                  placeholder="All categories"
                  options={ASSET_CATEGORIES.map((value) => ({
                    value,
                    label: value,
                  }))}
                  onChange={(value) => set({ category: single(value) })}
                />
              </FormField>
              {showBranch ? (
                <FormField label="Branch" htmlFor="asset-branch">
                  <DropdownSelect
                    id="asset-branch"
                    compact
                    clearable
                    value={filters.branchId}
                    placeholder="All Branches"
                    options={(branches.data ?? []).map((branch) => ({
                      value: branch.id,
                      label: branch.name,
                    }))}
                    onChange={(value) => set({ branchId: single(value) })}
                  />
                </FormField>
              ) : null}
            </div>
          </ResponsiveFilterPanel>
        ) : null}

        {notice ? (
          <InlineNotice tone="success" title="Saved">
            {notice}
          </InlineNotice>
        ) : null}

        <ServerTableSection
          table={table}
          tableId={TABLE_ID}
          ariaLabel="Assets"
          stackOnNarrow={false}
          columns={columns}
          filtered={applied.length > 0 || Boolean(query)}
          loadingTitle="Loading Assets"
          emptyTitle="No Assets"
          emptyDescription="There are no Asset records in this authorized view."
          noResultsDescription="No Assets match the current search and filters."
          onRowActivate={(row) => open(row.id)}
          rowLabel={(row) => row.assetCode || "Asset"}
        />
      </div>

      {creating ? (
        <CommandFormDialog
          command={createAssetCommand(branchScoped)}
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            setNotice("Asset added.");
            setRefresh((value) => value + 1);
          }}
        />
      ) : null}
    </PageContainer>
  );
}
