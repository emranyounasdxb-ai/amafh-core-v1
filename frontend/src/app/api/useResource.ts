import { useCallback, useEffect, useState } from "react";
import { useSession } from "../session/useSession";
import type { AuthenticatedSession } from "./contracts";
import { ApiFailure, type ApiClient } from "./http";
import { sharedRead } from "./sharedRead";

type Snapshot<T> = {
  scope: string;
  endpoint: string;
  path: string;
  data: T;
};

type RequestStatus = {
  key: string;
  pending: boolean;
  error: string;
  denied: boolean;
};

const sessionIdentities = new WeakMap<AuthenticatedSession, number>();
// A new authenticated session gets a different object, so retained reads cannot cross logins.
const sessionSnapshots = new WeakMap<
  AuthenticatedSession,
  Map<string, Snapshot<unknown>>
>();
let nextSessionIdentity = 0;
const snapshotLimit = 64;

function sessionIdentity(session: AuthenticatedSession) {
  let identity = sessionIdentities.get(session);
  if (identity === undefined) {
    identity = ++nextSessionIdentity;
    sessionIdentities.set(session, identity);
  }
  return identity;
}

function normalizedPath(path: string) {
  const [endpoint, search] = path.split("?", 2);
  if (!search) return endpoint;
  const parameters = new URLSearchParams(search);
  parameters.sort();
  return `${endpoint}?${parameters}`;
}

function snapshotKey(path: string, kind: string) {
  return JSON.stringify([kind, normalizedPath(path)]);
}

function rememberSnapshot<T>(
  session: AuthenticatedSession,
  path: string,
  kind: string,
  snapshot: Snapshot<T>,
) {
  let entries = sessionSnapshots.get(session);
  if (!entries) {
    entries = new Map();
    sessionSnapshots.set(session, entries);
  }
  const key = snapshotKey(path, kind);
  entries.delete(key);
  entries.set(key, snapshot);
  if (entries.size > snapshotLimit)
    entries.delete(entries.keys().next().value!);
}

function accessLost(error: unknown) {
  return (
    error instanceof ApiFailure &&
    ([401, 403, 404].includes(error.status) || error.code === "CSRF_INVALID")
  );
}

export function useResource<T>(
  path: string | null,
  refreshKey: string | number = 0,
  load?: (api: ApiClient, path: string, signal: AbortSignal) => Promise<T>,
  cacheKind?: string,
) {
  const { api, session } = useSession();
  const [version, setVersion] = useState(0);
  const scope = JSON.stringify(
    session && [
      sessionIdentity(session),
      session.employeeId,
      session.designation,
      session.branchId,
      session.departmentId,
      session.teamId,
    ],
  );
  const endpoint = path?.split("?", 1)[0] || "";
  // Custom loaders opt in with a distinct kind to avoid sharing a path's raw shape.
  const kind = cacheKind || (load ? null : "raw");
  const key = JSON.stringify([
    path && normalizedPath(path),
    version,
    refreshKey,
    scope,
    Boolean(load),
  ]);
  const [snapshot, setSnapshot] = useState<Snapshot<T> | null>(null);
  const [status, setStatus] = useState<RequestStatus | null>(null);
  const reload = useCallback(() => setVersion((value) => value + 1), []);

  if (path && session && status?.key !== key) {
    setStatus({ key, pending: true, error: "", denied: false });
  }

  useEffect(() => {
    if (!path || !session) return;
    const controller = new AbortController();
    sharedRead<T>(api, key, path, controller.signal, load)
      .then((data) => {
        if (controller.signal.aborted) return;
        const next = { scope, endpoint, path, data };
        setSnapshot(next);
        if (kind) rememberSnapshot(session, path, kind, next);
        setStatus({ key, pending: false, error: "", denied: false });
      })
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return;
        if (accessLost(failure)) {
          setSnapshot(null);
          sessionSnapshots.get(session)?.clear();
        }
        setStatus({
          key,
          pending: false,
          denied: accessLost(failure),
          error:
            failure instanceof Error
              ? failure.message
              : "The server could not be reached.",
        });
      });
    return () => controller.abort();
  }, [api, path, key, session, scope, endpoint, load, kind]);

  const current = status?.key === key;
  const denied = Boolean(current && status?.denied);
  const cached =
    path && session && kind
      ? (sessionSnapshots.get(session)?.get(snapshotKey(path, kind)) as
          Snapshot<T> | undefined)
      : undefined;
  const retained =
    !denied &&
    path &&
    session &&
    snapshot?.scope === scope &&
    snapshot.endpoint === endpoint
      ? snapshot
      : null;
  const visible = !denied && cached?.scope === scope ? cached : retained;
  const data = visible?.data ?? null;
  const loading = Boolean(path && session && (!current || status?.pending));
  return {
    data,
    dataPath: visible?.path || null,
    error: current && !loading ? status?.error || "" : "",
    denied,
    loading,
    updating: loading && data !== null,
    reload,
  };
}
