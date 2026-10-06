import { useState } from "react";
import {
  Button,
  FormField,
  SearchFilterToolbar,
  SearchInput,
  SectionCard,
  Select,
} from "../index";

const deskOptions = [
  { value: "all", label: "All desks" },
  { value: "north", label: "North operations" },
  { value: "harbour", label: "Harbour desk" },
  { value: "west", label: "West intake" },
];

const longDeskOptions = [
  { value: "all", label: "All desks" },
  {
    value: "north-harbour",
    label: "North operations — Harbour desk",
  },
];

const statusOptions = [
  { value: "all", label: "All statuses" },
  { value: "open", label: "Open" },
  { value: "review", label: "Review" },
  { value: "closed", label: "Closed" },
];

const ownerOptions = [
  { value: "all", label: "All owners" },
  { value: "rahman", label: "A. Rahman" },
  { value: "khalid", label: "M. Khalid" },
  { value: "noor", label: "S. Noor" },
];

const sortOptions = [
  { value: "recent", label: "Recent" },
  { value: "name", label: "Name" },
  { value: "owner", label: "Owner" },
];

function optionLabel(
  options: { value: string; label: string }[],
  value: string,
) {
  return options.find((option) => option.value === value)?.label ?? value;
}

function FilterFields({
  idPrefix,
  owner,
  onOwnerChange,
  status,
  onStatusChange,
  disabled,
}: {
  idPrefix: string;
  owner: string;
  onOwnerChange: (value: string) => void;
  status: string;
  onStatusChange: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <>
      <FormField label="Owner" htmlFor={`${idPrefix}-owner`}>
        <Select
          id={`${idPrefix}-owner`}
          compact
          label="Owner"
          value={owner}
          options={ownerOptions}
          disabled={disabled}
          clearable={owner !== "all"}
          onChange={onOwnerChange}
        />
      </FormField>
      <FormField label="Status" htmlFor={`${idPrefix}-status`}>
        <Select
          id={`${idPrefix}-status`}
          compact
          label="Status"
          value={status}
          options={statusOptions}
          disabled={disabled}
          clearable={status !== "all"}
          onChange={onStatusChange}
        />
      </FormField>
    </>
  );
}

function useFilterDemo(initial?: {
  search?: string;
  desk?: string;
  status?: string;
  owner?: string;
  sort?: string;
}) {
  const [search, setSearch] = useState(initial?.search ?? "");
  const [desk, setDesk] = useState(initial?.desk ?? "all");
  const [status, setStatus] = useState(initial?.status ?? "all");
  const [owner, setOwner] = useState(initial?.owner ?? "all");
  const [sort, setSort] = useState(initial?.sort ?? "recent");
  const applied = [
    desk !== "all"
      ? {
          id: "desk",
          field: "Desk",
          value: optionLabel(deskOptions.concat(longDeskOptions), desk),
          label: `Desk: ${optionLabel(deskOptions.concat(longDeskOptions), desk)}`,
          onRemove: () => setDesk("all"),
        }
      : null,
    status !== "all"
      ? {
          id: "status",
          field: "Status",
          value: optionLabel(statusOptions, status),
          label: `Status: ${optionLabel(statusOptions, status)}`,
          onRemove: () => setStatus("all"),
        }
      : null,
    owner !== "all"
      ? {
          id: "owner",
          field: "Owner",
          value: optionLabel(ownerOptions, owner),
          label: `Owner: ${optionLabel(ownerOptions, owner)}`,
          onRemove: () => setOwner("all"),
        }
      : null,
  ].filter((item): item is NonNullable<typeof item> => item !== null);
  const reset = () => {
    setSearch("");
    setDesk("all");
    setStatus("all");
    setOwner("all");
  };
  return {
    search,
    setSearch,
    desk,
    setDesk,
    status,
    setStatus,
    owner,
    setOwner,
    sort,
    setSort,
    applied,
    reset,
  };
}

function AlignedDesktopToolbar() {
  const demo = useFilterDemo({ desk: "north", status: "open" });
  return (
    <SectionCard
      title="Search and filters"
      description="One toolbar: Search, Desk, Sort, and Filters share a 32px baseline. Pages own the values. These controls do not call APIs."
    >
      <SearchFilterToolbar
        narrow={false}
        searchId="ds-table-search"
        searchLabel="Search"
        searchPlaceholder="Search records"
        searchValue={demo.search}
        onSearchChange={demo.setSearch}
        filters={[
          {
            id: "ds-desk",
            label: "Desk",
            value: demo.desk,
            onChange: demo.setDesk,
            options: deskOptions,
          },
        ]}
        sortId="ds-sort"
        sortValue={demo.sort}
        sortOptions={sortOptions}
        sortDirection="desc"
        onSortChange={demo.setSort}
        applied={demo.applied}
        onClearFilters={demo.reset}
        onResetFilters={demo.reset}
        filterPanel={
          <FilterFields
            idPrefix="ds-aligned"
            owner={demo.owner}
            onOwnerChange={demo.setOwner}
            status={demo.status}
            onStatusChange={demo.setStatus}
          />
        }
      />
      <SearchInput
        id="ds-suggest"
        value={demo.search}
        onChange={demo.setSearch}
        label="Search with suggestions"
        suggestions={[
          "Harbour desk",
          "North operations",
          "West intake",
        ].filter((item) =>
          item.toLowerCase().includes(demo.search.toLowerCase()),
        )}
      />
    </SectionCard>
  );
}

function EmptyFiltersToolbar() {
  const demo = useFilterDemo();
  return (
    <SectionCard
      title="Empty filter state"
      description="Clear All and the applied-chip row stay hidden until a filter is applied."
    >
      <SearchFilterToolbar
        narrow={false}
        searchId="ds-empty-search"
        searchLabel="Search"
        searchPlaceholder="Search records"
        searchValue={demo.search}
        onSearchChange={demo.setSearch}
        filters={[
          {
            id: "ds-empty-desk",
            label: "Desk",
            value: demo.desk,
            onChange: demo.setDesk,
            options: deskOptions,
          },
        ]}
        sortId="ds-empty-sort"
        sortValue={demo.sort}
        sortOptions={sortOptions}
        onSortChange={demo.setSort}
        applied={demo.applied}
        onClearFilters={demo.reset}
        onResetFilters={demo.reset}
        filterPanel={
          <FilterFields
            idPrefix="ds-empty"
            owner={demo.owner}
            onOwnerChange={demo.setOwner}
            status={demo.status}
            onStatusChange={demo.setStatus}
          />
        }
      />
    </SectionCard>
  );
}

function LongValueToolbar() {
  const demo = useFilterDemo({ desk: "north-harbour" });
  return (
    <SectionCard
      title="Long selected value"
      description="Quick filters keep a usable width. Long selected labels truncate inside the control."
    >
      <SearchFilterToolbar
        narrow={false}
        searchId="ds-long-search"
        searchLabel="Search"
        searchPlaceholder="Search records"
        searchValue={demo.search}
        onSearchChange={demo.setSearch}
        filters={[
          {
            id: "ds-long-desk",
            label: "Desk",
            value: demo.desk,
            onChange: demo.setDesk,
            options: longDeskOptions,
          },
        ]}
        sortId="ds-long-sort"
        sortValue={demo.sort}
        sortOptions={sortOptions}
        onSortChange={demo.setSort}
        applied={demo.applied}
        onClearFilters={demo.reset}
        onResetFilters={demo.reset}
        filterPanel={
          <FilterFields
            idPrefix="ds-long"
            owner={demo.owner}
            onOwnerChange={demo.setOwner}
            status={demo.status}
            onStatusChange={demo.setStatus}
          />
        }
      />
    </SectionCard>
  );
}

function WrappedMediumToolbar() {
  const demo = useFilterDemo({
    desk: "harbour",
    status: "review",
    owner: "khalid",
  });
  return (
    <SectionCard
      title="Wrapped medium width"
      description="Controls wrap as complete labeled units. Applied chips stay on the second row."
    >
      <div className="ds-viewport-frame ds-viewport-frame--medium">
        <div className="ds-viewport-frame__inner">
          <SearchFilterToolbar
            narrow={false}
            searchId="ds-wrap-search"
            searchLabel="Search"
            searchPlaceholder="Search records"
            searchValue={demo.search}
            onSearchChange={demo.setSearch}
            filters={[
              {
                id: "ds-wrap-desk",
                label: "Desk",
                value: demo.desk,
                onChange: demo.setDesk,
                options: deskOptions,
              },
              {
                id: "ds-wrap-status",
                label: "Status",
                value: demo.status,
                onChange: demo.setStatus,
                options: statusOptions,
              },
            ]}
            sortId="ds-wrap-sort"
            sortValue={demo.sort}
            sortOptions={sortOptions}
            onSortChange={demo.setSort}
            applied={demo.applied}
            onClearFilters={demo.reset}
            onResetFilters={demo.reset}
            actions={
              <Button size="standard" variant="secondary">
                Export
              </Button>
            }
            filterPanel={
              <FilterFields
                idPrefix="ds-wrap"
                owner={demo.owner}
                onOwnerChange={demo.setOwner}
                status={demo.status}
                onStatusChange={demo.setStatus}
              />
            }
          />
        </div>
      </div>
    </SectionCard>
  );
}

function NarrowDrawerToolbar() {
  const demo = useFilterDemo({ desk: "west", status: "open" });
  return (
    <SectionCard
      title="Narrow layout"
      description="Search uses the first row. Sort and Filters share the second. The Filters button opens the Filter Drawer — not a second Narrow filters control."
    >
      <div className="ds-viewport-frame ds-viewport-frame--narrow">
        <div className="ds-viewport-frame__inner">
          <SearchFilterToolbar
            narrow
            searchId="ds-narrow-search"
            searchLabel="Search"
            searchPlaceholder="Search records"
            searchValue={demo.search}
            onSearchChange={demo.setSearch}
            filters={[
              {
                id: "ds-narrow-desk",
                label: "Desk",
                value: demo.desk,
                onChange: demo.setDesk,
                options: deskOptions,
              },
            ]}
            sortId="ds-narrow-sort"
            sortValue={demo.sort}
            sortOptions={sortOptions}
            onSortChange={demo.setSort}
            applied={demo.applied}
            onClearFilters={demo.reset}
            onResetFilters={demo.reset}
            filterPanel={
              <FilterFields
                idPrefix="ds-narrow-filter"
                owner={demo.owner}
                onOwnerChange={demo.setOwner}
                status={demo.status}
                onStatusChange={demo.setStatus}
              />
            }
          />
        </div>
      </div>
    </SectionCard>
  );
}

function MultipleChipsToolbar() {
  const demo = useFilterDemo({
    desk: "north",
    status: "open",
    owner: "rahman",
  });
  return (
    <SectionCard
      title="Multiple applied chips"
      description="Chips use Field: Value, wrap cleanly, and keep Clear all on the same baseline."
    >
      <SearchFilterToolbar
        narrow={false}
        searchId="ds-chips-search"
        searchLabel="Search"
        searchPlaceholder="Search records"
        searchValue={demo.search}
        onSearchChange={demo.setSearch}
        filters={[
          {
            id: "ds-chips-desk",
            label: "Desk",
            value: demo.desk,
            onChange: demo.setDesk,
            options: deskOptions,
          },
        ]}
        sortId="ds-chips-sort"
        sortValue={demo.sort}
        sortOptions={sortOptions}
        onSortChange={demo.setSort}
        applied={demo.applied}
        onClearFilters={demo.reset}
        onResetFilters={demo.reset}
        filterPanel={
          <FilterFields
            idPrefix="ds-chips"
            owner={demo.owner}
            onOwnerChange={demo.setOwner}
            status={demo.status}
            onStatusChange={demo.setStatus}
          />
        }
      />
    </SectionCard>
  );
}

function DisabledLoadingToolbars() {
  const disabled = useFilterDemo({ desk: "harbour", status: "review" });
  const loading = useFilterDemo({ desk: "north", status: "open" });
  return (
    <SectionCard
      title="Disabled and loading"
      description="The same toolbar accepts disabled and loading presentation. Filter values stay with the caller."
    >
      <SearchFilterToolbar
        narrow={false}
        disabled
        searchId="ds-disabled-search"
        searchLabel="Search"
        searchPlaceholder="Search records"
        searchValue="North"
        onSearchChange={disabled.setSearch}
        filters={[
          {
            id: "ds-disabled-desk",
            label: "Desk",
            value: disabled.desk,
            onChange: disabled.setDesk,
            options: deskOptions,
          },
        ]}
        sortId="ds-disabled-sort"
        sortValue={disabled.sort}
        sortOptions={sortOptions}
        onSortChange={disabled.setSort}
        applied={disabled.applied}
        onClearFilters={disabled.reset}
        filterPanel={
          <FilterFields
            idPrefix="ds-disabled"
            owner={disabled.owner}
            onOwnerChange={disabled.setOwner}
            status={disabled.status}
            onStatusChange={disabled.setStatus}
            disabled
          />
        }
      />
      <SearchFilterToolbar
        narrow={false}
        loading
        searchId="ds-loading-search"
        searchLabel="Search"
        searchPlaceholder="Search records"
        searchValue=""
        onSearchChange={loading.setSearch}
        filters={[
          {
            id: "ds-loading-desk",
            label: "Desk",
            value: loading.desk,
            onChange: loading.setDesk,
            options: deskOptions,
          },
        ]}
        sortId="ds-loading-sort"
        sortValue={loading.sort}
        sortOptions={sortOptions}
        onSortChange={loading.setSort}
        applied={loading.applied}
        onClearFilters={loading.reset}
        filterPanel={
          <FilterFields
            idPrefix="ds-loading"
            owner={loading.owner}
            onOwnerChange={loading.setOwner}
            status={loading.status}
            onStatusChange={loading.setStatus}
          />
        }
      />
    </SectionCard>
  );
}

function LaptopWidthToolbar({ idPrefix }: { idPrefix: string }) {
  const demo = useFilterDemo({ desk: "north-harbour", status: "open" });
  return (
    <SearchFilterToolbar
      searchId={`${idPrefix}-search`}
      searchLabel="Search"
      searchPlaceholder="Search records"
      searchValue={demo.search}
      onSearchChange={demo.setSearch}
      filters={[
        {
          id: `${idPrefix}-desk`,
          label: "Desk",
          value: demo.desk,
          onChange: demo.setDesk,
          options: longDeskOptions,
        },
      ]}
      sortId={`${idPrefix}-sort`}
      sortValue={demo.sort}
      sortOptions={sortOptions}
      onSortChange={demo.setSort}
      applied={demo.applied}
      onClearFilters={demo.reset}
      onResetFilters={demo.reset}
      filterPanel={
        <FilterFields
          idPrefix={idPrefix}
          owner={demo.owner}
          onOwnerChange={demo.setOwner}
          status={demo.status}
          onStatusChange={demo.setStatus}
        />
      }
    />
  );
}

export function FiltersSection() {
  return (
    <section id="filters" className="ds-stack-20">
      <AlignedDesktopToolbar />
      <SectionCard
        title="Laptop content widths"
        description="Toolbar wrapping follows the Search and Filters container, not the browser viewport. Long selected values stay inside their control."
      >
        <div className="ds-content-frame ds-content-frame--1080">
          <p className="ds-content-frame__caption">
            ~1080px content width · 1366×768 with expanded Sidebar
          </p>
          <LaptopWidthToolbar idPrefix="ds-laptop-1080" />
        </div>
        <div className="ds-content-frame ds-content-frame--960">
          <p className="ds-content-frame__caption">
            ~960px content width
          </p>
          <LaptopWidthToolbar idPrefix="ds-laptop-960" />
        </div>
      </SectionCard>
      <EmptyFiltersToolbar />
      <LongValueToolbar />
      <WrappedMediumToolbar />
      <NarrowDrawerToolbar />
      <MultipleChipsToolbar />
      <DisabledLoadingToolbars />
    </section>
  );
}
