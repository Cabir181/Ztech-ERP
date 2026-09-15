/**
 * Who is signed in, what they may do, and the client's branding.
 *
 * The permission list held here decides what the interface offers. It is a
 * usability measure only: the server re-checks every request independently, so
 * a permission that is somehow stale here changes what is shown, never what is
 * allowed.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, api } from "../api/client";
import type { Session } from "../api/types";

interface SessionContextValue {
  session: Session | null;
  loading: boolean;
  /** True once the first session check has completed, successfully or not. */
  ready: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
  can: (...permissions: string[]) => boolean;
}

const SessionContext = createContext<SessionContextValue | null>(null);

function applyBranding(session: Session | null): void {
  const root = document.documentElement;
  if (!session) {
    root.style.removeProperty("--brand");
    root.style.removeProperty("--brand-accent");
    document.title = "Ztech Sales";
    return;
  }
  root.style.setProperty("--brand", session.company.brand_primary_color);
  root.style.setProperty("--brand-accent", session.company.brand_accent_color);
  document.title = `${session.company.display_name} — Ztech Sales`;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState(false);

  const load = useCallback(async () => {
    try {
      const next = await api.get<Session>("/api/auth/session/");
      setSession(next);
      applyBranding(next);
    } catch (error) {
      // Not being signed in is the normal first-load case, not a failure.
      if (!(error instanceof ApiError) || error.status >= 500) {
        console.error("Could not load the session.", error);
      }
      setSession(null);
      applyBranding(null);
    } finally {
      setLoading(false);
      setReady(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const signIn = useCallback(async (email: string, password: string) => {
    const next = await api.post<Session>("/api/auth/login/", { email, password });
    setSession(next);
    applyBranding(next);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.post("/api/auth/logout/");
    } finally {
      setSession(null);
      applyBranding(null);
    }
  }, []);

  const can = useCallback(
    (...permissions: string[]) => {
      if (!session) return false;
      return permissions.some((permission) => session.permissions.includes(permission));
    },
    [session],
  );

  const value = useMemo<SessionContextValue>(
    () => ({ session, loading, ready, signIn, signOut, refresh: load, can }),
    [session, loading, ready, signIn, signOut, load, can],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used inside a SessionProvider.");
  return context;
}

/** The signed-in session, for screens that only render behind the sign-in gate. */
export function useCurrentSession(): Session {
  const { session } = useSession();
  if (!session) throw new Error("This screen requires a signed-in session.");
  return session;
}
