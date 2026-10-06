import { useId, useRef, useState, type ReactNode } from "react";
import type { OverlayPlacement } from "../lib/positionOverlay";
import { PositionedOverlay } from "./PositionedOverlay";

export function Tooltip({
  content,
  children,
  delay = 280,
  placement = "top-start",
}: {
  content: ReactNode;
  children: ReactNode;
  delay?: number;
  placement?: OverlayPlacement;
}) {
  const labelId = useId();
  const [open, setOpen] = useState(false);
  const timer = useRef<number>(0);
  const anchorRef = useRef<HTMLDivElement>(null);
  const show = () => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setOpen(true), delay);
  };
  const hide = () => {
    window.clearTimeout(timer.current);
    setOpen(false);
  };
  return (
    <div
      className="ds-anchor"
      ref={anchorRef}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      <PositionedOverlay
        open={open}
        anchorRef={anchorRef}
        placement={placement}
        closeOnOutside={false}
        closeOnEscape
        onClose={hide}
        role="tooltip"
        label={typeof content === "string" ? content : labelId}
        className="ds-tooltip"
      >
        {content}
      </PositionedOverlay>
    </div>
  );
}
