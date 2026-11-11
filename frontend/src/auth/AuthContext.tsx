import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { fetchMe, login as apiLogin, logout as apiLogout, register as apiRegister } from "../api/auth";
import { refreshAccessToken, setAccessToken } from "../api/client";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (data: { email: string; password: string; full_name?: string; specialty?: string }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Restore the session from the HttpOnly refresh cookie or the backend's
    // Entra ID OIDC session - nothing is read from browser storage.
    refreshAccessToken()
      .then(async (token) => {
        if (!token) return;
        const res = await fetchMe();
        setUser(res.data);
      })
      .catch(() => {
        setAccessToken(null);
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string): Promise<User> {
    const response = await apiLogin(email, password);
    // The refresh token is set by the backend as an HttpOnly cookie.
    setAccessToken(response.data.access);
    const me = await fetchMe();
    setUser(me.data);
    return me.data;
  }

  async function register(data: { email: string; password: string; full_name?: string; specialty?: string }) {
    await apiRegister(data);
    await login(data.email, data.password);
  }

  function logout() {
    // Backend blacklists the refresh cookie, clears it and ends the OIDC session.
    apiLogout()
      .catch(() => undefined)
      .finally(() => setAccessToken(null));
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
