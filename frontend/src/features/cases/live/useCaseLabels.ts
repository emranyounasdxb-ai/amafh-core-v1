import { useEffect, useMemo, useState } from "react";
import { useSession } from "../../../app/session/useSession";
import type { AuthenticatedSession } from "../../../app/api/contracts";
import {
  recordImageSrc,
  type ImageKind,
  type ImageRecord,
} from "../../../app/api/recordImages";
import type {
  CaseRecord,
  DataRecord,
  NamedRecord,
} from "../../../app/api/models";

/** Mirrors the server Employee read scope so lookups never request records outside it. */
function mayReadEmployee(
  session: AuthenticatedSession | null,
  id: string,
  coordinator: boolean,
) {
  if (!session) return false;
  if (id === session.employeeId) return true;
  if (
    session.designation === "Coordinator" ||
    session.designation === "Sales Executive"
  )
    return false;
  return !(session.designation === "Team Leader" && coordinator);
}

function caseEmployees(row: CaseRecord) {
  return [
    [row.ownerEmployeeId, false],
    [row.createdByEmployeeId, false],
    [row.coordinatorEmployeeId, true],
  ] as const;
}

export function useCaseLabels(rows: CaseRecord[]) {
  const { api, session } = useSession();
  const [result, setResult] = useState<{
    session: AuthenticatedSession | null;
    labels: Record<string, string>;
    images: Record<string, string | undefined>;
  } | null>(null);
  const outOfScope = useMemo(() => {
    const ids = new Set<string>();
    rows.forEach((row) => {
      for (const [id, coordinator] of caseEmployees(row))
        if (id && !mayReadEmployee(session, id, coordinator)) ids.add(id);
    });
    return ids;
  }, [rows, session]);
  useEffect(() => {
    const controller = new AbortController();
    const paths = new Map<string, string>();
    rows.forEach((row) => {
      paths.set(row.bankId, `/catalog/banks/${row.bankId}`);
      paths.set(
        row.productTypeId,
        `/catalog/product-types/${row.productTypeId}`,
      );
      if (row.productVariantId)
        paths.set(
          row.productVariantId,
          `/catalog/product-variants/${row.productVariantId}`,
        );
      paths.set(row.customerId, `/customers/${row.customerId}`);
      for (const [id, coordinator] of caseEmployees(row))
        if (id && mayReadEmployee(session, id, coordinator))
          paths.set(id, `/employee-labels/${id}`);
    });
    Promise.all(
      [...paths].map(async ([id, path]) => {
        try {
          const value = await api.request<DataRecord>(path, {
            signal: controller.signal,
          });
          const identity = value.identity as DataRecord | undefined;
          return [
            id,
            String(
              value.fullName ||
                value.name ||
                identity?.full_name ||
                identity?.company_name ||
                "Unavailable",
            ),
            path.startsWith("/catalog/")
              ? recordImageSrc(
                  path.split("/")[2] as ImageKind,
                  value as ImageRecord,
                )
              : undefined,
          ] as const;
        } catch {
          return [id, "Unavailable", undefined] as const;
        }
      }),
    ).then(async (values) => {
      try {
        const [branches, departments] = await Promise.all([
          api.request<NamedRecord[]>("/branches", {
            signal: controller.signal,
          }),
          api.request<NamedRecord[]>("/departments", {
            signal: controller.signal,
          }),
        ]);
        values.push(
          ...branches.map((b) => [b.id, b.name, undefined] as const),
          ...departments.map((d) => [d.id, d.name, undefined] as const),
        );
      } catch {
        /* Inaccessible labels do not grant access to related records. */
      }
      if (!controller.signal.aborted)
        setResult((previous) => ({
          session,
          labels: {
            ...(previous?.session === session ? previous.labels : {}),
            ...Object.fromEntries(values.map(([id, name]) => [id, name])),
          },
          images: {
            ...(previous?.session === session ? previous.images : {}),
            ...Object.fromEntries(values.map(([id, , image]) => [id, image])),
          },
        }));
    });
    return () => controller.abort();
  }, [api, rows, session]);
  const label = (id: string | null) =>
    id
      ? id === session?.employeeId
        ? session.displayName
        : result?.session === session && result.labels[id]
          ? result.labels[id]
          : outOfScope.has(id)
            ? "Unavailable"
            : "Loading…"
      : "Not assigned";
  return Object.assign(label, {
    image: (id: string | null) =>
      result?.session === session && id ? result.images[id] : undefined,
  });
}
