import { useContext, type ReactNode } from "react";
import { cx } from "../lib/cx";
import { TablePreferenceScope } from "../lib/useColumnLayout";

export function DesignSystemRoot({
  children,
  className,
  tablePreferenceScope,
}: {
  children: ReactNode;
  className?: string;
  tablePreferenceScope?: string;
}) {
  const inheritedScope = useContext(TablePreferenceScope);
  return (
    <TablePreferenceScope.Provider
      value={tablePreferenceScope ?? inheritedScope}
    >
      <div className={cx("ds-root", className)}>{children}</div>
    </TablePreferenceScope.Provider>
  );
}
