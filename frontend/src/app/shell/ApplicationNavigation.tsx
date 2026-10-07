import { useState, type KeyboardEvent } from "react";
import { DsIcon, type SidebarNavGroup } from "../../design-system";
import styles from "./ApplicationShell.module.css";

/** Production sections expand in the navigation column, never in a flyout. */
export function ApplicationNavigation({
  groups,
  activeId,
  collapsed = false,
  onExpand,
  onSelect,
}: {
  groups: SidebarNavGroup[];
  activeId: string;
  collapsed?: boolean;
  onExpand?: () => void;
  onSelect: (id: string) => void;
}) {
  const activeGroup = groups.find((group) =>
    group.items.some((item) => item.id === activeId),
  )?.id;
  const [opened, setOpened] = useState<Record<string, boolean>>({});
  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const buttons = Array.from(
      event.currentTarget.querySelectorAll<HTMLButtonElement>("button"),
    ).filter((button) => !button.disabled && button.getClientRects().length > 0);
    if (!buttons.length) return;
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    event.preventDefault();
    const next =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? buttons.length - 1
          : (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) %
            buttons.length;
    buttons[next]?.focus();
  };
  return (
    <nav
      className={styles.navigation}
      aria-label="Main navigation"
      onKeyDown={onKeyDown}
    >
      {groups.map((group) => {
        const open = !collapsed && (opened[group.id] ?? activeGroup === group.id);
        return (
          <div
            key={group.id}
            onPointerEnter={(event) => {
              if (event.pointerType === "mouse")
                setOpened((current) => ({ ...current, [group.id]: true }));
            }}
          >
            <button
              type="button"
              className={`ds-sidebar-item ${activeGroup === group.id ? "ds-sidebar-item--active" : ""}`}
              aria-label={group.label}
              aria-expanded={open}
              aria-controls={`app-${group.id}-submenu`}
              onClick={() => {
                onExpand?.();
                setOpened((current) => ({ ...current, [group.id]: !open }));
              }}
            >
              <DsIcon name={group.items[0]?.icon ?? "dashboard"} size={18} />
              {!collapsed ? (
                <>
                  <span>{group.label}</span>
                  <DsIcon name={open ? "collapse" : "expand"} size={14} />
                </>
              ) : null}
            </button>
            <div
              id={`app-${group.id}-submenu`}
              hidden={!open}
              className={styles.submenu}
            >
              {group.items.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  className={`ds-sidebar-item ds-sidebar-item--sub ${item.id === activeId ? "ds-sidebar-item--active" : ""}`}
                  aria-current={item.id === activeId ? "page" : undefined}
                  onClick={() => onSelect(item.id)}
                >
                  <DsIcon name={item.icon ?? "dashboard"} size={16} />
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </nav>
  );
}
