import { Context } from "./useSession";
import {
  Fragment,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { AuthenticatedSession } from "../api/contracts";
import { ApiClient } from "../api/http";
import { createFormTokenStore } from "./formToken";
import { MEDIA_UPDATED } from "../api/recordImages";
import { clearSharedReads } from "../api/sharedRead";
import { clearSessionSnapshots } from "../api/resourceSnapshots";

const AUTH_BOUNDARY = "amafh-core:authentication-boundary";

const PERMISSION_REFRESH_MS = 60_000;
const PERMISSION_REFUSED = "amafh:permission-refused";

function sameIdentity(a: AuthenticatedSession, b: AuthenticatedSession) {
  return (
    a.employeeId === b.employeeId &&
    a.displayName === b.displayName &&
    a.avatarFileId === b.avatarFileId &&
    a.designation === b.designation &&
    a.branchId === b.branchId &&
    a.departmentId === b.departmentId &&
    a.teamId === b.teamId &&
    a.permissions.join(" ") === b.permissions.join(" ")
  );
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [csrf] = useState(createFormTokenStore);
  const [epoch, setEpoch] = useState(0);
  const identityRef = useRef<AuthenticatedSession | null>(null);
  const channelRef = useRef<BroadcastChannel | null>(null);
  const [session, setSession] = useState<AuthenticatedSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");
  const [expired, setExpired] = useState(false);
  const [api] = useState(
    () =>
      new ApiClient(
        () => {
          const value = csrf.get();
          return value ? { header: "X-CSRF-Token", value } : null;
        },
        fetch,
        () => {},
        () => window.dispatchEvent(new Event(PERMISSION_REFUSED)),
      ),
  );
  const boundary = useCallback(
    (code?: string) => {
      api.invalidateSession();
      clearSharedReads(api);
      clearSessionSnapshots(identityRef.current);
      identityRef.current = null;
      csrf.set(null);
      setSession(null);
      setEpoch((value) => value + 1);
      setLoading(false);
      setExpired(code === "SESSION_EXPIRED");
      setNotice(
        code === "CSRF_INVALID"
          ? "Please sign in again to restore your secure form token."
          : "",
      );
      window.history.replaceState(null, "", "/");
      window.dispatchEvent(new PopStateEvent("popstate"));
    },
    [api, csrf],
  );
  useLayoutEffect(() => {
    api.setAuthenticationLostHandler(boundary);
    return () => api.setAuthenticationLostHandler(() => {});
  }, [api, boundary]);
  const announceBoundary = () => {
    channelRef.current?.postMessage("changed");
    try {
      localStorage.setItem(AUTH_BOUNDARY, crypto.randomUUID());
    } catch {
      /* BroadcastChannel remains available when storage is restricted. */
    }
  };
  useEffect(() => {
    const channel =
      typeof BroadcastChannel === "undefined"
        ? null
        : new BroadcastChannel(AUTH_BOUNDARY);
    channelRef.current = channel;
    const changed = () => boundary();
    if (channel) channel.onmessage = changed;
    const storageChanged = (event: StorageEvent) => {
      if (event.key === AUTH_BOUNDARY) changed();
    };
    window.addEventListener("storage", storageChanged);
    return () => {
      channel?.close();
      channelRef.current = null;
      window.removeEventListener("storage", storageChanged);
    };
  }, [boundary]);
  const inFlight = useRef(false);
  const refresh = useCallback(() => {
    if (inFlight.current || !csrf.get()) return;
    inFlight.current = true;
    api
      .request<AuthenticatedSession>("/auth/me")
      .then((identity) => {
        const current = identityRef.current;
        if (current && current.employeeId !== identity.employeeId) {
          boundary();
          return;
        }
        if (current && !sameIdentity(current, identity)) {
          identityRef.current = identity;
          setSession(identity);
        }
      })
      .catch(() => {})
      .finally(() => {
        inFlight.current = false;
      });
  }, [api, csrf, boundary]);
  useEffect(() => {
    let active = true;
    api
      .request<AuthenticatedSession>("/auth/me")
      .then((identity) => {
        if (!active) return;
        if (csrf.get()) {
          identityRef.current = identity;
          setSession(identity);
          setNotice("");
        } else
          setNotice("Please sign in again to restore your secure form token.");
      })
      .catch((error: unknown) => {
        if (
          active &&
          error instanceof Error &&
          !("status" in error && error.status === 401)
        )
          setNotice(error.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api, csrf]);
  const signedIn = session !== null;
  useEffect(() => {
    if (!signedIn) return;
    const onVisible = () => {
      if (document.visibilityState === "visible") refresh();
    };
    window.addEventListener("focus", refresh);
    window.addEventListener(PERMISSION_REFUSED, refresh);
    window.addEventListener(MEDIA_UPDATED, refresh);
    document.addEventListener("visibilitychange", onVisible);
    const timer = window.setInterval(onVisible, PERMISSION_REFRESH_MS);
    return () => {
      window.removeEventListener("focus", refresh);
      window.removeEventListener(PERMISSION_REFUSED, refresh);
      window.removeEventListener(MEDIA_UPDATED, refresh);
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(timer);
    };
  }, [signedIn, refresh]);
  const signIn = async (email: string, password: string) => {
    if (identityRef.current) boundary();
    else {
      // Invalidate earlier attempts without unmounting the form that owns
      // this attempt's busy state, values and error feedback.
      api.invalidateSession();
      clearSharedReads(api);
      csrf.set(null);
    }
    const generation = api.sessionGeneration;
    const result = await api.request<
      AuthenticatedSession & { csrfToken: string }
    >("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: email.trim(), password }),
    });
    api.assertSessionGeneration(generation);
    csrf.set(result.csrfToken);
    const { csrfToken: _, ...identity } = result;
    identityRef.current = identity;
    setSession(identity);
    setNotice("");
    setExpired(false);
    announceBoundary();
  };
  const signOut = async () => {
    await api.request<void>("/auth/logout", { method: "POST" });
    boundary();
    announceBoundary();
  };
  return (
    <Context.Provider
      value={{
        api,
        session,
        loading,
        notice,
        expired,
        dismissExpiry: () => setExpired(false),
        signIn,
        signOut,
        refreshSession: refresh,
      }}
    >
      <Fragment key={epoch}>{children}</Fragment>
    </Context.Provider>
  );
}
