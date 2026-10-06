import { useEffect, useState, type ReactNode } from "react";
import { FilterCard, FilterDrawer } from "../../design-system";

/** The data-list filter button opens a drawer on narrow viewports. */
export function ResponsiveFilterPanel({
  id,
  label,
  className,
  children,
  onClose,
}: {
  id: string;
  label: string;
  className?: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const [narrow, setNarrow] = useState(
    () => window.matchMedia("(max-width: 639px)").matches,
  );
  useEffect(() => {
    const media = window.matchMedia("(max-width: 639px)");
    const update = () => setNarrow(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return narrow ? (
    <FilterDrawer open title={label} onClose={onClose} onApply={onClose}>
      <div
        id={id}
        className={className}
        style={{ containerType: "inline-size" }}
      >
        {children}
      </div>
    </FilterDrawer>
  ) : (
    <FilterCard id={id} label={label} className={className}>
      {children}
    </FilterCard>
  );
}
