/**
 * Authentication/session context. Owns the secure-storage tokens and exposes
 * sign-in / register / sign-out plus a shared HttpClient wired to the token
 * store. The client performs one refresh+retry on 401; if refresh fails the
 * context signs the user out and clears all cached state.
 *
 * The client never logs tokens; this module never puts tokens in React state
 * that could leak into logs — only a boolean `status` is exposed.
 */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { HttpClient, type TokenProvider } from "@/api/client";
import { AuthApi } from "@/api/endpoints";
import * as storage from "@/auth/storage";
import { clearPendingInvitation } from "@/invitation/pendingInvitation";

export type AuthStatus = "loading" | "signed-out" | "signed-in";

interface AuthContextValue {
  status: AuthStatus;
  client: HttpClient;
  signIn: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  signOut: (scope?: "device" | "all") => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }): React.ReactElement {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const queryClient = useQueryClient();
  // In-memory access token cache (avoids a secure-store read per request); the
  // refresh token stays only in secure storage.
  const accessRef = useRef<string | null>(null);

  const clearLocal = useCallback(async () => {
    accessRef.current = null;
    await storage.clearAll();
    queryClient.clear(); // drop the prior user's cached server state
    // Drop any pending invitation context so it cannot leak across an account
    // switch (sign-out clears it; the next sign-in starts clean).
    clearPendingInvitation();
  }, [queryClient]);

  // Build a stable HttpClient bound to a TokenProvider backed by this context.
  const client = useMemo(() => {
    const provider: TokenProvider = {
      getAccessToken: async () => {
        if (accessRef.current) return accessRef.current;
        const a = await storage.getAccessToken();
        accessRef.current = a;
        return a;
      },
      refresh: async () => {
        const refreshToken = await storage.getRefreshToken();
        if (!refreshToken) return null;
        try {
          const tokens = await AuthApi.refresh(bareClient, refreshToken);
          await storage.saveTokens({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
          accessRef.current = tokens.access_token;
          return tokens.access_token;
        } catch {
          return null;
        }
      },
      onAuthLost: async () => {
        await clearLocal();
        setStatus("signed-out");
      },
    };
    // A bare client (no recursive refresh) used only for the refresh call itself.
    const bareClient = new HttpClient({
      getAccessToken: async () => null,
      refresh: async () => null,
      onAuthLost: () => undefined,
    });
    return new HttpClient(provider);
  }, [clearLocal]);

  // Session restoration on launch. Never hangs in "loading": any failure to read
  // the secure store resolves to signed-out (storage.hasSession never throws, but
  // this catch is a belt-and-braces guarantee against an infinite loading state).
  useEffect(() => {
    let active = true;
    void (async () => {
      let restored = false;
      try {
        restored = await storage.hasSession();
      } catch {
        restored = false;
      }
      if (active) setStatus(restored ? "signed-in" : "signed-out");
    })();
    return () => {
      active = false;
    };
  }, []);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const tokens = await AuthApi.login(client, { email, password });
      await storage.saveTokens({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
      accessRef.current = tokens.access_token;
      queryClient.clear();
      setStatus("signed-in");
    },
    [client, queryClient],
  );

  const register = useCallback(
    async (email: string, password: string) => {
      await AuthApi.register(client, { email, password });
      // Registration does not auto-sign-in; the user then signs in explicitly.
    },
    [client],
  );

  const signOut = useCallback(
    async (scope: "device" | "all" = "device") => {
      try {
        if (scope === "all") await AuthApi.logoutAll(client);
        else await AuthApi.logout(client);
      } catch {
        // Even if the network logout fails, always clear local credentials.
      }
      await clearLocal();
      setStatus("signed-out");
    },
    [client, clearLocal],
  );

  const value = useMemo<AuthContextValue>(
    () => ({ status, client, signIn, register, signOut }),
    [status, client, signIn, register, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
