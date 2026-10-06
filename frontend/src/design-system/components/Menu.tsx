import { Fragment, useRef, useState, type ReactNode } from "react";
import { cx } from "../lib/cx";
import { PositionedOverlay } from "./PositionedOverlay";

export type MenuItem = {
  id: string;
  label: string;
  description?: string;
  icon?: ReactNode;
  disabled?: boolean;
  danger?: boolean;
  separator?: boolean;
  onSelect?: () => void;
};

function MenuItems({
  items,
  onClose,
}: {
  items: MenuItem[];
  onClose: () => void;
}) {
  return (
    <>
      {items.map((item) => (
        <Fragment key={item.id}>
          {item.separator ? <div className="ds-menu__sep" /> : null}
          <button
            type="button"
            role="menuitem"
            className={cx(
              "ds-menu__item",
              item.danger && "ds-menu__item--danger",
            )}
            disabled={item.disabled}
            onClick={() => {
              if (item.disabled) return;
              onClose();
              item.onSelect?.();
            }}
          >
            {item.icon}
            <span className="ds-menu__copy">
              <strong>{item.label}</strong>
              {item.description ? <em>{item.description}</em> : null}
            </span>
          </button>
        </Fragment>
      ))}
    </>
  );
}

export function Menu({
  trigger,
  items,
  label,
  align = "bottom-end",
  open: openProp,
  onOpenChange,
}: {
  trigger: ReactNode;
  items: MenuItem[];
  label: string;
  align?: "bottom-start" | "bottom-end" | "top-start" | "top-end";
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [uncontrolled, setUncontrolled] = useState(false);
  const open = openProp ?? uncontrolled;
  const setOpen = (next: boolean) => {
    onOpenChange?.(next);
    if (openProp === undefined) setUncontrolled(next);
  };
  const anchorRef = useRef<HTMLDivElement>(null);
  return (
    <div className="ds-anchor ds-anchor--fit" ref={anchorRef}>
      <div className="ds-anchor__trigger" onClick={() => setOpen(!open)}>
        {trigger}
      </div>
      <PositionedOverlay
        open={open}
        anchorRef={anchorRef}
        placement={align}
        onClose={() => setOpen(false)}
        role="menu"
        label={label}
        trapFocus
        matchAnchorWidth={false}
        className="ds-menu"
      >
        <MenuItems items={items} onClose={() => setOpen(false)} />
      </PositionedOverlay>
    </div>
  );
}

export function ContextMenu({
  children,
  items,
  label,
}: {
  children: ReactNode;
  items: MenuItem[];
  label: string;
}) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLDivElement>(null);
  return (
    <div
      className="ds-anchor"
      ref={anchorRef}
      onContextMenu={(event) => {
        event.preventDefault();
        setOpen(true);
      }}
    >
      {children}
      <PositionedOverlay
        open={open}
        anchorRef={anchorRef}
        placement="bottom-start"
        onClose={() => setOpen(false)}
        role="menu"
        label={label}
        trapFocus
        matchAnchorWidth={false}
        className="ds-menu"
      >
        <MenuItems items={items} onClose={() => setOpen(false)} />
      </PositionedOverlay>
    </div>
  );
}
