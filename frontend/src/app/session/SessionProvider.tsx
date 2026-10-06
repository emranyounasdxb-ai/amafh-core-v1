import { Context } from "./useSession";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { AuthenticatedSession } from "../api/contracts";
import { ApiClient } from "../api/http";
import { createFormTokenStore } from "./formToken";

const PERMISSION_REFRESH_MS = 60_000;
const PERMISSION_REFUSED = "amafh:permission-refused";

function sameIdentity(a: AuthenticatedSession, b: AuthenticatedSession) {
  return (
    a.employeeId === b.employeeId &&
    a.displayName === b.displayName &&
    a.designation === b.designation &&
    a.branchId === b.branchId &&
    a.departmentId === b.departmentId &&
    a.teamId === b.teamId &&
    a.permissions.join(" ") === b.permissions.join(" ")
  );
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [csrf] = useState(createFormTokenStore);
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
        (code) => {
          csrf.set(null);
          setSession(null);
          if (code === "SESSION_EXPIRED") setExpired(true);
          setNotice(
            code === "CSRF_INVALID"
              ? "Please sign in again to restore your secure form token."
              : "",
          );
        },
        () => window.dispatchEvent(new Event(PERMISSION_REFUSED)),
      ),
  );
  const inFlight = useRef(false);
  const refresh = useCallback(() => {
    if (inFlight.current || !csrf.get()) return;
    inFlight.current = true;
    api
      .request<AuthenticatedSession>("/auth/me")
      .then((identity) => {
        setSession((current) =>
          current &&
          current.employeeId === identity.employeeId &&
          !sameIdentity(current, identity)
            ? identity
            : current,
        );
      })
      .catch(() => {})
      .finally(() => {
        inFlight.current = false;
      });
  }, [api, csrf]);
  useEffect(() => {
    let active = true;
    api
      .request<AuthenticatedSession>("/auth/me")
      .then((identity) => {
        if (!active) return;
        if (csrf.get()) {
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
    document.addEventListener("visibilitychange", onVisible);
    const timer = window.setInterval(onVisible, PERMISSION_REFRESH_MS);
    return () => {
      window.removeEventListener("focus", refresh);
      window.removeEventListener(PERMISSION_REFUSED, refresh);
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(timer);
    };
  }, [signedIn, refresh]);
  const signIn = async (email: string, password: string) => {
    const result = await api.request<
      AuthenticatedSession & { csrfToken: string }
    >("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: email.trim(), password }),
    });
    csrf.set(result.csrfToken);
    const { csrfToken: _, ...identity } = result;
    setSession(identity);
    setNotice("");
    setExpired(false);
  };
  const signOut = async () => {
    await api.request<void>("/auth/logout", { method: "POST" });
    csrf.set(null);
    setSession(null);
    setNotice("");
    setExpired(false);
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
      {children}
    </Context.Provider>
  );
}
