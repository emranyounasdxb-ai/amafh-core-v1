import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE =
  'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

const escapeHandlers: Array<() => void> = [];

function focusables(container: HTMLElement) {
  return [...container.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
    (node) =>
      !node.hasAttribute("disabled") && node.getClientRects().length > 0,
  );
}

export function useFocusTrap(
  active: boolean,
  containerRef: RefObject<HTMLElement | null>,
  onEscape?: () => void,
  restore = true,
) {
  const onEscapeRef = useRef(onEscape);
  onEscapeRef.current = onEscape;
  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    const previous = document.activeElement as HTMLElement | null;
    if (!container) return;
    const items = focusables(container);
    (items[0] ?? container).focus();
    const handleEscape = () => onEscapeRef.current?.();
    if (onEscapeRef.current) escapeHandlers.push(handleEscape);

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (!onEscapeRef.current || escapeHandlers.at(-1) !== handleEscape)
          return;
        event.preventDefault();
        event.stopImmediatePropagation();
        onEscapeRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const nodes = focusables(container);
      if (!nodes.length) {
        event.preventDefault();
        container.focus();
        return;
      }
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      const index = escapeHandlers.lastIndexOf(handleEscape);
      if (index >= 0) escapeHandlers.splice(index, 1);
      if (restore) previous?.focus();
    };
  }, [active, containerRef, restore]);
}
