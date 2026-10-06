import type { ReactNode } from "react";
import {
  AppliedFilterSummary,
  FilterToolbar,
  FilterToolbarItem,
  type AppliedFilter,
} from "../../../design-system";
import styles from "./FinancePage.module.css";

export function FinanceToolbar({
  label,
  children,
  actions,
  applied = [],
  onClearFilters,
}: {
  label: string;
  children?: ReactNode;
  actions?: ReactNode;
  applied?: AppliedFilter[];
  onClearFilters?: () => void;
}) {
  if (!children && !actions) return null;
  return (
    <div className={styles.toolbarStack}>
      <FilterToolbar label={label} className={styles.toolbar}>
        {children}
        {actions ? (
          <FilterToolbarItem
            labeled={false}
            className="ds-filter-toolbar__item--page-actions"
          >
            <div className="ds-filter-toolbar__actions">{actions}</div>
          </FilterToolbarItem>
        ) : null}
      </FilterToolbar>
      <AppliedFilterSummary items={applied} onClear={onClearFilters} />
    </div>
  );
}
