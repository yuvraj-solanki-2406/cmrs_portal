"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, clientHeader, refreshAccessToken, setAccessToken, setSessionExpiredHandler } from "@/lib/apiClient";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const clearSession = useCallback(async () => {
    setAccessToken(null);
    setUser(null);
    // Clears the httpOnly refresh cookie + session flag so the route guard stops redirecting.
    await fetch("/api/v1/auth/logout/", { method: "POST", headers: clientHeader }).catch(() => undefined);
  }, []);

  // Restore the session on first load using the httpOnly refresh cookie.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = await refreshAccessToken();
      if (token) {
        try {
          const me = await api<User>("/auth/me/");
          if (!cancelled) setUser(me);
        } catch {
          /* fall through: not signed in */
        }
      }
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setSessionExpiredHandler(() => {
      void clearSession().then(() => router.replace("/login"));
    });
    return () => setSessionExpiredHandler(null);
  }, [clearSession, router]);

  const login = useCallback(async (username: string, password: string) => {
    const data = await api<{ access: string; user: User }>("/auth/login/", {
      method: "POST",
      body: { username, password },
    });
    setAccessToken(data.access);
    setUser(data.user);
  }, []);

  const logout = useCallback(async () => {
    await clearSession();
    router.replace("/login");
  }, [clearSession, router]);

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
