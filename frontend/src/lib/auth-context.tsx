"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Auth, getToken, setToken } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    if (!getToken()) {
      setLoading(false);
      return;
    }
    Auth.me()
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => setToken(null))
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await Auth.login(email, password);
    setToken(access_token);
    setUser(await Auth.me());
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const { access_token } = await Auth.register(email, password);
    setToken(access_token);
    setUser(await Auth.me());
  }, []);

  const logout = useCallback(() => {
    // Revoke the token server-side (best-effort), then clear local state.
    Auth.logout().catch(() => undefined);
    setToken(null);
    setUser(null);
    window.location.href = "/register";
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout }),
    [user, loading, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
