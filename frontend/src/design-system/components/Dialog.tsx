import { useCallback, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { DsIcon } from "../icons";
import { cx } from "../lib/cx";
import { useFocusTrap } from "../lib/useFocusTrap";
import { DesignSystemRoot } from "./DesignSystemRoot";
import { IconButton } from "./IconButton";

export type DialogSize = "sm" | "md" | "lg" | "xl" | "fullscreen";

export function Dialog({
  open,
  title,
  children,
  footer,
  size = "lg",
  onClose,
  closeOnOutside = true,
  closeOnEscape = true,
  fullscreenOnNarrow = true,
  busy = false,
  hideClose = false,
  role = "dialog",
  description,
}: {
  open: boolean;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: DialogSize;
  onClose: () => void;
  closeOnOutside?: boolean;
  closeOnEscape?: boolean;
  fullscreenOnNarrow?: boolean;
  busy?: boolean;
  hideClose?: boolean;
  role?: "dialog" | "alertdialog";
  description?: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const close = useCallback(() => {
    if (!busy) onClose();
  }, [busy, onClose]);
  useFocusTrap(open, panelRef, closeOnEscape ? close : undefined);
  if (!open) return null;
  return createPortal(
    <DesignSystemRoot>
      <div
        className="ds-dialog-backdrop"
        onMouseDown={() => {
          if (closeOnOutside) close();
        }}
      >
        <div
          ref={panelRef}
          className={cx(
            "ds-dialog",
            `ds-dialog--${size}`,
            fullscreenOnNarrow && "ds-dialog--narrow-full",
            busy && "ds-dialog--busy",
          )}
          role={role}
          aria-modal="true"
          aria-busy={busy || undefined}
          aria-label={typeof title === "string" ? title : undefined}
          tabIndex={-1}
          onMouseDown={(event) => event.stopPropagation()}
        >
          <header className="ds-dialog__header">
            <div className="ds-dialog__heading">
              <h2 className="ds-dialog__title">{title}</h2>
              {description ? (
                <p className="ds-dialog__description">{description}</p>
              ) : null}
            </div>
            {hideClose ? null : (
              <IconButton
                label="Close dialog"
                variant="ghost"
                size="compact"
                tooltip={false}
                disabled={busy}
                onClick={close}
              >
                <DsIcon name="close" size={16} />
              </IconButton>
            )}
          </header>
          <div className="ds-dialog__body">{children}</div>
          {footer ? (
            <footer className="ds-dialog__footer">{footer}</footer>
          ) : null}
        </div>
      </div>
    </DesignSystemRoot>,
    document.body,
  );
}
