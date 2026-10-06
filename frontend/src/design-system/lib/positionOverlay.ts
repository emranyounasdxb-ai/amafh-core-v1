export type OverlayPlacement =
  | "bottom-start"
  | "bottom-end"
  | "top-start"
  | "top-end"
  | "right-start"
  | "right-end"
  | "auto";

export function positionOverlay(
  anchor: DOMRect,
  overlay: { width: number; height: number },
  placement: OverlayPlacement = "auto",
  padding = 8,
) {
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  if (placement.startsWith("right")) {
    const width = overlay.width || 220;
    const height = Math.min(
      overlay.height || 280,
      viewportHeight - padding * 2,
    );
    let left = anchor.right + 6;
    if (left + width > viewportWidth - padding) {
      left = Math.max(padding, anchor.left - width - 6);
    }
    let top = placement === "right-end" ? anchor.bottom - height : anchor.top;
    if (top < padding) top = padding;
    if (top + height > viewportHeight - padding) {
      top = Math.max(padding, viewportHeight - height - padding);
    }
    return {
      top,
      left,
      width,
      maxHeight: height,
      maxWidth: Math.max(160, viewportWidth - left - padding),
      placement: "right" as const,
    };
  }
  const spaceBelow = viewportHeight - anchor.bottom - padding;
  const spaceAbove = anchor.top - padding;
  const needed = overlay.height || 200;
  const preferTop =
    placement.startsWith("top") ||
    (placement === "auto" && spaceBelow < 200 && spaceAbove > spaceBelow) ||
    (placement.startsWith("bottom") &&
      needed > spaceBelow &&
      spaceAbove > spaceBelow);
  const alignEnd = placement.endsWith("end");
  const height = Math.min(
    overlay.height || 280,
    Math.max(160, preferTop ? spaceAbove : spaceBelow),
  );
  const width = Math.max(overlay.width, anchor.width);
  let top = preferTop ? anchor.top - height - 6 : anchor.bottom + 6;
  let left = alignEnd ? anchor.right - width : anchor.left;

  if (top < padding) top = padding;
  if (top + height > viewportHeight - padding) {
    top = Math.max(padding, viewportHeight - height - padding);
  }
  if (left + width > viewportWidth - padding) {
    left = Math.max(padding, viewportWidth - width - padding);
  }
  if (left < padding) left = padding;

  return {
    top,
    left,
    width,
    maxHeight: height,
    maxWidth: Math.max(160, viewportWidth - left - padding),
    placement: preferTop ? "top" : "bottom",
  };
}
