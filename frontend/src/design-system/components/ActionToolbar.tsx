import type { ReactNode } from "react";
import { DsIcon } from "../icons";
import { cx } from "../lib/cx";
import { IconButton } from "./IconButton";
import { Menu, type MenuItem } from "./Menu";

export function ActionToolbar({
  children,
  overflowItems,
  className,
}: {
  children?: ReactNode;
  overflowItems?: MenuItem[];
  className?: string;
}) {
  return (
    <div className={cx("ds-action-toolbar", className)} role="toolbar">
      {children}
      {overflowItems?.length ? (
        <Menu
          label="More actions"
          align="bottom-end"
          trigger={
            <IconButton label="More actions" variant="ghost">
              <DsIcon name="more" size={16} />
            </IconButton>
          }
          items={overflowItems}
        />
      ) : null}
    </div>
  );
}
