import { createContext, useContext } from "react";
import type { AuthenticatedSession } from "../api/contracts";
import type { ApiClient } from "../api/http";
type SessionState = {
  api: ApiClient;
  session: AuthenticatedSession | null;
  loading: boolean;
  notice: string;
  expired: boolean;
  dismissExpiry: () => void;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshSession: () => void;
};
export const Context = createContext<SessionState | null>(null);
export function useSession() {
  const value = useContext(Context);
  if (!value) throw new Error("SessionProvider required");
  return value;
}
