import type { ApiClient } from "../api/http";

// Leading-edge signals have no delayed timer that could renew after sleep.
// Coalescing high-frequency pointer events can expire a session at most 1s early.
export function watchHumanActivity(
  api: ApiClient,
  target: Window = window,
  now: () => number = () => performance.now(),
) {
  const generation = api.sessionGeneration;
  let lastSignal = -Infinity;
  const signal = (event: Event) => {
    if (!event.isTrusted || api.sessionGeneration !== generation) return;
    const instant = now();
    if (instant >= lastSignal && instant - lastSignal < 1000) return;
    lastSignal = instant;
    void api.request<void>("/auth/activity", { method: "POST" }).catch(() => {});
  };
  const events = ["keydown", "pointerdown", "pointermove", "wheel"] as const;
  for (const event of events)
    target.addEventListener(event, signal, { passive: true, capture: true });
  return () => {
    for (const event of events) target.removeEventListener(event, signal, true);
  };
}
