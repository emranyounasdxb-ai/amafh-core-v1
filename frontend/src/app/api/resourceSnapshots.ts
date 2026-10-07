import type { AuthenticatedSession } from "./contracts";

export type Snapshot<T> = {
  scope: string;
  endpoint: string;
  path: string;
  data: T;
};

export const sessionSnapshots = new WeakMap<
  AuthenticatedSession,
  Map<string, Snapshot<unknown>>
>();

export function clearSessionSnapshots(session: AuthenticatedSession | null) {
  if (session) sessionSnapshots.delete(session);
}
