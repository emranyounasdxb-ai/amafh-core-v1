import { useCallback, useEffect, useRef } from "react";

type FocusTarget = () => HTMLElement | null | undefined;

function focusLost() {
  const active = document.activeElement;
  return !(
    active instanceof HTMLElement &&
    active !== document.body &&
    active.isConnected
  );
}

function recoverFocus(target: FocusTarget) {
  window.requestAnimationFrame(() =>
    window.setTimeout(() => {
      if (focusLost()) target()?.focus();
    }, 0),
  );
}

/**
 * Returns `arm`, called after a successful save. Focus moves to `target` only
 * when the control that opened the command no longer exists, both right after
 * the dialog closes and again when `refreshed` changes with the reloaded data.
 */
export function useFocusRecovery(refreshed: unknown, target: FocusTarget) {
  const armed = useRef(false);
  const targetRef = useRef(target);
  targetRef.current = target;
  useEffect(() => {
    if (!armed.current) return;
    armed.current = false;
    recoverFocus(() => targetRef.current());
  }, [refreshed]);
  return useCallback(() => {
    armed.current = true;
    recoverFocus(() => targetRef.current());
  }, []);
}
