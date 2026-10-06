import {
  formatCompactDateRange,
  formatDateOnly,
  type AppliedFilter,
} from "../../../design-system";

export function rangeChip(
  id: string,
  field: string,
  start: string,
  end: string,
  onRemove: () => void,
): AppliedFilter | null {
  if (!start && !end) return null;
  return {
    id,
    label: field,
    field,
    value:
      start && end
        ? formatCompactDateRange(start, end)
        : start
          ? `${formatDateOnly(start)} – End`
          : `Until ${formatDateOnly(end)}`,
    onRemove,
  };
}
