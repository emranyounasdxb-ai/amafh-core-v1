import { useState, type ReactNode } from "react";
import {
  AppliedFilterSummary,
  DateRangePicker,
  DropdownSelect,
  FilterButton,
  FilterDrawer,
  FilterPopover,
  FilterToolbar,
  FilterToolbarItem,
  FormField,
  type AppliedFilter,
  type DateOnly,
} from "../../design-system";
import {
  PERIOD_OPTIONS,
  PRODUCT_OPTIONS,
  filterLabel,
  fixedOptions,
  panelFilters,
  productRequired,
  type PanelFilter,
  type ReportCatalogItem,
  type ReportPeriod,
} from "./reportPresentation";
import type { ReportSources } from "./useReportSources";
import styles from "./ReportsPage.module.css";

export type PanelValues = Partial<Record<PanelFilter, string>>;

const pick = (value: string | string[]) =>
  Array.isArray(value) ? (value[0] ?? "") : value;

export function ReportFilterBar({
  reports,
  definition,
  onReport,
  period,
  startDate,
  endDate,
  rangeInvalid,
  onPeriod,
  onRange,
  product,
  productInvalid,
  onProduct,
  applied,
  onApply,
  sources,
  actions,
}: {
  reports: ReportCatalogItem[];
  definition: ReportCatalogItem;
  onReport: (report: string) => void;
  period: ReportPeriod;
  startDate: string;
  endDate: string;
  rangeInvalid: boolean;
  onPeriod: (period: ReportPeriod) => void;
  onRange: (startDate: string, endDate: string) => void;
  product: string;
  productInvalid: boolean;
  onProduct: (product: string) => void;
  applied: PanelValues;
  onApply: (values: PanelValues) => void;
  sources: ReportSources;
  actions?: ReactNode;
}) {
  const report = definition.report;
  const keys = panelFilters(definition);
  const appliedKey = JSON.stringify(applied);
  const [draftState, setDraftState] = useState({
    key: appliedKey,
    values: applied,
  });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const draft = draftState.key === appliedKey ? draftState.values : applied;
  const setDraft = (values: PanelValues) =>
    setDraftState({ key: appliedKey, values });
  const change = (key: PanelFilter, value: string) => {
    const next: PanelValues = { ...draft, [key]: value };
    if (
      key === "branchId" &&
      value &&
      draft.departmentId &&
      sources.departmentBranch(draft.departmentId) !== value
    )
      next.departmentId = "";
    setDraft(next);
  };
  const reset = () => {
    setDraft({});
    onApply({});
  };

  const appliedChips: AppliedFilter[] = keys.flatMap((key) => {
    const value = applied[key];
    if (!value) return [];
    const options = fixedOptions(report, key) ?? sources.options(key, "");
    const label =
      options.find((option) => option.value === value)?.label ??
      (key === "branchId"
        ? sources.branchLabel(value)
        : key === "departmentId"
          ? sources.departmentLabel(value)
          : key === "bankId"
            ? sources.bankLabel(value)
            : "Selected");
    return [
      {
        id: key,
        label: filterLabel(report, key),
        field: filterLabel(report, key),
        value: label,
        onRemove: () => onApply({ ...applied, [key]: "" }),
      },
    ];
  });

  const panel = keys.length ? (
    <div className={styles.filterPanel}>
      {keys.map((key) => {
        const id = `report-filter-${key}`;
        const fixed = fixedOptions(report, key);
        const label = filterLabel(report, key);
        return (
          <FormField key={key} label={label} htmlFor={id}>
            <DropdownSelect
              id={id}
              compact
              clearable
              searchable={!fixed}
              placeholder="All"
              value={draft[key] ?? ""}
              loading={!fixed && sources.loading(key)}
              options={fixed ?? sources.options(key, draft.branchId ?? "")}
              onChange={(value) => change(key, pick(value))}
            />
          </FormField>
        );
      })}
    </div>
  ) : null;

  return (
    <div className="ds-search-filter">
      <FilterToolbar label="Report filters" className={styles.toolbar}>
        <FilterToolbarItem
          label="Report"
          htmlFor="report-kind"
          className={styles.reportControl}
        >
          <DropdownSelect
            id="report-kind"
            label="Report"
            compact
            clearable={false}
            searchable={reports.length > 8}
            value={report}
            options={reports.map((item) => ({
              value: item.report,
              label: item.title,
            }))}
            onChange={(value) => {
              const next = pick(value);
              if (next) onReport(next);
            }}
          />
        </FilterToolbarItem>
        <FilterToolbarItem
          label="Period"
          htmlFor="report-period"
          className="ds-filter-toolbar__item--quick"
        >
          <DropdownSelect
            id="report-period"
            label="Period"
            compact
            clearable={false}
            value={period}
            options={PERIOD_OPTIONS}
            onChange={(value) =>
              onPeriod((pick(value) as ReportPeriod) || "month")
            }
          />
        </FilterToolbarItem>
        {period === "custom" ? (
          <FilterToolbarItem
            label="Report date range"
            htmlFor="report-range"
            className={styles.rangeControl}
          >
            <DateRangePicker
              id="report-range"
              compact
              compactRangeLabel
              invalid={rangeInvalid}
              value={{
                start: startDate as DateOnly | "",
                end: endDate as DateOnly | "",
              }}
              onChange={(range) => onRange(range.start, range.end)}
            />
          </FilterToolbarItem>
        ) : null}
        {definition.filters.includes("productCode") ? (
          <FilterToolbarItem
            label="Product"
            htmlFor="report-product"
            className="ds-filter-toolbar__item--quick"
          >
            <DropdownSelect
              id="report-product"
              label="Product"
              compact
              required={productRequired(report)}
              invalid={productInvalid}
              clearable={!productRequired(report)}
              placeholder={
                productRequired(report) ? "Select product" : "All products"
              }
              value={product}
              options={PRODUCT_OPTIONS}
              onChange={(value) => onProduct(pick(value))}
            />
          </FilterToolbarItem>
        ) : null}
        {panel ? (
          <>
            <FilterToolbarItem
              labeled={false}
              className="ds-filter-toolbar__item--filters ds-cq-wide"
            >
              <FilterPopover
                count={appliedChips.length}
                onApply={() => onApply(draft)}
                onReset={reset}
              >
                {panel}
              </FilterPopover>
            </FilterToolbarItem>
            <FilterToolbarItem
              labeled={false}
              className="ds-filter-toolbar__item--filters ds-cq-narrow"
            >
              <FilterButton
                size="compact"
                count={appliedChips.length}
                onClick={() => setDrawerOpen(true)}
              />
            </FilterToolbarItem>
          </>
        ) : null}
        {actions ? (
          <FilterToolbarItem
            labeled={false}
            className="ds-filter-toolbar__item--page-actions"
          >
            <div className="ds-filter-toolbar__actions">{actions}</div>
          </FilterToolbarItem>
        ) : null}
      </FilterToolbar>
      <AppliedFilterSummary
        items={appliedChips}
        onClear={appliedChips.length ? reset : undefined}
      />
      {panel ? (
        <FilterDrawer
          open={drawerOpen}
          title="Filters"
          onClose={() => setDrawerOpen(false)}
          onReset={reset}
          onApply={() => {
            onApply(draft);
            setDrawerOpen(false);
          }}
        >
          {panel}
        </FilterDrawer>
      ) : null}
    </div>
  );
}
