"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, getCurrentUser, logout as logoutRequest } from "@/lib/api";
import type { AuthUser } from "@/lib/types";

type AuthContextValue = {
  isReady: boolean;
  refreshUser: () => Promise<void>;
  setAuthenticatedUser: (user: AuthUser | null) => void;
  logout: () => Promise<void>;
  user: AuthUser | null;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isReady, setIsReady] = useState(false);

  async function refreshUser() {
    try {
      const currentUser = await getCurrentUser();
      setUser(currentUser);
    } catch (error) {
      if (!(error instanceof ApiError) || error.statusCode !== 401) {
        console.error(error);
      }
      setUser(null);
    } finally {
      setIsReady(true);
    }
  }

  async function logout() {
    try {
      await logoutRequest();
    } finally {
      setUser(null);
    }
  }

  useEffect(() => {
    void refreshUser();
  }, []);

  const value = useMemo(
    () => ({
      isReady,
      refreshUser,
      setAuthenticatedUser: setUser,
      logout,
      user
    }),
    [isReady, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
