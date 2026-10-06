import { useState } from "react";
import { useSession } from "../../../app/session/useSession";
import { PerformanceOverview } from "./PerformanceOverview";
import { PerformanceDetail } from "./PerformanceDetail";
import {
  emptyFilters,
  type OverviewState,
  type PerformanceFilters,
  type Product,
} from "./performancePresentation";

export function PerformancePage({
  id,
  select,
}: {
  id?: string;
  select: (id?: string) => void;
}) {
  const { session } = useSession();
  const [product, setProduct] = useState<Product | "">("");
  const [filters, setFilters] = useState<PerformanceFilters>(emptyFilters);
  const [overview, setOverview] = useState<OverviewState>({
    view: "employees",
    draft: emptyFilters,
    search: "",
    page: 1,
    pageSize: 25,
    sort: null,
  });
  if (!session) return null;

  const seller = session.designation === "Sales Executive";
  if (seller || id) {
    const employeeId = id ?? session.employeeId;
    const own = seller && employeeId === session.employeeId;
    return (
      <PerformanceDetail
        key={employeeId}
        employeeId={employeeId}
        own={own}
        filters={filters}
        product={product}
        onProduct={setProduct}
        onFilters={(patch) => {
          setFilters((current) => ({ ...current, ...patch }));
          setOverview((current) => ({
            ...current,
            draft: { ...current.draft, ...patch },
            page: 1,
          }));
        }}
        onBack={seller ? undefined : () => select()}
      />
    );
  }

  return (
    <PerformanceOverview
      state={overview}
      update={(patch) => setOverview((current) => ({ ...current, ...patch }))}
      filters={filters}
      applyFilters={(next) => {
        setFilters(next);
        setOverview((current) => ({ ...current, draft: next, page: 1 }));
      }}
      product={product}
      setProduct={(next) => {
        setProduct(next);
        setOverview((current) => ({ ...current, page: 1 }));
      }}
      open={select}
    />
  );
}
