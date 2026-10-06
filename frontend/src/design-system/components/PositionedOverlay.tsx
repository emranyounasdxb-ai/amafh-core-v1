import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { createPortal } from "react-dom";
import { cx } from "../lib/cx";
import { positionOverlay, type OverlayPlacement } from "../lib/positionOverlay";
import { useFocusTrap } from "../lib/useFocusTrap";
import { DesignSystemRoot } from "./DesignSystemRoot";

export function PositionedOverlay({
  open,
  anchorRef,
  children,
  placement = "auto",
  closeOnOutside = true,
  closeOnEscape = true,
  onClose,
  role = "dialog",
  label,
  className,
  trapFocus = false,
  restoreFocus = true,
  matchAnchorWidth = false,
  lockHeight = true,
}: {
  open: boolean;
  anchorRef: RefObject<HTMLElement | null>;
  children: ReactNode;
  placement?: OverlayPlacement;
  closeOnOutside?: boolean;
  closeOnEscape?: boolean;
  onClose: () => void;
  role?: "dialog" | "listbox" | "menu" | "tooltip" | "presentation";
  label?: string;
  className?: string;
  trapFocus?: boolean;
  restoreFocus?: boolean;
  matchAnchorWidth?: boolean;
  lockHeight?: boolean;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const [coords, setCoords] = useState({
    top: 0,
    left: 0,
    width: 240,
    maxHeight: 320,
    maxWidth: 360,
  });

  const update = useCallback(() => {
    const anchor = anchorRef.current?.getBoundingClientRect();
    const panel = panelRef.current?.getBoundingClientRect();
    if (!anchor) return;
    const next = positionOverlay(
      anchor,
      {
        width: matchAnchorWidth
          ? anchor.width
          : panel?.width && panel.width > 0
            ? panel.width
            : 240,
        height: panel?.height && panel.height > 0 ? panel.height : 1,
      },
      placement,
    );
    setCoords(next);
  }, [anchorRef, matchAnchorWidth, placement]);

  useLayoutEffect(() => {
    if (!open) return;
    update();
    const panel = panelRef.current;
    const observer =
      panel && typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(() => update())
        : null;
    if (panel && observer) observer.observe(panel);
    const frame = window.requestAnimationFrame(() => update());
    return () => {
      observer?.disconnect();
      window.cancelAnimationFrame(frame);
    };
  }, [open, update]);

  useEffect(() => {
    if (!open) return;
    const onWin = () => update();
    window.addEventListener("resize", onWin);
    window.addEventListener("scroll", onWin, true);
    return () => {
      window.removeEventListener("resize", onWin);
      window.removeEventListener("scroll", onWin, true);
    };
  }, [open, update]);

  useFocusTrap(
    open && trapFocus,
    panelRef,
    closeOnEscape ? () => onCloseRef.current() : undefined,
    restoreFocus,
  );

  useEffect(() => {
    if (!open || !closeOnOutside) return;
    const onPointer = (event: MouseEvent) => {
      const target = event.target;
      const panel = panelRef.current;
      if (target instanceof Node && panel?.contains(target)) return;
      if (target instanceof Node && anchorRef.current?.contains(target)) return;
      if (target instanceof Element && panel) {
        const other = target.closest(".ds-popover");
        if (
          other &&
          other !== panel &&
          (panel.compareDocumentPosition(other) &
            Node.DOCUMENT_POSITION_FOLLOWING) !==
            0
        ) {
          return;
        }
      }
      event.stopPropagation();
      onCloseRef.current();
    };
    document.addEventListener("mousedown", onPointer, true);
    return () => document.removeEventListener("mousedown", onPointer, true);
  }, [anchorRef, closeOnOutside, open]);

  useEffect(() => {
    if (!open || trapFocus || !closeOnEscape) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      onCloseRef.current();
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [closeOnEscape, open, trapFocus]);

  if (!open) return null;
  return createPortal(
    <DesignSystemRoot>
      <div
        ref={panelRef}
        className={cx("ds-popover", className)}
        role={role}
        aria-label={label}
        tabIndex={-1}
        style={{
          top: coords.top,
          left: coords.left,
          width: matchAnchorWidth ? coords.width : "max-content",
          minWidth: matchAnchorWidth ? coords.width : undefined,
          maxHeight: lockHeight ? coords.maxHeight : undefined,
          maxWidth: coords.maxWidth,
        }}
      >
        {children}
      </div>
    </DesignSystemRoot>,
    document.body,
  );
}
