import { useState, type ReactNode } from "react";
import {
  AppliedFilterSummary,
  FilterButton,
  FilterPopover,
  SortControl,
  type AppliedFilter,
} from "../components/FilterControls";
import {
  FilterToolbar,
  FilterToolbarItem,
} from "../components/FilterToolbar";
import { SearchInput } from "../components/SearchInput";
import { DropdownSelect } from "../components/DropdownSelect";
import type { SelectOption } from "../components/Select";
import { Tooltip } from "../components/Tooltip";
import { FilterDrawer } from "./FilterDrawer";
import { cx } from "../lib/cx";

export type FilterChoice = {
  id: string;
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
};

export function SearchFilterToolbar({
  searchId,
  searchLabel,
  searchValue,
  onSearchChange,
  searchPlaceholder = "Search",
  filters,
  applied,
  onClearFilters,
  sortId,
  sortValue,
  sortOptions,
  onSortChange,
  sortDirection,
  sortLabel,
  filterPanel,
  onApplyFilters,
  onResetFilters,
  extra,
  actions,
  narrow,
  disabled,
  loading,
  className,
}: {
  searchId: string;
  searchLabel: string;
  searchValue: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  filters?: FilterChoice[];
  applied?: AppliedFilter[];
  onClearFilters?: () => void;
  sortId?: string;
  sortValue?: string;
  sortOptions?: { value: string; label: string }[];
  onSortChange?: (value: string) => void;
  sortDirection?: "asc" | "desc";
  sortLabel?: string;
  filterPanel?: ReactNode;
  onApplyFilters?: () => void;
  onResetFilters?: () => void;
  extra?: ReactNode;
  actions?: ReactNode;
  narrow?: boolean;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
}) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const pageActions = actions ?? extra;
  const count = applied?.length ?? 0;
  const showPanel = Boolean(filterPanel);

  return (
    <div
      className={cx(
        "ds-search-filter",
        narrow === true && "ds-search-filter--narrow",
        narrow === false && "ds-search-filter--wide",
        className,
      )}
    >
      <FilterToolbar label="Search and filters">
        <FilterToolbarItem
          label={searchLabel}
          htmlFor={searchId}
          className="ds-filter-toolbar__item--search"
        >
          <SearchInput
            id={searchId}
            compact
            label={searchLabel}
            placeholder={searchPlaceholder}
            value={searchValue}
            onChange={onSearchChange}
            disabled={disabled || loading}
          />
        </FilterToolbarItem>
        {filters?.map((filter, index) => {
          const selected = filter.options.find(
            (option) => option.value === filter.value,
          )?.label;
          const select = (
            <DropdownSelect
              id={filter.id}
              label={filter.label}
              compact
              clearable={Boolean(filter.value) && filter.value !== "all"}
              value={filter.value}
              options={filter.options}
              disabled={disabled || loading || filter.disabled}
              loading={loading}
              onChange={(next) => filter.onChange(String(next))}
            />
          );
          return (
            <FilterToolbarItem
              key={filter.id}
              label={filter.label}
              htmlFor={filter.id}
              className={cx(
                "ds-filter-toolbar__item--quick",
                index > 0 && "ds-filter-toolbar__item--quick-extra",
              )}
            >
              {selected && selected.length > 18 ? (
                <Tooltip content={selected}>{select}</Tooltip>
              ) : (
                select
              )}
            </FilterToolbarItem>
          );
        })}
        {sortId && sortValue != null && sortOptions && onSortChange ? (
          <SortControl
            id={sortId}
            label={sortLabel}
            value={sortValue}
            options={sortOptions}
            onChange={onSortChange}
            direction={sortDirection}
            disabled={disabled || loading}
            loading={loading}
          />
        ) : null}
        {showPanel ? (
          <FilterToolbarItem
            labeled={false}
            className="ds-filter-toolbar__item--filters ds-cq-wide"
          >
            <FilterPopover
              count={count}
              disabled={disabled}
              loading={loading}
              onApply={onApplyFilters}
              onReset={onResetFilters}
            >
              {filterPanel}
            </FilterPopover>
          </FilterToolbarItem>
        ) : null}
        {showPanel ? (
          <FilterToolbarItem
            labeled={false}
            className="ds-filter-toolbar__item--filters ds-cq-narrow"
          >
            <FilterButton
              size="compact"
              count={count}
              disabled={disabled}
              loading={loading}
              onClick={() => setDrawerOpen(true)}
            />
          </FilterToolbarItem>
        ) : null}
        {pageActions ? (
          <FilterToolbarItem
            labeled={false}
            className="ds-filter-toolbar__item--page-actions"
          >
            <div className="ds-filter-toolbar__actions">{pageActions}</div>
          </FilterToolbarItem>
        ) : null}
      </FilterToolbar>
      <AppliedFilterSummary items={applied ?? []} onClear={onClearFilters} />
      {showPanel ? (
        <FilterDrawer
          open={drawerOpen}
          title="Filters"
          busy={loading}
          onClose={() => setDrawerOpen(false)}
          onReset={onResetFilters}
          onApply={() => {
            onApplyFilters?.();
            setDrawerOpen(false);
          }}
        >
          {filterPanel}
        </FilterDrawer>
      ) : null}
    </div>
  );
}
