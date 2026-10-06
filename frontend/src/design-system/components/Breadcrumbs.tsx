import type { ReactNode } from "react";
import { DsIcon } from "../icons";

export type BreadcrumbItem = {
  id: string;
  label: ReactNode;
  onClick?: () => void;
};

export function Breadcrumbs({
  items,
  label = "Breadcrumb",
}: {
  items: BreadcrumbItem[];
  label?: string;
}) {
  return (
    <nav className="ds-breadcrumbs" aria-label={label}>
      <ol>
        {items.map((item, index) => {
          const last = index === items.length - 1;
          return (
            <li key={item.id}>
              {item.onClick && !last ? (
                <button type="button" onClick={item.onClick}>
                  {item.label}
                </button>
              ) : (
                <span aria-current={last ? "page" : undefined}>
                  {item.label}
                </span>
              )}
              {last ? null : <DsIcon name="next" size={14} />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
