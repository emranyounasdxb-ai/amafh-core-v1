import type { ReactNode } from "react";
import { useSession } from "../../app/session/useSession";
import { useColumnLayout } from "../../design-system/lib/useColumnLayout";

export type ConnectedColumn<T> = {
  key: string;
  label: string;
  render?: (row: T) => ReactNode;
  sortKey?: string;
  width?: number;
  fixed?: boolean;
};

export function useConnectedColumnLayout<T>(
  tableId: string,
  columns: ConnectedColumn<T>[],
) {
  const { session } = useSession();
  return useColumnLayout(
    `amafh:table-layout:v1:${session?.employeeId || "signed-out"}:${tableId}`,
    columns,
  );
}
