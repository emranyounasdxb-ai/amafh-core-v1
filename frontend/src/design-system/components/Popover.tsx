import { useId, useRef, useState, type ReactNode } from "react";
import { PositionedOverlay } from "./PositionedOverlay";
import type { OverlayPlacement } from "../lib/positionOverlay";

export function Popover({
  trigger,
  children,
  open: openProp,
  onOpenChange,
  placement = "bottom-start",
  label,
  closeOnOutside = true,
  className,
}: {
  trigger: ReactNode;
  children: ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  placement?: OverlayPlacement;
  label?: string;
  closeOnOutside?: boolean;
  className?: string;
}) {
  const fallbackId = useId();
  const [uncontrolled, setUncontrolled] = useState(false);
  const open = openProp ?? uncontrolled;
  const setOpen = (next: boolean) => {
    onOpenChange?.(next);
    if (openProp === undefined) setUncontrolled(next);
  };
  const anchorRef = useRef<HTMLDivElement>(null);
  return (
    <div className="ds-anchor" ref={anchorRef}>
      <div className="ds-anchor__trigger" onClick={() => setOpen(!open)}>
        {trigger}
      </div>
      <PositionedOverlay
        open={open}
        anchorRef={anchorRef}
        placement={placement}
        closeOnOutside={closeOnOutside}
        onClose={() => setOpen(false)}
        label={label ?? fallbackId}
        trapFocus
        className={className}
      >
        {children}
      </PositionedOverlay>
    </div>
  );
}
