"use client";

import { createContext, useContext } from "react";
import useSWR from "swr";
import { getMe } from "./api";
import type { UserOut } from "./types";

interface AuthContextValue {
  user: UserOut | null;
  isLoading: boolean;
  isError: boolean;
  mutate: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  isLoading: true,
  isError: false,
  mutate: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { data, isLoading, error, mutate } = useSWR("/api/auth/me", getMe, {
    shouldRetryOnError: false,
    revalidateOnFocus: false,
  });

  return (
    <AuthContext.Provider
      value={{
        user: data ?? null,
        isLoading,
        isError: !!error,
        mutate,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
