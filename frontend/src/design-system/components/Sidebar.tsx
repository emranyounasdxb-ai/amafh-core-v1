import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { cx } from "../lib/cx";
import { DsIcon, type DsIconName } from "../icons";
import { useFocusTrap } from "../lib/useFocusTrap";
import { Avatar } from "./Avatar";
import { DesignSystemRoot } from "./DesignSystemRoot";
import { Divider, ScrollArea } from "./Layout";
import { IconButton } from "./IconButton";
import { Menu, type MenuItem } from "./Menu";
import { PositionedOverlay } from "./PositionedOverlay";
import { ProfileCard } from "./Profile";
import { StatusBadge, type StatusTone } from "./StatusBadge";
import { Tooltip } from "./Tooltip";

const SidebarUiContext = createContext({ collapsed: false });

function useSidebarCollapsed() {
  return useContext(SidebarUiContext).collapsed;
}

export type SidebarBadgeValue = {
  count?: number;
  max?: number;
  tone?: Extract<StatusTone, "brand" | "danger" | "neutral">;
  dot?: boolean;
  label?: string;
};

export type SidebarLeafItem = {
  id: string;
  label: string;
  icon?: DsIconName;
  disabled?: boolean;
  loading?: boolean;
  badge?: SidebarBadgeValue;
  tooltip?: string;
};

export type SidebarNavItem = SidebarLeafItem & {
  children?: SidebarLeafItem[];
};

export type SidebarNavGroup = {
  id: string;
  label?: string;
  collapsible?: boolean;
  items: SidebarNavItem[];
};

function formatBadgeCount(count: number, max = 99) {
  return count > max ? `${max}+` : String(count);
}

export function SidebarBadge({
  count,
  max = 99,
  tone = "brand",
  dot = false,
  label,
  collapsed = false,
}: SidebarBadgeValue & { collapsed?: boolean }) {
  if (dot && (count == null || count === 0)) {
    return (
      <span
        className={cx(
          "ds-sidebar-badge",
          "ds-sidebar-badge--dot",
          collapsed && "ds-sidebar-badge--corner",
        )}
        aria-label={label ?? "Has updates"}
      />
    );
  }
  if (count == null || count <= 0) return null;
  const text = formatBadgeCount(count, max);
  return (
    <span
      className={cx(
        "ds-sidebar-badge",
        `ds-sidebar-badge--${tone}`,
        collapsed && "ds-sidebar-badge--corner",
      )}
      aria-label={label ?? `${count} items`}
    >
      {text}
    </span>
  );
}

export function SidebarTooltip({
  content,
  children,
}: {
  content: ReactNode;
  children: ReactNode;
}) {
  if (!content) return <>{children}</>;
  return (
    <Tooltip content={content} placement="right-start" delay={120}>
      <span className="ds-sidebar-tooltip">{children}</span>
    </Tooltip>
  );
}

export function SidebarDivider() {
  return <Divider />;
}

export function SidebarScrollArea({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <ScrollArea className={cx("ds-sidebar-scroll", className)}>
      {children}
    </ScrollArea>
  );
}

export function SidebarHeader({ children }: { children: ReactNode }) {
  return <div className="ds-sidebar-header">{children}</div>;
}

export function SidebarBrand({
  name = "AMAFH",
  logoSrc = "/production/amafh-core-full-logo-exact.svg",
  markSrc = "/production/amafh-core-mark-exact.svg",
  environment,
  collapsed,
}: {
  name?: string;
  logoSrc?: string;
  markSrc?: string;
  environment?: ReactNode;
  collapsed?: boolean;
}) {
  const fromContext = useSidebarCollapsed();
  const isCollapsed = collapsed ?? fromContext;
  return (
    <div className="ds-sidebar-brand">
      <img
        className={
          isCollapsed ? "ds-sidebar-brand__mark" : "ds-sidebar-brand__logo"
        }
        src={isCollapsed ? markSrc : logoSrc}
        alt=""
        width={isCollapsed ? 28 : 120}
        height={28}
      />
      <span className="ds-sidebar-brand__copy">
        {isCollapsed ? null : environment ? (
          <StatusBadge tone="brand">{environment}</StatusBadge>
        ) : null}
      </span>
      <span className="ds-sr-only">{name}</span>
    </div>
  );
}

export function SidebarToggle({
  collapsed,
  onClick,
}: {
  collapsed: boolean;
  onClick: () => void;
}) {
  return (
    <IconButton
      label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      variant="ghost"
      size="compact"
      onClick={onClick}
    >
      <DsIcon name={collapsed ? "sidebarOpen" : "sidebarClose"} size={18} />
    </IconButton>
  );
}

export function SidebarContent({ children }: { children: ReactNode }) {
  return <div className="ds-sidebar-content">{children}</div>;
}

export function SidebarFooter({ children }: { children: ReactNode }) {
  return <div className="ds-sidebar-footer">{children}</div>;
}

export function SidebarGroupLabel({
  children,
  collapsed,
}: {
  children: ReactNode;
  collapsed?: boolean;
}) {
  const contextCollapsed = useSidebarCollapsed();
  const isCollapsed = collapsed ?? contextCollapsed;
  if (isCollapsed) return null;
  return <p className="ds-sidebar-group__label">{children}</p>;
}

export function SidebarGroup({
  id,
  label,
  collapsible,
  open = true,
  onOpenChange,
  children,
}: {
  id?: string;
  label?: ReactNode;
  collapsible?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: ReactNode;
}) {
  const collapsed = useSidebarCollapsed();
  if (collapsible && label) {
    return (
      <div className="ds-sidebar-group" data-id={id}>
        {collapsed ? null : (
          <button
            type="button"
            className="ds-sidebar-group__trigger"
            aria-expanded={open}
            onClick={() => onOpenChange?.(!open)}
          >
            <span>{label}</span>
            <DsIcon name={open ? "collapse" : "expand"} size={14} />
          </button>
        )}
        {open || collapsed ? (
          <div className="ds-sidebar-group__items">{children}</div>
        ) : null}
      </div>
    );
  }
  return (
    <div className="ds-sidebar-group" data-id={id}>
      {label ? <SidebarGroupLabel>{label}</SidebarGroupLabel> : null}
      <div className="ds-sidebar-group__items">{children}</div>
    </div>
  );
}

function ItemIcon({
  icon,
  loading,
  size = 18,
}: {
  icon?: DsIconName;
  loading?: boolean;
  size?: 16 | 18;
}) {
  if (loading) return <span className="ds-spinner" aria-hidden="true" />;
  if (!icon) return <span className="ds-sidebar-item__icon-slot" />;
  return <DsIcon name={icon} size={size} />;
}

export function SidebarItem({
  id,
  label,
  icon,
  active = false,
  disabled = false,
  loading = false,
  badge,
  tooltip,
  current,
  expanded,
  hasChildren = false,
  onClick,
  onToggle,
}: {
  id: string;
  label: string;
  icon?: DsIconName;
  active?: boolean;
  disabled?: boolean;
  loading?: boolean;
  badge?: SidebarBadgeValue;
  tooltip?: string;
  current?: boolean;
  expanded?: boolean;
  hasChildren?: boolean;
  onClick?: () => void;
  onToggle?: () => void;
}) {
  const collapsed = useSidebarCollapsed();
  const tip = collapsed || tooltip ? (tooltip ?? label) : undefined;
  const button = (
    <button
      type="button"
      className={cx(
        "ds-sidebar-item",
        active && "ds-sidebar-item--active",
        disabled && "ds-sidebar-item--disabled",
        hasChildren && "ds-sidebar-item--parent",
      )}
      aria-label={collapsed ? label : undefined}
      aria-current={current ? "page" : undefined}
      aria-expanded={hasChildren ? expanded : undefined}
      aria-controls={hasChildren && !collapsed ? `${id}-submenu` : undefined}
      aria-busy={loading || undefined}
      disabled={disabled || loading}
      onClick={() => {
        if (disabled) return;
        if (hasChildren) onToggle?.();
        else onClick?.();
      }}
    >
      <span className="ds-sidebar-item__icon">
        <ItemIcon icon={icon} loading={loading} />
      </span>
      <span className="ds-sidebar-item__label">{label}</span>
      {badge ? <SidebarBadge {...badge} collapsed={collapsed} /> : null}
      {hasChildren && !collapsed ? (
        <DsIcon name={expanded ? "collapse" : "expand"} size={14} />
      ) : null}
    </button>
  );
  if (collapsed && hasChildren) return button;
  if (disabled && tooltip) {
    return <SidebarTooltip content={tooltip}>{button}</SidebarTooltip>;
  }
  if (collapsed) {
    return <SidebarTooltip content={tip}>{button}</SidebarTooltip>;
  }
  return (
    <SidebarTooltip content={label.length > 22 ? label : undefined}>
      {button}
    </SidebarTooltip>
  );
}

export function SidebarSubmenuItem({
  id,
  label,
  icon,
  active = false,
  disabled = false,
  badge,
  tooltip,
  onClick,
}: {
  id: string;
  label: string;
  icon?: DsIconName;
  active?: boolean;
  disabled?: boolean;
  badge?: SidebarBadgeValue;
  tooltip?: string;
  onClick?: () => void;
}) {
  const button = (
    <button
      type="button"
      className={cx(
        "ds-sidebar-item",
        "ds-sidebar-item--sub",
        active && "ds-sidebar-item--active",
      )}
      aria-current={active ? "page" : undefined}
      disabled={disabled}
      onClick={onClick}
      data-id={id}
    >
      {icon ? (
        <span className="ds-sidebar-item__icon">
          <ItemIcon icon={icon} size={16} />
        </span>
      ) : null}
      <span className="ds-sidebar-item__label">{label}</span>
      {badge ? <SidebarBadge {...badge} /> : null}
      {tooltip && disabled ? (
        <span className="ds-sr-only">{tooltip}</span>
      ) : null}
    </button>
  );
  const tip =
    disabled && tooltip ? tooltip : label.length > 22 ? label : undefined;
  return <SidebarTooltip content={tip}>{button}</SidebarTooltip>;
}

export function SidebarSubmenu({
  id,
  open,
  children,
}: {
  id: string;
  open: boolean;
  children: ReactNode;
}) {
  const collapsed = useSidebarCollapsed();
  if (collapsed || !open) return null;
  return (
    <div className="ds-sidebar-submenu" id={`${id}-submenu`} role="group">
      {children}
    </div>
  );
}

export function SidebarNavigation({
  groups,
  activeId,
  onSelect,
  openSubmenus,
  onOpenSubmenusChange,
  openGroups,
  onOpenGroupsChange,
  label = "Primary",
}: {
  groups: SidebarNavGroup[];
  activeId?: string;
  onSelect?: (id: string) => void;
  openSubmenus?: string[];
  onOpenSubmenusChange?: (ids: string[]) => void;
  openGroups?: string[];
  onOpenGroupsChange?: (ids: string[]) => void;
  label?: string;
}) {
  const collapsed = useSidebarCollapsed();
  const [uncontrolledSubs, setUncontrolledSubs] = useState<string[]>([]);
  const [uncontrolledGroups, setUncontrolledGroups] = useState<string[]>(() =>
    groups.filter((group) => group.collapsible).map((group) => group.id),
  );
  const [flyoutId, setFlyoutId] = useState<string | null>(null);
  const flyoutAnchor = useRef<HTMLDivElement>(null);
  const submenuIds = openSubmenus ?? uncontrolledSubs;
  const setSubmenus = onOpenSubmenusChange ?? setUncontrolledSubs;
  const groupIds = openGroups ?? uncontrolledGroups;
  const setGroups = onOpenGroupsChange ?? setUncontrolledGroups;

  const parentOfActive = useMemo(() => {
    for (const group of groups) {
      for (const item of group.items) {
        if (item.children?.some((child) => child.id === activeId)) {
          return item.id;
        }
      }
    }
    return null;
  }, [activeId, groups]);

  const isOpen = (id: string) =>
    submenuIds.includes(id) || parentOfActive === id;

  const toggleSub = (id: string) => {
    const next = submenuIds.includes(id)
      ? submenuIds.filter((value) => value !== id)
      : [...submenuIds, id];
    if (parentOfActive === id && submenuIds.includes(id)) return;
    setSubmenus(next);
  };

  const onNavKey = (event: KeyboardEvent<HTMLElement>) => {
    if (
      event.key !== "ArrowDown" &&
      event.key !== "ArrowUp" &&
      event.key !== "Home" &&
      event.key !== "End"
    ) {
      return;
    }
    const buttons = [
      ...event.currentTarget.querySelectorAll<HTMLButtonElement>(
        ".ds-sidebar-item:not(:disabled)",
      ),
    ];
    if (!buttons.length) return;
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    event.preventDefault();
    if (event.key === "Home") buttons[0]?.focus();
    if (event.key === "End") buttons[buttons.length - 1]?.focus();
    if (event.key === "ArrowDown") {
      buttons[(index + 1 + buttons.length) % buttons.length]?.focus();
    }
    if (event.key === "ArrowUp") {
      buttons[(index - 1 + buttons.length) % buttons.length]?.focus();
    }
  };

  const flyoutItem = groups
    .flatMap((group) => group.items)
    .find((item) => item.id === flyoutId);

  return (
    <nav className="ds-sidebar-nav" aria-label={label} onKeyDown={onNavKey}>
      {groups.map((group) => (
        <SidebarGroup
          key={group.id}
          id={group.id}
          label={group.label}
          collapsible={group.collapsible}
          open={!group.collapsible || groupIds.includes(group.id)}
          onOpenChange={(open) => {
            setGroups(
              open
                ? [...groupIds, group.id]
                : groupIds.filter((value) => value !== group.id),
            );
          }}
        >
          {group.items.map((item) => {
            const childActive = item.children?.some(
              (child) => child.id === activeId,
            );
            const itemActive = item.id === activeId || Boolean(childActive);
            const expanded = isOpen(item.id);
            return (
              <div
                key={item.id}
                className="ds-sidebar-branch"
                ref={item.id === flyoutId ? flyoutAnchor : undefined}
              >
                <SidebarItem
                  id={item.id}
                  label={item.label}
                  icon={item.icon}
                  active={itemActive}
                  current={item.id === activeId}
                  disabled={item.disabled}
                  loading={item.loading}
                  badge={item.badge}
                  tooltip={item.tooltip}
                  hasChildren={Boolean(item.children?.length)}
                  expanded={collapsed ? flyoutId === item.id : expanded}
                  onClick={() => onSelect?.(item.id)}
                  onToggle={() => {
                    if (collapsed && item.children?.length) {
                      setFlyoutId(flyoutId === item.id ? null : item.id);
                      return;
                    }
                    toggleSub(item.id);
                  }}
                />
                {item.children?.length ? (
                  <SidebarSubmenu id={item.id} open={expanded}>
                    {item.children.map((child) => (
                      <SidebarSubmenuItem
                        key={child.id}
                        id={child.id}
                        label={child.label}
                        icon={child.icon}
                        active={child.id === activeId}
                        disabled={child.disabled}
                        badge={child.badge}
                        tooltip={child.tooltip}
                        onClick={() => onSelect?.(child.id)}
                      />
                    ))}
                  </SidebarSubmenu>
                ) : null}
              </div>
            );
          })}
        </SidebarGroup>
      ))}
      <PositionedOverlay
        open={Boolean(flyoutItem)}
        anchorRef={flyoutAnchor}
        placement="right-start"
        onClose={() => setFlyoutId(null)}
        role="menu"
        label={flyoutItem?.label ?? "Section"}
        trapFocus
        className="ds-menu ds-sidebar-flyout"
      >
        <div>
          <p className="ds-sidebar-flyout__title">{flyoutItem?.label}</p>
          {flyoutItem?.children?.map((child) => (
            <SidebarSubmenuItem
              key={child.id}
              id={child.id}
              label={child.label}
              icon={child.icon}
              active={child.id === activeId}
              disabled={child.disabled}
              badge={child.badge}
              onClick={() => {
                onSelect?.(child.id);
                setFlyoutId(null);
              }}
            />
          ))}
        </div>
      </PositionedOverlay>
    </nav>
  );
}

export function SidebarProfile({
  name,
  designation,
  src,
  items,
  collapsed,
}: {
  name: string;
  designation?: string;
  src?: string;
  items?: MenuItem[];
  collapsed?: boolean;
}) {
  const fromContext = useSidebarCollapsed();
  const isCollapsed = collapsed ?? fromContext;
  const menuItems = items ?? [
    {
      id: "profile",
      label: "View profile",
      icon: <DsIcon name="user" size={16} />,
    },
    {
      id: "settings",
      label: "Account settings",
      icon: <DsIcon name="settings" size={16} />,
    },
    {
      id: "out",
      label: "Sign out",
      icon: <DsIcon name="signOut" size={16} />,
      separator: true,
      danger: true,
    },
  ];
  const trigger = isCollapsed ? (
    <button
      type="button"
      className="ds-sidebar-profile ds-sidebar-profile--collapsed"
      aria-label={`${name}${designation ? `, ${designation}` : ""}`}
    >
      <Avatar name={name} src={src} size="sm" />
    </button>
  ) : (
    <ProfileCard name={name} designation={designation} src={src} menu />
  );
  const menu = (
    <Menu
      label="Account"
      align="top-start"
      trigger={trigger}
      items={menuItems}
    />
  );
  if (isCollapsed) {
    return (
      <SidebarTooltip
        content={`${name}${designation ? ` · ${designation}` : ""}`}
      >
        {menu}
      </SidebarTooltip>
    );
  }
  return <div className="ds-sidebar-profile">{menu}</div>;
}

export function SidebarMobileTrigger({
  onClick,
  label = "Open navigation",
}: {
  onClick: () => void;
  label?: string;
}) {
  return (
    <IconButton label={label} variant="secondary" onClick={onClick}>
      <DsIcon name="sidebarOpen" size={18} />
    </IconButton>
  );
}

export function SidebarMobileDrawer({
  open,
  onClose,
  children,
  label = "Navigation",
  closeOnOutside = true,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  label?: string;
  closeOnOutside?: boolean;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const close = useCallback(() => onClose(), [onClose]);
  useFocusTrap(open, panelRef, close);
  if (!open) return null;
  return createPortal(
    <DesignSystemRoot>
      <div
        className="ds-drawer-backdrop ds-drawer-backdrop--start"
        onMouseDown={() => {
          if (closeOnOutside) close();
        }}
      >
        <div
          ref={panelRef}
          className="ds-sidebar-drawer"
          role="dialog"
          aria-modal="true"
          aria-label={label}
          tabIndex={-1}
          onMouseDown={(event) => event.stopPropagation()}
        >
          {children}
        </div>
      </div>
    </DesignSystemRoot>,
    document.body,
  );
}

export function Sidebar({
  collapsed = false,
  label = "Application",
  children,
  className,
}: {
  collapsed?: boolean;
  label?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <aside
      className={cx(
        "ds-sidebar",
        collapsed && "ds-sidebar--collapsed",
        className,
      )}
      aria-label={label}
    >
      <SidebarUiContext.Provider value={{ collapsed }}>
        {children}
      </SidebarUiContext.Provider>
    </aside>
  );
}
