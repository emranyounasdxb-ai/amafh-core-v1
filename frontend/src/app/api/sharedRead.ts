import type { ApiClient } from "./http";

type InFlight = {
  controller: AbortController;
  promise: Promise<unknown>;
  readers: number;
};

const inFlight = new WeakMap<ApiClient, Map<string, InFlight>>();

export function clearSharedReads(api: ApiClient) {
  for (const entry of inFlight.get(api)?.values() ?? [])
    entry.controller.abort();
  inFlight.delete(api);
}

export function sharedRead<T>(
  api: ApiClient,
  key: string,
  path: string,
  signal: AbortSignal,
  load?: (api: ApiClient, path: string, signal: AbortSignal) => Promise<T>,
): Promise<T> {
  const generation = api.sessionGeneration;
  let requests = inFlight.get(api);
  if (!requests) {
    requests = new Map();
    inFlight.set(api, requests);
  }
  const registry = requests;
  let entry = registry.get(key);
  if (entry?.controller.signal.aborted) {
    registry.delete(key);
    entry = undefined;
  }
  if (!entry) {
    const controller = new AbortController();
    const created: InFlight = {
      controller,
      readers: 0,
      promise: Promise.resolve().then(async () => {
        api.assertSessionGeneration(generation);
        const result = await (load
          ? load(api, path, controller.signal)
          : api.request<T>(path, { signal: controller.signal }));
        api.assertSessionGeneration(generation);
        return result;
      }),
    };
    entry = created;
    registry.set(key, created);
    void created.promise
      .finally(() => {
        if (registry.get(key) === created) registry.delete(key);
      })
      .catch(() => {});
  }
  const active = entry;
  active.readers += 1;
  let released = false;
  const release = () => {
    if (released) return;
    released = true;
    active.readers -= 1;
    if (active.readers === 0)
      queueMicrotask(() => {
        if (active.readers === 0) active.controller.abort();
      });
  };
  signal.addEventListener("abort", release, { once: true });
  if (signal.aborted) release();
  return active.promise.finally(() => {
    signal.removeEventListener("abort", release);
    release();
  }) as Promise<T>;
}
