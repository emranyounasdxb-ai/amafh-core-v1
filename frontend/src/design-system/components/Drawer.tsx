import { useCallback, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { DsIcon } from "../icons";
import { cx } from "../lib/cx";
import { useFocusTrap } from "../lib/useFocusTrap";
import { DesignSystemRoot } from "./DesignSystemRoot";
import { IconButton } from "./IconButton";

export type DrawerSize = "standard" | "wide";
export type DrawerSide = "end" | "start";

export function Drawer({
  open,
  title,
  children,
  footer,
  onClose,
  size = "standard",
  side = "end",
  closeOnOutside = true,
  closeOnEscape = true,
  busy = false,
  description,
}: {
  open: boolean;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
  size?: DrawerSize;
  side?: DrawerSide;
  closeOnOutside?: boolean;
  closeOnEscape?: boolean;
  busy?: boolean;
  description?: ReactNode;
}) {
  const panelRef = useRef<HTMLElement>(null);
  const close = useCallback(() => {
    if (!busy) onClose();
  }, [busy, onClose]);
  useFocusTrap(open, panelRef, closeOnEscape ? close : undefined);
  if (!open) return null;
  return createPortal(
    <DesignSystemRoot>
      <div
        className={cx("ds-drawer-backdrop", `ds-drawer-backdrop--${side}`)}
        onMouseDown={() => {
          if (closeOnOutside) close();
        }}
      >
        <aside
          ref={panelRef}
          className={cx(
            "ds-drawer",
            `ds-drawer--${size}`,
            `ds-drawer--${side}`,
          )}
          role="dialog"
          aria-modal="true"
          aria-busy={busy || undefined}
          aria-label={typeof title === "string" ? title : undefined}
          tabIndex={-1}
          onMouseDown={(event) => event.stopPropagation()}
        >
          <header className="ds-drawer__header">
            <div className="ds-dialog__heading">
              <h2 className="ds-drawer__title">{title}</h2>
              {description ? (
                <p className="ds-dialog__description">{description}</p>
              ) : null}
            </div>
            <IconButton
              label="Close panel"
              variant="ghost"
              size="compact"
              tooltip={false}
              disabled={busy}
              onClick={close}
            >
              <DsIcon name="close" size={16} />
            </IconButton>
          </header>
          <div className="ds-drawer__body">{children}</div>
          {footer ? (
            <footer className="ds-drawer__footer">{footer}</footer>
          ) : null}
        </aside>
      </div>
    </DesignSystemRoot>,
    document.body,
  );
}
