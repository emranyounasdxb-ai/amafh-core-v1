import {
  CompactDate,
  InlineNotice,
  MonetaryAmount,
  dubaiTodayDateOnly,
} from "../../../design-system";
import { useResource } from "../../../app/api/useResource";
import type { PackageVersion } from "../../employees/live/hr/hrRecords";

/** Read-only salary package reference for the payment form. It never fills the amount. */
export function PackageReference({
  employeeId,
  paymentDate,
  paymentMonth,
}: {
  employeeId: string;
  paymentDate: string;
  paymentMonth: string;
}) {
  const on =
    paymentDate || (paymentMonth ? `${paymentMonth}-01` : dubaiTodayDateOnly());
  const resource = useResource<{ package: PackageVersion | null }>(
    `/employees/${employeeId}/packages/applicable?on=${encodeURIComponent(on)}`,
  );
  if (resource.loading && !resource.data) return null;
  if (resource.denied || resource.error || !resource.data) return null;
  const row = resource.data.package;
  return (
    <InlineNotice tone="info" title="Package reference (read-only)">
      {row ? (
        <>
          Total monthly{" "}
          <MonetaryAmount compact={false} align="start" value={row.totalMonthlyAed} />
          , basic{" "}
          <MonetaryAmount compact={false} align="start" value={row.basicSalaryAed} />
          , effective <CompactDate value={row.effectiveDate} />. Enter the
          payment amount separately.
        </>
      ) : (
        "No package version applies on this date."
      )}
    </InlineNotice>
  );
}
