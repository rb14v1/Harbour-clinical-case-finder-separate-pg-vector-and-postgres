import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { fetchMe, login as apiLogin, logout as apiLogout, register as apiRegister } from "../api/auth";
import { getRefreshToken, setAccessToken, setRefreshToken } from "../api/client";
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
    const refresh = getRefreshToken();
    if (!refresh) {
      setLoading(false);
      return;
    }
    fetchMe()
      .then((res) => setUser(res.data))
      .catch(() => {
        setRefreshToken(null);
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string): Promise<User> {
    const response = await apiLogin(email, password);
    setAccessToken(response.data.access);
    setRefreshToken(response.data.refresh);
    const me = await fetchMe();
    setUser(me.data);
    return me.data;
  }

  async function register(data: { email: string; password: string; full_name?: string; specialty?: string }) {
    await apiRegister(data);
    await login(data.email, data.password);
  }

  function logout() {
    const refresh = getRefreshToken();
    if (refresh) {
      apiLogout(refresh).catch(() => undefined);
    }
    setAccessToken(null);
    setRefreshToken(null);
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
